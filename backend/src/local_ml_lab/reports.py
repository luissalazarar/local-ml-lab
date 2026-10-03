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

PETROLEUM = "#054D61"
TURQUOISE = "#049990"
LIGHT_GRAY = "#EDEDED"
ORANGE = "#EB5B27"
BLUE = "#0871B8"

PRESENTATION_LABELS = {
    "selection_oof": "Predicción de validación",
    "selection_validation": "Validación de selección",
    "selection_validation_folds": "Particiones de validación",
    "selection_monthly_holdout": "Validación mensual usada para seleccionar",
    "selection_cv": "Validación cruzada usada para seleccionar",
    "history": "Histórico observado",
    "forecast_future": "Pronóstico futuro",
    "target_unit": "Unidades del resultado",
    "score": "Sin unidad",
    "r2": "R²",
    "balanced_accuracy": "Exactitud balanceada",
}


def presentation_label(value):
    if value is None:
        return "No disponible"
    return PRESENTATION_LABELS.get(str(value), str(value))


def selected_model_name(result):
    model_id = result.get("selection_decision", {}).get("model_id")
    return next(
        (
            candidate.get("display_name") or candidate.get("model_id")
            for candidate in result.get("candidates", [])
            if candidate.get("model_id") == model_id
        ),
        model_id or "No aplica",
    )


def release_label(result):
    version = str(result.get("engine_version") or "")
    parts = version.split(".")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        return f"v{int(parts[0])}.{int(parts[1])}.{int(parts[2]):04d}"
    return version or "No disponible"


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
        {"bold": True, "bg_color": PETROLEUM, "font_color": "white", "border": 1}
    )
    title = workbook.add_format({"bold": True, "font_size": 16, "font_color": PETROLEUM})
    sheets = [
        "00_Resumen",
        "01_Calidad_Data",
        "02_Preparacion",
        "03_Configuracion",
        "04_Modelos_Probados",
        "05_Metricas",
        "06_Predicciones",
        "07_Drivers",
        "08_Errores",
        "09_Advertencias",
        "10_Validacion",
        "11_Diccionario",
        "12_Seleccion_Modelo",
        "13_Limites",
        "14_Confirmacion",
        "15_Prueba_Reservada",
        "16_Metricas_Clase",
        "17_Pronostico_Horizonte",
        "18_Escenarios",
    ]
    for name in sheets:
        worksheet = workbook.add_worksheet(name)
        worksheet.freeze_panes(1, 0)
        worksheet.set_column(0, 12, 24)
    summary = workbook.get_worksheet_by_name("00_Resumen")
    summary.write(0, 0, "Laboratorio ML — Resumen", title)
    summary.write(1, 0, "Desarrollado por Luis Salazar")
    rows = [
        ("Objetivo", result.get("goal")),
        ("Tipo", result.get("problem_type")),
        ("Modelo seleccionado", selected_model_name(result)),
        ("Métrica principal", presentation_label(result.get("primary_metric_id"))),
        ("Confiabilidad", result.get("reliability", {}).get("primary_level")),
        ("Significado", "Solidez de la evaluación; no es una probabilidad de acierto."),
        ("Escenarios interactivos", scenario_summary_text(result)),
        ("Versión de Laboratorio ML", release_label(result)),
    ]
    for index, (key, value) in enumerate(rows, 3):
        summary.write(index, 0, key, header)
        summary.write(index, 1, safe_text(value))
    quality = result.get("data_quality", {}).get("columns", [])
    write_table(workbook.get_worksheet_by_name("01_Calidad_Data"), quality, header)
    write_table(workbook.get_worksheet_by_name("02_Preparacion"), preparation_rows(result), header)
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
        dictionary_rows(result),
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("12_Seleccion_Modelo"),
        [result.get("selection_decision", {})],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("13_Limites"),
        [{"limite": value} for value in result.get("limitations", [])],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("14_Confirmacion"),
        [result.get("confirmation", {})],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("15_Prueba_Reservada"),
        [result.get("final_test", {})] if result.get("final_test") else [],
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("16_Metricas_Clase"),
        result.get("diagnostics", {}).get("per_class", []),
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("17_Pronostico_Horizonte"),
        result.get("forecast", {}).get("horizon_diagnostics", []),
        header,
    )
    write_table(
        workbook.get_worksheet_by_name("18_Escenarios"),
        scenario_rows(result),
        header,
    )
    workbook.close()


