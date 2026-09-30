import hashlib
import json
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402


def safe_text(value) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")) and not is_number(text):
        return "'" + text
    return text


def paragraph_text(value) -> str:
    return escape(safe_text(value))


def is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def create_excel(result: dict, path: Path) -> None:
    workbook = xlsxwriter.Workbook(
        path, {"constant_memory": True, "strings_to_formulas": False, "strings_to_urls": False}
    )
    header = workbook.add_format(
        {"bold": True, "bg_color": "#0F766E", "font_color": "white", "border": 1}
    )
    title = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#115E59"})
    sheets = [
        "00_Resumen",
        "01_Calidad_Data",
        "02_Limpieza",
        "03_Configuracion",
        "04_Modelos_Probados",
        "05_Metricas",
        "06_Predicciones",
        "07_Drivers",
        "08_Errores",
        "09_Advertencias",
        "10_Validacion",
        "11_Diccionario",
    ]
    for name in sheets:
        worksheet = workbook.add_worksheet(name)
        worksheet.freeze_panes(1, 0)
        worksheet.set_column(0, 12, 24)
    summary = workbook.get_worksheet_by_name("00_Resumen")
    summary.write(0, 0, "Laboratorio ML — Resumen", title)
    rows = [
        ("Objetivo", result.get("goal")),
        ("Tipo", result.get("problem_type")),
        ("Modelo seleccionado", result.get("selection_decision", {}).get("model_id")),
        ("Métrica principal", result.get("primary_metric_id")),
        ("Confiabilidad", result.get("reliability", {}).get("primary_level")),
        ("Versión", result.get("engine_version")),
    ]
    for index, (key, value) in enumerate(rows, 2):
        summary.write(index, 0, key, header)
        summary.write(index, 1, safe_text(value))
    quality = result.get("data_quality", {}).get("columns", [])
    write_table(workbook.get_worksheet_by_name("01_Calidad_Data"), quality, header)
    write_table(
        workbook.get_worksheet_by_name("02_Limpieza"), cleaning_rows(quality), header
    )
    write_table(
        workbook.get_worksheet_by_name("03_Configuracion"),
        [result.get("resolved_config", {})],
        header,
    )
    candidates = result.get("candidates", [])
    write_table(workbook.get_worksheet_by_name("04_Modelos_Probados"), candidates, header)
    write_table(
        workbook.get_worksheet_by_name("05_Metricas"), result.get("evaluation_metrics", []), header
    )
    write_table(
        workbook.get_worksheet_by_name("06_Predicciones"), result.get("predictions", []), header
    )
    write_table(workbook.get_worksheet_by_name("07_Drivers"), result.get("drivers", []), header)
    write_table(
        workbook.get_worksheet_by_name("08_Errores"), candidate_error_rows(candidates), header
    )
    write_table(
        workbook.get_worksheet_by_name("09_Advertencias"),
        [{"advertencia": limitation} for limitation in result.get("limitations", [])]
        or [{"advertencia": "No se registraron advertencias adicionales."}],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("10_Validacion"),
        [result.get("validation_plan", {})],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("11_Diccionario"),
        [
            {
                "termino": "Confiabilidad",
                "definicion": "Solidez de la evaluación; no es probabilidad de acierto.",
            },
            {"termino": "R²", "definicion": "No es porcentaje de acierto y puede ser negativo."},
            {
                "termino": "selection_oof",
                "definicion": "Predicción fuera del train del fold, también usada para seleccionar.",
            },
        ],
        header,
    )
    workbook.close()


def cleaning_rows(columns):
    rows = []
    for column in columns:
        actions = []
        if column.get("null_count"):
            actions.append("Imputación ajustada solo con train dentro de cada fold")
        if column.get("possible_id"):
            actions.append("Exclusión preventiva como posible identificador")
        if not actions:
            actions.append("Sin modificación directa; se conservó el valor original")
        rows.append(
            {
                "column_id": column.get("column_id"),
                "display_name": column.get("display_name"),
                "accion": "; ".join(actions),
                "nota": "El archivo canónico no reemplaza valores con estadísticas aprendidas.",
            }
        )
    return rows or [{"accion": "No hubo columnas para documentar."}]


def candidate_error_rows(candidates):
    errors = [
        {
            "model_id": candidate.get("model_id"),
            "status": candidate.get("status"),
            "reason_code": candidate.get("reason_code"),
        }
        for candidate in candidates
        if candidate.get("status") == "failed"
    ]
    return errors or [{"status": "Sin errores", "detalle": "Ningún candidato registró un fallo."}]


