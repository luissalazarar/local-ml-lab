"""Conservative, deterministic data preparation.

This module only normalizes representations chosen by the user. It deliberately
does not impute, scale, encode, select features, or learn target statistics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import xlsxwriter

from local_ml_lab.domain.contracts import PreparationRecipe

CURRENCY_MARKERS = {
    "PEN": ("S/", "PEN"),
    "USD": ("US$", "USD", "$"),
    "EUR": ("€", "EUR"),
}


class PreparationError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class PreparationResult:
    frame: pd.DataFrame
    quarantined: list[dict[str, Any]]
    transformations: list[dict[str, Any]]
    preview: list[dict[str, Any]]
    type_overrides: dict[str, str]
    roles: dict[str, str]
    row_ids: list[str]


def canonical_recipe(recipe: PreparationRecipe | dict) -> dict:
    model = (
        recipe
        if isinstance(recipe, PreparationRecipe)
        else PreparationRecipe.model_validate(recipe)
    )
    return model.model_dump(mode="json", exclude_none=True)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    """Content hash independent from parquet transport metadata."""
    digest = hashlib.sha256()
    digest.update(b'{"columns":')
    digest.update(
        json.dumps(
            list(frame.columns), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    )
    digest.update(b',"rows":[')
    first = True
    for row in frame.itertuples(index=False, name=None):
        if not first:
            digest.update(b",")
        digest.update(
            json.dumps(
                [_json_value(value) for value in row],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        first = False
    digest.update(b"]}")
    return digest.hexdigest()


def suggest_preparation(frame: pd.DataFrame, profile: dict, source_extension: str) -> dict:
    columns = []
    for meta in profile["columns"]:
        column_id = meta["column_id"]
        series = frame[column_id]
        values = [_safe_example(v) for v in series.dropna().head(4)]
        detected = meta["inferred_semantic_type"]
        alerts = list(meta.get("quality_issue_codes", []))
        suggestion: dict[str, Any] = {
            "type": "auto",
            "role": "identifier" if meta.get("possible_id") else "variable",
            "trim": bool(_exterior_space_count(series)),
            "empty_to_missing": bool(_empty_string_count(series)),
        }
        numeric = detect_numeric_pattern(series)
        dates = detect_date_pattern(series, source_extension)
        if numeric["looks_numeric"] and detected != "numeric":
            alerts.append("NUMBER_STORED_AS_TEXT")
            suggestion.update(
                {
                    "type": "numeric",
                    "decimal_separator": numeric["decimal_separator"],
                    "thousands_separator": numeric["thousands_separator"],
                    "percent": numeric["percent"],
                    "currency": numeric["currency"],
                }
            )
        elif dates["looks_date"] and not pd.api.types.is_datetime64_any_dtype(series):
            alerts.append("DATE_STORED_AS_TEXT")
            suggestion.update({"type": "date", "date_format": dates["recommended_format"]})
        if numeric["mixed_currencies"]:
            alerts.append("MIXED_CURRENCIES")
            suggestion = {"type": "auto", "role": suggestion["role"]}
        if dates["ambiguous"]:
            alerts.append("AMBIGUOUS_DATE")
        if meta["distinct_count"] <= 1:
            suggestion["role"] = "ignore"
        columns.append(
            {
                **meta,
                "examples": values,
                "alerts": sorted(set(alerts)),
                "recommended": suggestion,
                "numeric_pattern": numeric,
                "date_pattern": dates,
            }
        )
    return {"columns": columns, "duplicate_count": int(frame.duplicated().sum())}


def apply_recipe(
    source: pd.DataFrame,
    recipe: PreparationRecipe | dict,
    *,
    source_extension: str,
    preview_limit: int = 30,
) -> PreparationResult:
    recipe = (
        recipe
        if isinstance(recipe, PreparationRecipe)
        else PreparationRecipe.model_validate(recipe)
    )
    unknown = set(recipe.columns) - set(source.columns)
    referenced = {item.column_id for item in recipe.filters}
    if recipe.monthly_aggregation:
        referenced |= {
            recipe.monthly_aggregation.date_column_id,
            recipe.monthly_aggregation.value_column_id,
        }
    if unknown or referenced - set(source.columns):
        raise PreparationError("UNKNOWN_COLUMN", "La receta menciona columnas inexistentes")

    frame = source.copy(deep=True)
    row_ids = [f"row-{index + 1:07d}" for index in range(len(frame))]
    active = pd.Series(True, index=frame.index)
    quarantined: list[dict[str, Any]] = []
    transformations: list[dict[str, Any]] = []
    preview: list[dict[str, Any]] = []
    type_overrides: dict[str, str] = {}
    roles: dict[str, str] = {}

    for column_id, config in recipe.columns.items():
        original = frame[column_id].copy()
        converted = original.copy()
        roles[column_id] = config.role
        if config.trim:
            converted = converted.map(_trim_value)
        if config.empty_to_missing:
            converted = converted.map(_empty_to_missing)
        if config.category_merges:
            merges = config.category_merges
            converted = converted.map(
                lambda value, category_merges=merges: category_merges.get(value, value)
                if isinstance(value, str)
                else value
            )

        invalid = pd.Series(False, index=frame.index)
        reason = ""
        if config.type == "date":
            converted, invalid = convert_dates(
                converted,
                config.date_format or "UNAMBIGUOUS",
                source_extension=source_extension,
                allow_excel_serials=config.excel_date_serials,
            )
            type_overrides[column_id] = "datetime"
            reason = "La fecha no pudo interpretarse con el formato confirmado"
        elif config.type == "numeric":
            converted, invalid = convert_numbers(
                converted,
                decimal=config.decimal_separator,
                thousands=config.thousands_separator,
                percent=config.percent,
                currency=config.currency,
            )
            type_overrides[column_id] = "numeric"
            reason = "El número no pudo interpretarse con los separadores confirmados"
        elif config.type == "categorical":
            converted = converted.map(_text_or_none)
            type_overrides[column_id] = "categorical"
        elif config.type == "text":
            converted = converted.map(_text_or_none)
            type_overrides[column_id] = "text"

        invalid_count = int((invalid & active).sum())
        if invalid_count and config.invalid == "block":
            examples = [_safe_example(v) for v in original[invalid].head(3)]
            raise PreparationError(
                "UNCONVERTIBLE_VALUES",
                f"{column_id} tiene {invalid_count} valores no convertibles: {examples}",
            )
        if invalid_count:
            for index in frame.index[invalid & active]:
                quarantined.append(
                    quarantine_row(
                        row_ids[index], reason, column_id, original.loc[index], "preparación"
                    )
                )
            active &= ~invalid

        changed = _changed_mask(original, converted)
        frame[column_id] = converted
        changed_count = int(changed.sum())
        if changed_count or config.type != "auto" or config.role != "variable":
            transformations.append(
                {
                    "column_id": column_id,
                    "transformation": _describe_transformation(config),
                    "affected_count": changed_count,
                    "invalid_count": invalid_count,
                    "type_before": _simple_dtype(original),
                    "type_after": config.type,
                }
            )
        for index in frame.index[changed][:preview_limit]:
            preview.append(
                {
                    "row_id": row_ids[index],
                    "column_id": column_id,
                    "before": _safe_example(original.loc[index]),
                    "after": _safe_example(converted.loc[index]),
                }
            )

    if recipe.exact_duplicates == "exclude":
        duplicate = frame.duplicated(keep="first") & active
        for index in frame.index[duplicate]:
            quarantined.append(
                quarantine_row(
                    row_ids[index],
                    "Duplicado exacto excluido por decisión del usuario",
                    None,
                    None,
                    "duplicados",
                )
            )
        active &= ~duplicate
        transformations.append(
            {
                "column_id": None,
                "transformation": "Excluir duplicados exactos conservando la primera aparición",
                "affected_count": int(duplicate.sum()),
                "invalid_count": 0,
                "type_before": None,
                "type_after": None,
            }
        )

    for row_filter in recipe.filters:
        excluded = _filter_exclusions(frame, active, row_filter)
        description = _describe_filter(row_filter)
        for index in frame.index[excluded]:
            quarantined.append(
                quarantine_row(
                    row_ids[index],
                    description,
                    row_filter.column_id,
                    frame.loc[index, row_filter.column_id],
                    "filtro",
                )
            )
        active &= ~excluded
        transformations.append(
            {
                "column_id": row_filter.column_id,
                "transformation": description,
                "affected_count": int(excluded.sum()),
                "invalid_count": 0,
                "type_before": None,
                "type_after": None,
            }
        )

    active_frame = frame.loc[active].reset_index(drop=True)
    active_row_ids = [row_ids[index] for index in frame.index[active]]
    if recipe.monthly_aggregation:
        active_frame, active_row_ids, summary = _aggregate_monthly(
            active_frame, active_row_ids, recipe.monthly_aggregation
        )
        transformations.append(summary)

    return PreparationResult(
        frame=active_frame,
        quarantined=quarantined,
        transformations=transformations,
        preview=preview[:preview_limit],
        type_overrides=type_overrides,
        roles=roles,
        row_ids=active_row_ids,
    )


def quality_comparison(original_profile: dict, prepared_profile: dict) -> dict:
    return {
        "original": _quality_summary(original_profile),
        "prepared": _quality_summary(prepared_profile),
    }


def export_prepared_excel(
    path: Path,
    frame: pd.DataFrame,
    mapping: list[dict],
    quarantined: list[dict],
    transformations: list[dict],
    quality: dict,
    roles: dict[str, str],
) -> None:
    names = {item["column_id"]: item["display_name"] for item in mapping}
    workbook = xlsxwriter.Workbook(
        path, {"constant_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    )
    header = workbook.add_format({"bold": True, "bg_color": "#054D61", "font_color": "white"})
    prepared = workbook.add_worksheet("01_Datos_Preparados")
    prepared.freeze_panes(1, 0)
    for col, column_id in enumerate(frame.columns):
        prepared.write(0, col, safe_excel_value(names.get(column_id, column_id)), header)
    for row, values in enumerate(frame.itertuples(index=False, name=None), 1):
        for col, value in enumerate(values):
            prepared.write(row, col, safe_excel_value(value))
    _write_records(workbook.add_worksheet("02_Filas_Apartadas"), quarantined, header)
    _write_records(workbook.add_worksheet("03_Transformaciones"), transformations, header)
    quality_rows = [
        {
            "indicador": key,
            "original": quality["original"].get(key),
            "preparado": quality["prepared"].get(key),
        }
        for key in quality["original"]
    ]
    _write_records(workbook.add_worksheet("04_Calidad"), quality_rows, header)
    dictionary = [
        {
            "Columna": names.get(column_id, column_id),
            "Qué contiene": _human_dtype(frame[column_id]),
            "Cómo se usa": {
                "variable": "Variable que puede aportar información al modelo",
                "identifier": "Identificador; no se usa para aprender patrones",
                "ignore": "Ignorada en el modelado",
            }.get(roles.get(column_id, "variable"), "Variable"),
        }
        for column_id in frame.columns
    ]
    dictionary.extend(
        [
            {
                "Columna": "Filas apartadas",
                "Qué contiene": "Concepto",
                "Cómo se usa": "Filas conservadas aparte que no participan en esta versión.",
            },
            {
                "Columna": "Versión preparada",
                "Qué contiene": "Concepto",
                "Cómo se usa": "Representaciones confirmadas antes del análisis; no incluye imputación, escalado ni codificación aprendida.",
            },
        ]
    )
    _write_records(workbook.add_worksheet("05_Diccionario"), dictionary, header)
    workbook.close()


def _human_dtype(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return "Fecha"
    if pd.api.types.is_numeric_dtype(series):
        return "Número"
    return "Categoría o texto"


def detect_numeric_pattern(series: pd.Series) -> dict:
    values = [str(v).strip() for v in series.dropna() if str(v).strip()][:200]
    currencies = {
        code
        for code, markers in CURRENCY_MARKERS.items()
        if any(any(marker in value for marker in markers) for value in values)
    }
    percent = bool(values) and sum(value.endswith("%") for value in values) / len(values) >= 0.8
    decimal, thousands = None, None
    comma_decimal = sum(bool(re.search(r",\d{1,4}\s*%?$", value)) for value in values)
    dot_decimal = sum(bool(re.search(r"\.\d{1,4}\s*%?$", value)) for value in values)
    if comma_decimal > dot_decimal and comma_decimal >= max(2, math.ceil(len(values) * 0.6)):
        decimal = ","
        thousands = "." if sum("." in value for value in values) >= 2 else None
    elif dot_decimal > comma_decimal and dot_decimal >= max(2, math.ceil(len(values) * 0.6)):
        decimal = "."
        thousands = "," if sum("," in value for value in values) >= 2 else None
    simple = 0
    for value in values:
        stripped = _strip_currency(value).rstrip("%").strip().replace(" ", "")
        candidate = stripped
        if thousands:
            candidate = candidate.replace(thousands, "")
        if decimal:
            candidate = candidate.replace(decimal, ".")
        try:
            float(candidate)
            simple += 1
        except ValueError:
            pass
    return {
        "looks_numeric": bool(values) and simple / len(values) >= 0.9 and not len(currencies) > 1,
        "decimal_separator": decimal,
        "thousands_separator": thousands,
        "percent": percent,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "mixed_currencies": len(currencies) > 1,
    }


def detect_date_pattern(series: pd.Series, source_extension: str) -> dict:
    if pd.api.types.is_datetime64_any_dtype(series):
        return {
            "looks_date": True,
            "ambiguous": False,
            "recommended_format": "YMD",
            "excel_serials": source_extension == ".xlsx",
        }
    values = [str(v).strip() for v in series.dropna() if str(v).strip()][:200]
    iso = sum(bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ T].*)?$", v)) for v in values)
    dmy_like = [v for v in values if re.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}(?:[ T].*)?$", v)]
    ambiguous = any(
        int(re.split(r"[-/]", v)[0]) <= 12 and int(re.split(r"[-/]", v)[1]) <= 12 for v in dmy_like
    )
    looks = bool(values) and (iso + len(dmy_like)) / len(values) >= 0.9
    return {
        "looks_date": looks,
        "ambiguous": ambiguous,
        "recommended_format": "YMD" if iso >= len(dmy_like) else (None if ambiguous else "DMY"),
        "excel_serials": False,
    }


def convert_dates(series, date_format, *, source_extension, allow_excel_serials):
    results = []
    invalid = []
    for value in series:
        if _is_missing(value):
            results.append(pd.NaT)
            invalid.append(False)
            continue
        parsed = _parse_date(value, date_format, source_extension, allow_excel_serials)
        results.append(parsed if parsed is not None else pd.NaT)
        invalid.append(parsed is None)
    return pd.Series(results, index=series.index, dtype="datetime64[ns]"), pd.Series(
        invalid, index=series.index
    )


def _parse_date(value, date_format, source_extension, allow_excel_serials):
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).normalize()
    if (
        allow_excel_serials
        and source_extension == ".xlsx"
        and isinstance(value, (int, float))
        and 1 <= value <= 2_958_465
    ):
        return (pd.Timestamp("1899-12-30") + pd.to_timedelta(float(value), unit="D")).normalize()
    text = str(value).strip()
    formats = {
        "DMY": ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M:%S"],
        "MDY": ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%Y %H:%M:%S", "%m-%d-%Y %H:%M:%S"],
        "YMD": [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ],
        "UNAMBIGUOUS": ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"],
    }
    candidates = formats[date_format]
    if date_format == "UNAMBIGUOUS":
        match = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", text)
        if match:
            first, second = int(match[1]), int(match[2])
            if first <= 12 and second <= 12:
                return None
            candidates = ["%d/%m/%Y", "%d-%m-%Y"] if first > 12 else ["%m/%d/%Y", "%m-%d-%Y"]
    for pattern in candidates:
        try:
            return pd.Timestamp(datetime.strptime(text, pattern)).normalize()
        except ValueError:
            continue
    return None


def convert_numbers(series, *, decimal, thousands, percent, currency):
    if currency:
        observed = {
            code
            for code, markers in CURRENCY_MARKERS.items()
            if any(any(marker in str(value) for marker in markers) for value in series.dropna())
        }
        if observed - {currency}:
            raise PreparationError("MIXED_CURRENCIES", "La columna contiene más de una moneda")
    results, invalid = [], []
    for value in series:
        if _is_missing(value):
            results.append(float("nan"))
            invalid.append(False)
            continue
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            number = float(value)
        else:
            text = str(value).strip()
            if currency:
                text = _strip_currency(text)
            if text.endswith("%"):
                if not percent:
                    results.append(float("nan"))
                    invalid.append(True)
                    continue
                text = text[:-1].strip()
            elif percent:
                results.append(float("nan"))
                invalid.append(True)
                continue
            text = text.replace("\u00a0", " ").strip()
            if thousands:
                text = text.replace(thousands, "")
            if decimal:
                text = text.replace(decimal, ".")
            if re.search(r"[^0-9+\-.eE]", text):
                results.append(float("nan"))
                invalid.append(True)
                continue
            try:
                number = float(text)
            except ValueError:
                results.append(float("nan"))
                invalid.append(True)
                continue
        if percent:
            number /= 100.0
        results.append(number)
        invalid.append(False)
    return pd.Series(results, index=series.index, dtype="float64"), pd.Series(
        invalid, index=series.index
    )


def quarantine_row(row_id, reason, column_id, value, stage):
    return {
        "row_id": row_id,
        "reason": reason,
        "column_id": column_id,
        "original_value": _safe_example(value),
        "stage": stage,
    }


def safe_excel_value(value):
    if _is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value.item() if hasattr(value, "item") else value


def _filter_exclusions(frame, active, row_filter):
    series = frame[row_filter.column_id]
    if row_filter.kind == "date_range":
        parsed = pd.to_datetime(series, errors="coerce")
        keep = pd.Series(True, index=series.index)
        if row_filter.start:
            keep &= parsed >= pd.Timestamp(row_filter.start)
        if row_filter.end:
            keep &= parsed <= pd.Timestamp(row_filter.end)
    elif row_filter.kind == "category":
        included = series.astype("string").isin(row_filter.values)
        keep = included if row_filter.mode == "include" else ~included
    else:
        keep = pd.to_numeric(series, errors="coerce").notna()
    return active & ~keep.fillna(False)


def _aggregate_monthly(frame, row_ids, config):
    dates = pd.to_datetime(frame[config.date_column_id], errors="coerce")
    values = pd.to_numeric(frame[config.value_column_id], errors="coerce")
    if dates.isna().any() or values.isna().any():
        raise PreparationError(
            "AGGREGATION_INVALID_VALUES", "La agregación mensual requiere fechas y números válidos"
        )
    work = pd.DataFrame({"month": dates.dt.to_period("M").dt.to_timestamp(), "value": values})
    grouped = work.groupby("month", sort=True)["value"].agg(config.operation).reset_index()
    result = pd.DataFrame(
        {config.date_column_id: grouped["month"], config.value_column_id: grouped["value"]}
    )
    return (
        result,
        [f"month-{value:%Y-%m}" for value in grouped["month"]],
        {
            "column_id": config.value_column_id,
            "transformation": f"Agrupar por mes usando {'suma' if config.operation == 'sum' else 'promedio'}",
            "affected_count": len(frame),
            "invalid_count": 0,
            "type_before": "filas",
            "type_after": "serie mensual",
        },
    )


def _describe_filter(item):
    if item.kind == "date_range":
        return f"Filtrar periodo entre {item.start or 'inicio'} y {item.end or 'fin'}"
    if item.kind == "category":
        return f"{'Incluir' if item.mode == 'include' else 'Excluir'} categorías confirmadas"
    return "Excluir filas sin valor numérico"


def _describe_transformation(config):
    pieces = []
    if config.trim:
        pieces.append("quitar espacios exteriores")
    if config.empty_to_missing:
        pieces.append("convertir textos vacíos en faltantes")
    if config.type == "date":
        pieces.append(f"interpretar como fecha {config.date_format or 'inequívoca'}")
    if config.type == "numeric":
        pieces.append("interpretar como número")
        if config.percent:
            pieces.append("convertir porcentaje a proporción")
        if config.currency:
            pieces.append(f"retirar símbolo {config.currency} conservando la unidad")
    if config.category_merges:
        pieces.append("unificar categorías confirmadas")
    if config.role != "variable":
        pieces.append(f"usar como {config.role}")
    return "; ".join(pieces) or "Conservar representación"


def _quality_summary(profile):
    return {
        "filas": profile["row_count"],
        "columnas_numericas": sum(
            c["inferred_semantic_type"] == "numeric" for c in profile["columns"]
        ),
        "columnas_fecha": sum(
            c["inferred_semantic_type"] == "datetime" for c in profile["columns"]
        ),
        "faltantes": sum(c["null_count"] for c in profile["columns"]),
        "duplicados": profile["duplicate_count"],
    }


def _write_records(sheet, rows, header):
    rows = rows or [{"estado": "Sin registros"}]
    columns = list(dict.fromkeys(key for row in rows for key in row))
    sheet.freeze_panes(1, 0)
    sheet.set_column(0, max(0, len(columns) - 1), 24)
    for col, key in enumerate(columns):
        sheet.write(0, col, key, header)
    for row_index, row in enumerate(rows, 1):
        for col, key in enumerate(columns):
            sheet.write(row_index, col, safe_excel_value(row.get(key)))


def _changed_mask(before, after):
    left = before.map(_json_value)
    right = after.map(_json_value)
    return left != right


def _json_value(value):
    if _is_missing(value):
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).isoformat()
    if hasattr(value, "item"):
        value = value.item()
    return value


def _safe_example(value):
    value = _json_value(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value).replace("\n", " ").replace("\r", " ")[:120]


def _is_missing(value):
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _trim_value(value):
    return value.strip() if isinstance(value, str) else value


def _empty_to_missing(value):
    return None if isinstance(value, str) and not value.strip() else value


def _text_or_none(value):
    return None if _is_missing(value) else str(value)


def _exterior_space_count(series):
    return sum(isinstance(v, str) and v != v.strip() for v in series.dropna())


def _empty_string_count(series):
    return sum(isinstance(v, str) and not v.strip() for v in series.dropna())


def _strip_currency(value):
    for markers in CURRENCY_MARKERS.values():
        for marker in markers:
            value = value.replace(marker, "")
    return value.strip()


def _simple_dtype(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "text"