def dictionary_rows(result):
    definitions = {
        "Confiabilidad": "Solidez de la evaluación; no es probabilidad de acierto.",
        "MAE": "Error absoluto promedio, en la misma unidad del resultado; más bajo es mejor.",
        "RMSE": "Error que penaliza más los errores grandes; más bajo es mejor.",
        "R²": "No es porcentaje; 1 es ajuste perfecto, cerca de 0 no mejora la referencia del promedio y puede ser negativo.",
        "Exactitud": "Proporción total de aciertos; puede engañar si una clase domina.",
        "Exactitud balanceada": "Promedia el acierto de cada clase; más alto es mejor.",
        "F1 macro": "Calcula F1 por clase y les da el mismo peso; más alto es mejor.",
        "Soporte": "Cantidad de casos reales de cada categoría.",
        "Matriz de confusión": "Fila es real, columna es predicho y la diagonal contiene aciertos.",
        "Error": "Predicho menos real.",
        "Importancia predictiva": "Cambio de la métrica al alterar una variable fuera del entrenamiento; no demuestra causalidad.",
        "Validación": "Datos apartados de cada ajuste; aquí también participan en la selección.",
        "Pronóstico futuro": "Meses todavía sin valor real disponible; V1 no incluye intervalos.",
        "Original": "El archivo tal como se subió; la preparación no lo modifica.",
        "Preparado": "Tipos y representaciones confirmadas antes de elegir el objetivo.",
        "Análisis": "Decisiones que dependen del resultado elegido, como filas disponibles y agregación mensual.",
        "Entrenamiento": "Transformaciones y patrones aprendidos usando solo la parte de entrenamiento.",
    }
    terms = {"Confiabilidad", "Validación"}
    if result.get("data_preparation"):
        terms.update({"Original", "Preparado", "Análisis", "Entrenamiento"})
    metric_terms = {
        "mae": "MAE",
        "rmse": "RMSE",
        "r2": "R²",
        "accuracy": "Exactitud",
        "balanced_accuracy": "Exactitud balanceada",
        "macro_f1": "F1 macro",
    }
    terms.update(
        metric_terms.get(row.get("metric_id"), "") for row in result.get("evaluation_metrics", [])
    )
    if result.get("predictions"):
        terms.add("Error")
    if result.get("drivers"):
        terms.add("Importancia predictiva")
    if result.get("problem_type") == "classification":
        terms.update({"Soporte", "Matriz de confusión"})
    if result.get("problem_type") == "forecasting":
        terms.add("Pronóstico futuro")
    return [
        {"termino": term, "definicion": definitions[term]} for term in definitions if term in terms
    ]


def preparation_rows(result):
    preparation = result.get("data_preparation", {})
    rows = []
    for item in preparation.get("transformations", []):
        rows.append(
            {
                "version": preparation.get("dataset_version_id"),
                "columna": item.get("column_id"),
                "transformacion": item.get("transformation"),
                "valores_afectados": item.get("affected_count"),
                "filas_iniciales": preparation.get("rows_input"),
                "filas_analizadas": preparation.get("rows_analyzed"),
                "filas_apartadas": preparation.get("rows_quarantined"),
            }
        )
    if preparation.get("target_missing_rows"):
        rows.append(
            {
                "version": preparation.get("dataset_version_id"),
                "transformacion": "Apartar filas sin resultado para este objetivo",
                "valores_afectados": preparation["target_missing_rows"],
            }
        )
    if rows:
        return rows
    columns = result.get("data_quality", {}).get("columns", [])
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