def write_table(worksheet, rows, header):
    if not rows:
        worksheet.write(0, 0, "No disponible: esta sección no aplica al análisis.")
        return
    keys = sorted({key for row in rows for key in row})
    for column, key in enumerate(keys):
        worksheet.write(0, column, key, header)
    for row_index, row in enumerate(rows, 1):
        for column_index, key in enumerate(keys):
            value = row.get(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                worksheet.write_number(row_index, column_index, value)
            else:
                worksheet.write_string(row_index, column_index, safe_text(value))
    worksheet.autofilter(0, 0, max(1, len(rows)), max(0, len(keys) - 1))


def create_pdf(result: dict, path: Path) -> None:
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Reporte Laboratorio ML",
    )
    story = [
        Paragraph("Laboratorio ML", styles["Title"]),
        Paragraph("Reporte de análisis local", styles["Heading2"]),
        Spacer(1, 8 * mm),
    ]
    for heading, content in [
        ("Objetivo", result.get("goal")),
        (
            "Resumen de datos",
            f"{result.get('dataset_summary', {}).get('row_count', 0)} filas · {result.get('dataset_summary', {}).get('column_count', 0)} columnas",
        ),
        ("Confiabilidad", result.get("reliability", {}).get("primary_level", "No evaluable")),
        ("Validación", result.get("validation_plan", {}).get("evidence_mode", "No evaluable")),
        ("Modelo seleccionado", result.get("selection_decision", {}).get("model_id", "No aplica")),
        ("Métrica principal", result.get("primary_metric_id", "No aplica")),
    ]:
        story.extend(
            [
                Paragraph(heading, styles["Heading2"]),
                Paragraph(paragraph_text(content), styles["BodyText"]),
                Spacer(1, 4 * mm),
            ]
        )
    metrics = [["Métrica", "Valor", "Población", "Rol"]] + [
        [
            metric["name"],
            "No disponible" if metric["value"] is None else f"{metric['value']:.4g}",
            str(metric["n_used"]),
            metric.get("evaluation_role", ""),
        ]
        for metric in result.get("evaluation_metrics", [])
    ]
    story += [Paragraph("Métricas", styles["Heading2"]), styled_table(metrics)]
    chart = result_chart(result)
    if chart:
        story += [Spacer(1, 6 * mm), Paragraph("Resultado visual", styles["Heading2"]), chart]
    drivers = result.get("drivers", [])[:10]
    if drivers:
        names = column_names(result)
        driver_rows = [["Variable", "Importancia", "Rol"]] + [
            [
                names.get(driver.get("source_column_id"), driver.get("source_column_id")),
                f"{driver.get('importance_mean', 0):.4g}",
                driver.get("evaluation_role", ""),
            ]
            for driver in drivers
        ]
        story += [Spacer(1, 6 * mm), Paragraph("Variables predictivas", styles["Heading2"]), styled_table(driver_rows)]
    story += [PageBreak(), Paragraph("Limitaciones y advertencias", styles["Heading2"])]
    for text in result.get("limitations", []) or ["Sin advertencias adicionales"]:
        story.append(Paragraph("• " + paragraph_text(text), styles["BodyText"]))
    story += [
        Spacer(1, 6 * mm),
        Paragraph(
            "La importancia predictiva no demuestra causalidad. La validación usada para seleccionar no constituye una prueba final independiente.",
            styles["BodyText"],
        ),
    ]
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def styled_table(rows):
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def result_chart(result):
    predictions = result.get("predictions", [])
    problem = result.get("problem_type")
    figure, axis = plt.subplots(figsize=(7.2, 3.6), dpi=120)
    if problem == "regression":
        points = [row for row in predictions if row.get("actual") is not None and row.get("predicted") is not None]
        if not points:
            plt.close(figure)
            return None
        actual = [row["actual"] for row in points]
        predicted = [row["predicted"] for row in points]
        axis.scatter(actual, predicted, alpha=0.7, color="#0F766E")
        low, high = min(actual + predicted), max(actual + predicted)
        axis.plot([low, high], [low, high], "--", color="#64748B")
        axis.set(xlabel="Real", ylabel="Predicho", title="Real frente a predicho · fuera de train")
    elif problem == "classification":
        matrix = result.get("diagnostics", {}).get("confusion_matrix")
        labels = result.get("diagnostics", {}).get("class_labels", [])
        if not matrix:
            plt.close(figure)
            return None
        image = axis.imshow(matrix, cmap="BuGn")
        figure.colorbar(image, ax=axis)
        axis.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
        axis.set_yticks(range(len(labels)), labels)
        axis.set(xlabel="Predicho", ylabel="Real", title="Matriz de confusión · fuera de train")
        for row, values in enumerate(matrix):
            for column, value in enumerate(values):
                axis.text(column, row, str(value), ha="center", va="center")
    elif problem == "forecasting":
        history = [row for row in predictions if row.get("evaluation_role") == "history"]
        future = [row for row in predictions if row.get("evaluation_role") == "forecast_future"]
        if not history or not future:
            plt.close(figure)
            return None
        axis.plot([row["target_period"] for row in history], [row["actual"] for row in history], label="Historia", color="#0F766E")
        axis.plot([row["target_period"] for row in future], [row["predicted"] for row in future], label="Pronóstico futuro", color="#EA580C", marker="o")
        axis.tick_params(axis="x", labelrotation=45)
        axis.legend()
        axis.set(title="Historia y pronóstico mensual futuro", ylabel="Unidad del objetivo")
    else:
        plt.close(figure)
        return None
    figure.tight_layout()
    buffer = BytesIO()
    figure.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(figure)
    buffer.seek(0)
    image = Image(buffer, width=165 * mm, height=82 * mm)
    image._source_buffer = buffer
    return image


def column_names(result):
    return {
        column["column_id"]: column["display_name"]
        for column in result.get("data_quality", {}).get("columns", [])
    }


def footer(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 10 * mm, "Laboratorio ML · reporte local")
    canvas.drawRightString(192 * mm, 10 * mm, f"Página {document.page}")
    canvas.restoreState()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
