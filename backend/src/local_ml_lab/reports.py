import hashlib
import json
from pathlib import Path

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def safe_text(value) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")) and not is_number(text):
        return "'" + text
    return text


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
        ws = workbook.add_worksheet(name)
        ws.freeze_panes(1, 0)
        ws.set_column(0, 12, 22)
    ws = workbook.get_worksheet_by_name("00_Resumen")
    ws.write(0, 0, "Laboratorio ML — Resumen", title)
    rows = [
        ("Objetivo", result.get("goal")),
        ("Tipo", result.get("problem_type")),
        ("Modelo seleccionado", result.get("selection_decision", {}).get("model_id")),
        ("Confiabilidad", result.get("reliability", {}).get("primary_level")),
        ("Versión", result.get("engine_version")),
    ]
    for i, (k, v) in enumerate(rows, 2):
        ws.write(i, 0, k, header)
        ws.write(i, 1, safe_text(v))
    write_table(
        workbook.get_worksheet_by_name("01_Calidad_Data"),
        result.get("data_quality", {}).get("columns", []),
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("04_Modelos_Probados"), result.get("candidates", []), header
    )
    write_table(
        workbook.get_worksheet_by_name("05_Metricas"), result.get("evaluation_metrics", []), header
    )
    write_table(
        workbook.get_worksheet_by_name("06_Predicciones"), result.get("predictions", []), header
    )
    write_table(workbook.get_worksheet_by_name("07_Drivers"), result.get("drivers", []), header)
    write_table(
        workbook.get_worksheet_by_name("09_Advertencias"),
        [{"advertencia": x} for x in result.get("limitations", [])],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("10_Validacion"), [result.get("validation_plan", {})], header
    )
    write_table(
        workbook.get_worksheet_by_name("03_Configuracion"),
        [result.get("resolved_config", {})],
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
        ],
        header,
    )
    workbook.close()


def write_table(ws, rows, header):
    if not rows:
        ws.write(0, 0, "No disponible")
        return
    keys = sorted({k for row in rows for k in row})
    for col, key in enumerate(keys):
        ws.write(0, col, key, header)
    for r, row in enumerate(rows, 1):
        for c, key in enumerate(keys):
            value = row.get(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                ws.write_number(r, c, value)
            else:
                ws.write_string(r, c, safe_text(value))
    ws.autofilter(0, 0, max(1, len(rows)), max(0, len(keys) - 1))


def create_pdf(result: dict, path: Path) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
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
        (
            "Confiabilidad del análisis",
            result.get("reliability", {}).get("primary_level", "No evaluable"),
        ),
        ("Validación", result.get("validation_plan", {}).get("evidence_mode", "No evaluable")),
        ("Modelo seleccionado", result.get("selection_decision", {}).get("model_id", "No aplica")),
    ]:
        story.extend(
            [
                Paragraph(heading, styles["Heading2"]),
                Paragraph(safe_text(content), styles["BodyText"]),
                Spacer(1, 4 * mm),
            ]
        )
    metrics = [["Métrica", "Valor", "Población"]] + [
        [
            m["name"],
            "No disponible" if m["value"] is None else f"{m['value']:.4g}",
            str(m["n_used"]),
        ]
        for m in result.get("evaluation_metrics", [])
    ]
    table = Table(metrics, repeatRows=1, colWidths=[60 * mm, 40 * mm, 40 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F766E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story += [
        Paragraph("Métricas", styles["Heading2"]),
        table,
        PageBreak(),
        Paragraph("Limitaciones y advertencias", styles["Heading2"]),
    ]
    for text in result.get("limitations", ["Sin advertencias adicionales"]):
        story.append(Paragraph("• " + safe_text(text), styles["BodyText"]))
    story += [
        Spacer(1, 6 * mm),
        Paragraph(
            "La importancia predictiva no demuestra necesariamente causalidad.", styles["BodyText"]
        ),
        Paragraph(
            "Este nivel resume cómo se evaluó el resultado. No es una probabilidad de acierto ni demuestra utilidad para una decisión concreta.",
            styles["BodyText"],
        ),
    ]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 10 * mm, "Laboratorio ML · reporte local")
    canvas.drawRightString(192 * mm, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