def scenario_summary_text(result):
    scenario = result.get("scenario_explorer", {})
    if scenario.get("available"):
        return (
            f"Disponible con {scenario.get('model_name', 'el modelo seleccionado')}; "
            "es una proyección acotada, no una evaluación ni evidencia causal."
        )
    return "No disponible para esta corrida."


def scenario_rows(result):
    scenario = result.get("scenario_explorer", {})
    if not scenario.get("available"):
        return [{"estado": "No disponible", "motivo": scenario.get("reason_code", "No aplica")}]
    return [
        {
            "estado": "Disponible",
            "modelo": scenario.get("model_name"),
            "variable": control.get("display_name"),
            "tipo": control.get("kind"),
            "valor_representativo": control.get("default"),
            "minimo_observado": control.get("minimum"),
            "maximo_observado": control.get("maximum"),
            "categorias_disponibles": control.get("options"),
            "importancia_predictiva": control.get("importance_mean"),
            "nota": "Proyección acotada; no es evaluación ni evidencia causal.",
        }
        for control in scenario.get("controls", [])
    ]


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
    if not rows or not any(row for row in rows):
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
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].textColor = colors.HexColor(PETROLEUM)
    styles["Heading2"].fontName = "Helvetica-Bold"
    styles["Heading2"].textColor = colors.HexColor(PETROLEUM)
    styles["BodyText"].fontName = "Helvetica"
    styles["BodyText"].fontSize = 10
    styles["BodyText"].leading = 15
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
        Paragraph("Desarrollado por Luis Salazar", styles["BodyText"]),
        Paragraph(release_label(result), styles["BodyText"]),
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
        (
            "Qué significa",
            "Describe la solidez de la evaluación; no es una probabilidad de acierto.",
        ),
        ("Validación", presentation_label(result.get("validation_plan", {}).get("evidence_mode"))),
        ("Modelo seleccionado", selected_model_name(result)),
        ("Métrica principal", presentation_label(result.get("primary_metric_id"))),
        (
            "Preparación de datos",
            preparation_summary_text(result.get("data_preparation", {})),
        ),
    ]:
        story.extend(
            [
                Paragraph(heading, styles["Heading2"]),
                Paragraph(paragraph_text(content), styles["BodyText"]),
                Spacer(1, 4 * mm),
            ]
        )
    story += [
        Paragraph("Cómo se eligió el modelo", styles["Heading2"]),
        Paragraph(
            paragraph_text(
                result.get("selection_decision", {}).get(
                    "reason",
                    "No hubo una selección predictiva aplicable.",
                )
            ),
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Cómo se evaluó", styles["Heading2"]),
        Paragraph(
            paragraph_text(
                f"{presentation_label(result.get('validation_plan', {}).get('strategy'))}. "
                "Las transformaciones se ajustaron dentro de cada entrenamiento y los candidatos comparables usaron las mismas observaciones."
            ),
            styles["BodyText"],
        ),
        Spacer(1, 4 * mm),
        Paragraph("Comprobación adicional", styles["Heading2"]),
        Paragraph(paragraph_text(confirmation_text(result)), styles["BodyText"]),
        Spacer(1, 4 * mm),
        Paragraph("Prueba reservada", styles["Heading2"]),
        Paragraph(paragraph_text(holdout_text(result)), styles["BodyText"]),
        Spacer(1, 4 * mm),
        Paragraph("Qué significan los límites", styles["Heading2"]),
        Paragraph(
            "Acotan qué puede concluirse. Los umbrales de selección son decisiones del producto y no pruebas de significancia estadística.",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Cómo leer este resultado", styles["Heading2"]),
        Paragraph(paragraph_text(report_reading_help(result)), styles["BodyText"]),
        Spacer(1, 4 * mm),
    ]
    metrics = [["Métrica", "Valor", "Población", "Rol"]] + [
        [
            presentation_label(metric.get("metric_id"))
            if metric.get("metric_id") == "r2"
            else metric["name"],
            "No disponible" if metric["value"] is None else f"{metric['value']:.4g}",
            str(metric["n_used"]),
            presentation_label(metric.get("evaluation_role", "")),
        ]
        for metric in result.get("evaluation_metrics", [])
    ]
    story += [Paragraph("Métricas", styles["Heading2"]), styled_table(metrics)]
    horizon_rows = result.get("forecast", {}).get("horizon_diagnostics", [])
    if horizon_rows:
        rows = [["Mes", "MAE modelo", "MAE referencia", "Diferencia"]] + [
            [
                f"+{item['horizon']}",
                f"{item['selected_mae']:.4g}",
                f"{item['baseline_mae']:.4g}",
                f"{item['mae_difference']:.4g}",
            ]
            for item in horizon_rows
        ]
        story += [
            Spacer(1, 4 * mm),
            Paragraph("Error histórico por distancia al futuro", styles["Heading2"]),
            styled_table(rows),
        ]
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
                presentation_label(driver.get("evaluation_role", "")),
            ]
            for driver in drivers
        ]
        story += [
            Spacer(1, 6 * mm),
            Paragraph("Variables predictivas", styles["Heading2"]),
            styled_table(driver_rows),
        ]
    scenario = result.get("scenario_explorer", {})
    if scenario.get("available"):
        story += [
            Spacer(1, 6 * mm),
            Paragraph("Escenarios interactivos", styles["Heading2"]),
            Paragraph(
                paragraph_text(
                    f"La app guardó un reajuste local de {scenario.get('model_name', 'el modelo seleccionado')} "
                    f"con {scenario.get('fit_row_count', 0)} filas para probar valores dentro de los rangos observados. "
                    "Estas proyecciones no reevalúan la corrida, no demuestran causalidad y no garantizan resultados futuros."
                ),
                styles["BodyText"],
            ),
        ]
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


