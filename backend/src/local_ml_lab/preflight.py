"""Educational checks that run before starting CPU work."""

from __future__ import annotations

import pandas as pd


def _issue(code: str, explanation: str, suggestion: str) -> dict[str, str]:
    return {"code": code, "explanation": explanation, "suggestion": suggestion}


def evaluate_preflight(frame: pd.DataFrame, profile: dict, config: dict) -> dict:
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    columns = {column["column_id"]: column for column in profile.get("columns", [])}
    problem = config["problem_type"]
    target = config.get("target_column_id")
    expected = {
        "estimate_value": {"regression"},
        "classify": {"classification"},
        "forecast": {"forecasting"},
        "drivers": {"regression", "classification"},
        "explore": {"exploration"},
    }.get(config.get("goal"), set())
    if expected and problem not in expected:
        blockers.append(_issue(
            "GOAL_PROBLEM_MISMATCH",
            "El tipo de análisis no corresponde con el objetivo elegido.",
            "Vuelve a elegir el objetivo y usa la configuración recomendada.",
        ))

    if problem == "exploration":
        return {
            "can_run": not blockers,
            "blockers": blockers,
            "warnings": _profile_warnings(profile),
            "explanation": "La exploración puede ejecutarse sin target ni entrenamiento." if not blockers else "Corrige el objetivo antes de continuar.",
            "suggestions": ["Revisa las alertas del perfil y corrige el archivo original cuando corresponda."],
        }

    if not target or target not in columns or target not in frame:
        blockers.append(_issue(
            "TARGET_NOT_FOUND",
            "No encontramos la columna que quieres analizar en esta versión del archivo.",
            "Vuelve al objetivo y elige una columna disponible.",
        ))
        return _summary(blockers, warnings)

    target_profile = columns[target]
    target_values = frame[target].dropna()
    if len(target_values) < 2:
        blockers.append(_issue(
            "INSUFFICIENT_EVALUABLE_ROWS",
            "Quedan menos de dos filas con resultado conocido; no alcanza para evaluar.",
            "Añade observaciones con target o elige otra columna.",
        ))

    if problem == "regression":
        if target_profile["inferred_semantic_type"] != "numeric":
            blockers.append(_issue(
                "REGRESSION_TARGET_NOT_NUMERIC",
                "Estimar un valor necesita un target numérico; la columna elegida contiene categorías o texto.",
                "Elige una columna numérica o cambia a Predecir una categoría.",
            ))
        elif target_values.nunique(dropna=True) <= 1:
            blockers.append(_issue(
                "CONSTANT_TARGET",
                "El resultado tiene un solo valor y no hay variación que aprender o evaluar.",
                "Usa un target con distintos valores.",
            ))
    elif problem == "classification":
        if target_profile["inferred_semantic_type"] == "numeric":
            blockers.append(_issue(
                "CONTINUOUS_TARGET_FOR_CLASSIFICATION",
                "Predecir una categoría necesita etiquetas; no tratamos automáticamente un número continuo como clases.",
                "Elige una columna categórica o usa Estimar un valor.",
            ))
        counts = target_values.value_counts(dropna=True)
        if len(counts) < 2:
            blockers.append(_issue(
                "SINGLE_CLASS_TARGET",
                "El target solo contiene una categoría y no existe una comparación entre clases.",
                "Añade al menos otra categoría con casos reales.",
            ))
        elif int(counts.min()) < 2:
            blockers.append(_issue(
                "CLASS_SUPPORT_INSUFFICIENT",
                "Una categoría aparece una sola vez y no puede repartirse entre entrenamiento y validación.",
                "Añade más ejemplos reales de esa categoría o elige otro target.",
            ))
        elif int(counts.min()) < 5:
            warnings.append(_issue(
                "LOW_CLASS_SUPPORT",
                "La clase con menos casos tiene soporte limitado; la evaluación será inestable.",
                "Reúne más ejemplos de las clases menos frecuentes antes de tomar decisiones.",
            ))
    elif problem == "forecasting":
        _check_forecast(frame, columns, config, blockers, warnings)

    if problem in {"regression", "classification"} and not _usable_features(columns, config, target):
        warnings.append(_issue(
            "NO_USABLE_FEATURES",
            "No queda ninguna variable seleccionada; solo se evaluará una referencia que no usa variables.",
            "Puedes continuar con la referencia o incluir una variable disponible antes del resultado.",
        ))
    if len(target_values) < 20 and not any(x["code"] == "INSUFFICIENT_EVALUABLE_ROWS" for x in blockers):
        warnings.append(_issue(
            "SMALL_DATASET",
            "Hay pocas observaciones para comprobar si el patrón se repite.",
            "Interpreta el resultado como exploratorio y reúne más observaciones si puedes.",
        ))
    warnings.extend(_profile_warnings(profile))
    return _summary(blockers, warnings)