def preparation_summary_text(preparation):
    if not preparation:
        return "Se usó la versión original sin una receta de preparación adicional."
    return (
        f"Versión {preparation.get('dataset_version_id', 'no disponible')}; "
        f"{len(preparation.get('transformations', []))} transformaciones; "
        f"{preparation.get('rows_input', 0)} filas iniciales; "
        f"{preparation.get('rows_analyzed', 0)} filas analizadas; "
        f"{preparation.get('rows_quarantined', 0)} filas apartadas. "
        "Original: archivo sin cambios. Preparado: representaciones confirmadas. "
        "Análisis: decisiones ligadas al objetivo. Entrenamiento: aprendizaje limitado a sus datos de entrenamiento."
    )


def confirmation_text(result):
    confirmation = result.get("confirmation", {})
    status = confirmation.get("status", "not_run")
    if status == "confirmed":
        return "La mejora volvió a aparecer con suficiente consistencia en una segunda separación reproducible."
    if status == "not_confirmed":
        return "La mejora no volvió a aparecer con suficiente consistencia; se conservó la referencia."
    return "No se ejecutó porque no aplicaba o no había soporte suficiente; no se redujeron los requisitos."


def holdout_text(result):
    final_test = result.get("final_test")
    if not final_test:
        return "No se reservó una prueba final porque separar más datos habría dejado demasiado poco soporte."
    if final_test.get("selection_improvement_repeated"):
        return "La mejora volvió a aparecer en datos que no participaron en elegir el modelo."
    return "La mejora observada durante selección no se repitió en la prueba reservada; el ganador no se cambió después de verla."