def _usable_features(columns: dict, config: dict, target: str) -> list[str]:
    configured = config.get("included_column_ids", None)
    included = set(columns) if configured is None else set(configured)
    excluded = set(config.get("excluded_column_ids") or []) | {target}
    return [
        column_id
        for column_id, column in columns.items()
        if column_id in included
        and column_id not in excluded
        and not column.get("possible_id")
        and column.get("distinct_count", 0) > 1
    ]


def _check_forecast(frame, columns, config, blockers, warnings) -> None:
    target = config.get("target_column_id")
    date_column = config.get("date_column_id")
    options = config.get("forecast_options") or {}
    horizon = options.get("horizon")
    if columns[target]["inferred_semantic_type"] != "numeric":
        blockers.append(_issue(
            "FORECAST_TARGET_NOT_NUMERIC",
            "El pronóstico mensual necesita un target numérico.",
            "Elige una cantidad numérica para pronosticar.",
        ))
    if date_column not in columns or date_column not in frame:
        blockers.append(_issue(
            "FORECAST_DATE_NOT_FOUND",
            "No encontramos la columna de fecha seleccionada.",
            "Elige una columna que contenga fechas.",
        ))
        return
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 24:
        blockers.append(_issue(
            "FORECAST_HORIZON_OUT_OF_RANGE",
            "El horizonte debe estar entre 1 y 24 meses.",
            "Elige cuántos meses futuros quieres estimar dentro de ese rango.",
        ))
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    values = pd.to_numeric(frame[target], errors="coerce")
    if dates.isna().any():
        blockers.append(_issue(
            "FORECAST_INVALID_DATE",
            "Algunas fechas no pudieron interpretarse.",
            "Usa fechas reales y consistentes en toda la columna.",
        ))
        return
    if values.isna().any():
        blockers.append(_issue(
            "FORECAST_INVALID_VALUE",
            "El target contiene faltantes o valores no numéricos; V1 no rellena meses ni valores.",
            "Completa o retira esas filas en una copia de tu archivo.",
        ))
    periods = dates.dt.to_period("M")
    if periods.duplicated().any() and options.get("aggregation") not in {"sum", "mean"}:
        blockers.append(_issue(
            "DUPLICATE_MONTHS_REQUIRE_AGGREGATION",
            "Hay varias filas para un mismo mes y no se indicó cómo combinarlas.",
            "Elige sumar o promediar las filas de cada mes.",
        ))
        return
    unique = pd.PeriodIndex(periods.drop_duplicates().sort_values(), freq="M")
    if len(unique):
        expected = pd.period_range(unique[0], unique[-1], freq="M")
        if len(expected.difference(unique)):
            blockers.append(_issue(
                "MISSING_MONTHLY_PERIODS",
                "La serie tiene meses faltantes. Forecasting V1 exige un calendario mensual continuo.",
                "Completa la serie con datos reales o usa Exploración; la app no inventa meses.",
            ))
    if isinstance(horizon, int) and len(unique) < horizon + 2:
        blockers.append(_issue(
            "INSUFFICIENT_HISTORY",
            "No hay suficiente historial para separar un bloque de validación y estimar ese horizonte.",
            "Añade más meses o reduce el horizonte.",
        ))


def _profile_warnings(profile: dict) -> list[dict[str, str]]:
    if not profile.get("duplicate_count"):
        return []
    return [_issue(
        "DEPENDENT_DUPLICATES_REQUIRE_REVIEW",
        "Detectamos filas duplicadas; podrían inflar la evidencia si representan el mismo caso.",
        "Confirma si son observaciones reales independientes y corrige el archivo si son copias.",
    )]


def _summary(blockers: list[dict[str, str]], warnings: list[dict[str, str]]) -> dict:
    suggestions = list(dict.fromkeys(item["suggestion"] for item in [*blockers, *warnings]))
    return {
        "can_run": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "explanation": (
            "La configuración está lista para ejecutar."
            if not blockers
            else "Corrige estos puntos antes de entrenar; todavía no se consumieron recursos de modelado."
        ),
        "suggestions": suggestions,
    }