def styled_table(rows):
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PETROLEUM)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(LIGHT_GRAY)),
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
        points = [
            row
            for row in predictions
            if row.get("actual") is not None and row.get("predicted") is not None
        ]
        if not points:
            plt.close(figure)
            return None
        actual = [row["actual"] for row in points]
        predicted = [row["predicted"] for row in points]
        axis.scatter(actual, predicted, alpha=0.75, color=TURQUOISE, edgecolor=PETROLEUM)
        low, high = min(actual + predicted), max(actual + predicted)
        margin = (high - low or max(abs(low), 1)) * 0.08
        axis.plot(
            [low - margin, high + margin], [low - margin, high + margin], "--", color="#64748B"
        )
        axis.set_xlim(low - margin, high + margin)
        axis.set_ylim(low - margin, high + margin)
        axis.grid(alpha=0.2)
        axis.set(
            xlabel="Real · unidades del resultado",
            ylabel="Predicho · unidades del resultado",
            title="Valores reales y predichos · validación",
        )
    elif problem == "classification":
        matrix = result.get("diagnostics", {}).get("confusion_matrix")
        labels = result.get("diagnostics", {}).get("class_labels", [])
        if not matrix:
            plt.close(figure)
            return None
        image = axis.imshow(matrix, cmap="GnBu")
        figure.colorbar(image, ax=axis)
        axis.set_xticks(range(len(labels)), labels, rotation=30, ha="right")
        axis.set_yticks(range(len(labels)), labels)
        axis.set(xlabel="Predicho", ylabel="Real", title="Matriz de confusión · validación")
        for row, values in enumerate(matrix):
            for column, value in enumerate(values):
                axis.text(column, row, str(value), ha="center", va="center")
    elif problem == "forecasting":
        history = [row for row in predictions if row.get("evaluation_role") == "history"]
        future = [row for row in predictions if row.get("evaluation_role") == "forecast_future"]
        if not history or not future:
            plt.close(figure)
            return None
        final_test = [
            row for row in predictions if row.get("evaluation_role") == "final_test"
        ]
        selection = [
            row for row in predictions if row.get("evaluation_role") == "selection_backtest"
        ]
        if final_test:
            validation = final_test
            validation_label = "Prueba reservada"
        else:
            last_unit = selection[-1].get("unit_id") if selection else None
            validation = [row for row in selection if row.get("unit_id") == last_unit]
            validation_label = "Última prueba de selección"
        axis.plot(
            [row["target_period"] for row in history],
            [row["actual"] for row in history],
            label="Histórico observado",
            color=TURQUOISE,
        )
        if validation:
            axis.plot(
                [row["target_period"] for row in validation],
                [row["predicted"] for row in validation],
                label=validation_label,
                color=BLUE,
                linestyle="--",
            )
        axis.plot(
            [history[-1]["target_period"]] + [row["target_period"] for row in future],
            [history[-1]["actual"]] + [row["predicted"] for row in future],
            label="Pronóstico futuro",
            color=ORANGE,
            linestyle="--",
            marker="o",
        )
        axis.axvline(history[-1]["target_period"], color=ORANGE, linestyle=":", alpha=0.7)
        axis.tick_params(axis="x", labelrotation=45)
        axis.legend()
        axis.grid(axis="y", alpha=0.2)
        axis.set(
            title="Histórico, bloque fuera de muestra y pronóstico mensual", ylabel="Unidades del resultado"
        )
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
    canvas.drawString(18 * mm, 10 * mm, "Laboratorio ML · Desarrollado por Luis Salazar")
    canvas.drawRightString(192 * mm, 10 * mm, f"Página {document.page}")
    canvas.restoreState()


def report_reading_help(result):
    metric = presentation_label(result.get("primary_metric_id"))
    problem = result.get("problem_type")
    direction = (
        "más bajo es mejor"
        if result.get("primary_metric_id") in {"mae", "rmse"}
        else "más alto es mejor"
    )
    if problem == "classification":
        extra = " En la matriz, fila es real, columna es predicho y soporte es la cantidad de casos reales."
    elif problem == "regression":
        extra = " El error es predicho menos real."
    elif problem == "forecasting":
        extra = " El futuro aún no tiene valor real y V1 no muestra intervalos."
    else:
        extra = " La exploración no produce métricas predictivas."
    return f"La métrica usada es {metric}: {direction}. Confiabilidad describe la evaluación, no una probabilidad. La referencia muestra si el modelo aportó frente a una regla sencilla.{extra}"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
