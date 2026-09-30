"""Regenera todos los ejemplos públicos con una semilla fija."""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "examples"
SEED = 42
CREATED = datetime(2026, 9, 30, tzinfo=UTC)


def write_workbook(path: Path, data: pd.DataFrame, guide: list[tuple[str, str]]) -> None:
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        writer.book.set_properties(
            {
                "title": path.stem.replace("_", " ").title(),
                "author": "Laboratorio ML",
                "comments": "Ejemplo sintético reproducible; no representa personas reales.",
                "created": CREATED,
            }
        )
        data.to_excel(writer, sheet_name="Datos", index=False)
        pd.DataFrame(guide, columns=["Tema", "Explicación"]).to_excel(
            writer, sheet_name="Guía", index=False
        )
        for sheet in writer.sheets.values():
            sheet.freeze_panes(1, 0)
            sheet.set_column(0, max(1, len(data.columns) - 1), 20)


def write_reader_cases(path: Path) -> None:
    rows = 24
    data = pd.DataFrame(
        {
            "Caso_ID": [f"CASE-{index:03d}" for index in range(1, rows + 1)],
            "Cantidad": [None if index == 4 else index * 2.5 for index in range(rows)],
            "Categoría": ["A", "B", "C"] * 8,
            "Fecha": pd.date_range("2024-01-01", periods=rows, freq="MS"),
            "Resultado": [80 + index * 3 for index in range(rows)],
        }
    )
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        writer.book.set_properties({"title": "Casos de lectura Excel", "author": "Laboratorio ML", "created": CREATED})
        data.to_excel(writer, sheet_name="Datos", index=False, startrow=2)
        sheet = writer.sheets["Datos"]
        sheet.write(0, 0, "Ejemplo con filas introductorias")
        sheet.write(1, 0, "La tabla comienza en la fila 3")
        pd.DataFrame({"Nota": ["Hoja auxiliar; no es la tabla analizable."]}).to_excel(writer, sheet_name="Auxiliar", index=False)


def regression(rng: np.random.Generator) -> pd.DataFrame:
    rows = 160
    age = rng.integers(20, 66, rows)
    income = np.clip(rng.normal(3_800, 1_250, rows), 1_100, 8_500)
    tenure = rng.integers(1, 85, rows)
    channel = rng.choice(["Tienda", "Web", "Teléfono"], rows, p=[0.5, 0.35, 0.15])
    channel_effect = pd.Series(channel).map({"Tienda": 140, "Web": 30, "Teléfono": -60}).to_numpy()
    spend = 180 + income * 0.16 + tenure * 3.1 + (age - 40) * 2.2 + channel_effect
    spend += rng.normal(0, 155, rows)
    frame = pd.DataFrame(
        {
            "Cliente_ID": [f"CLI-{index:04d}" for index in range(1, rows + 1)],
            "Edad": age,
            "Ingreso_mensual": income.round(2),
            "Canal_preferido": channel,
            "Antigüedad_meses": tenure,
            "Gasto_mensual": np.clip(spend, 80, None).round(2),
        }
    )
    frame.loc[rng.choice(rows, 8, replace=False), "Ingreso_mensual"] = np.nan
    frame.loc[rng.choice(rows, 6, replace=False), "Canal_preferido"] = None
    return frame


def classification(rng: np.random.Generator) -> pd.DataFrame:
    rows = 210
    income = np.clip(rng.normal(4_000, 1_500, rows), 900, 10_000)
    debt = np.clip(rng.beta(2.2, 4.5, rows), 0.02, 0.95)
    tenure = rng.integers(1, 97, rows)
    channel = rng.choice(["Oficina", "Web", "Aliado"], rows, p=[0.45, 0.4, 0.15])
    region = rng.choice(["Lima", "Norte", "Centro", "Sur"], rows)
    logit = -0.65 + (income - 3_500) / 1_700 - debt * 2.2 + tenure / 100
    logit += np.where(channel == "Web", 0.25, 0) + rng.normal(0, 0.85, rows)
    probability = 1 / (1 + np.exp(-logit))
    outcome = np.where(rng.random(rows) < probability, "Aprobado", "Revisar")
    frame = pd.DataFrame(
        {
            "Solicitud_ID": [f"SOL-{index:04d}" for index in range(1, rows + 1)],
            "Ingreso_mensual": income.round(2),
            "Ratio_deuda": debt.round(3),
            "Antigüedad_meses": tenure,
            "Canal": channel,
            "Región": region,
            "Resultado": outcome,
        }
    )
    frame.loc[rng.choice(rows, 7, replace=False), "Ingreso_mensual"] = np.nan
    return frame


def forecast(rng: np.random.Generator) -> pd.DataFrame:
    periods = pd.date_range("2021-01-01", periods=60, freq="MS")
    index = np.arange(len(periods))
    values = 850 + index * 11 + 115 * np.sin(2 * np.pi * index / 12) + rng.normal(0, 34, len(index))
    return pd.DataFrame({"Mes": periods, "Ventas": values.round(2)})


def exploration() -> pd.DataFrame:
    rows = [
        ["REG-001", "Lima", 120.0, "2026-01-03", "Activo", "misma"],
        ["REG-002", "lima", None, "2026-01-04", "Activo", "misma"],
        ["REG-003", "Norte", 95.5, "2026-01-05", "Pausado", "misma"],
        ["REG-003", "Norte", 95.5, "2026-01-05", "Pausado", "misma"],
        ["REG-005", "Sur ", 140.0, None, "Activo", "misma"],
        ["REG-006", None, 110.0, "2026-01-07", "Activo", "misma"],
    ]
    return pd.DataFrame(rows, columns=["Registro_ID", "Zona", "Monto", "Fecha", "Estado", "Constante"])


def preparation_example(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    zones = [" Norte ", "Sur", "Centro", "Lima"]
    for index in range(1, 49):
        amount = 900 + index * 17.35
        rows.append(
            {
                "Operación ID": f"OP-{index:04d}",
                "Fecha venta": f"{(index % 27) + 1:02d}/{(index % 12) + 1:02d}/2026",
                "Monto texto": f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "Zona": zones[index % len(zones)],
                "Visitas": int(rng.integers(1, 12)),
                "Ventas": round(amount * 0.42 + rng.normal(0, 35), 2),
            }
        )
    rows[6]["Fecha venta"] = "fecha pendiente"
    rows[11]["Monto texto"] = "sin dato"
    rows[18]["Zona"] = ""
    rows.append(dict(rows[20]))
    return pd.DataFrame(rows)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    rng = np.random.default_rng(SEED)
    regression_data = regression(rng)
    classification_data = classification(rng)
    forecast_data = forecast(rng)
    exploration_data = exploration()
    preparation_data = preparation_example(rng)

    write_workbook(ROOT / "regression.xlsx", regression_data, [
        ("Objetivo", "Estimar un valor numérico con señal realista e imperfecta."),
        ("Target sugerido", "Gasto_mensual"),
        ("Qué aprenderás", "MAE, referencias, modelos y variables predictivamente útiles."),
        ("Privacidad", "Todos los registros son sintéticos."),
    ])
    write_workbook(ROOT / "classification.xlsx", classification_data, [
        ("Objetivo", "Predecir una categoría con dos clases y desbalance moderado."),
        ("Target sugerido", "Resultado"),
        ("Qué aprenderás", "Exactitud, exactitud balanceada, F1 macro y matriz de confusión."),
        ("Privacidad", "Todos los registros son sintéticos."),
    ])
    write_workbook(ROOT / "forecast_monthly.xlsx", forecast_data, [
        ("Objetivo", "Estimar próximos meses de una serie mensual continua."),
        ("Fecha", "Mes"),
        ("Target sugerido", "Ventas"),
        ("Qué aprenderás", "Histórico, validación mensual, referencia estacional y futuro."),
    ])
    write_workbook(ROOT / "exploration.xlsx", exploration_data, [
        ("Objetivo", "Explorar calidad sin entrenar un modelo."),
        ("Qué contiene", "Faltantes, duplicado, ID, constante, categorías, números y fechas."),
        ("Qué aprenderás", "Cómo leer el perfil y decidir qué corregir en el archivo original."),
    ])
    write_workbook(ROOT / "preparation.xlsx", preparation_data, [
        ("Objetivo", "Preparar un Excel típico antes de estimar Ventas."),
        ("Qué contiene", "Fecha DMY como texto, monto con coma decimal, ID, espacios, faltantes y un duplicado exacto."),
        ("Decisiones", "Confirma formatos, revisa antes/después y decide qué filas segregar."),
        ("Privacidad", "Todos los registros son sintéticos."),
    ])

    regression_data.to_csv(ROOT / "regression.csv", index=False)
    classification_data.to_csv(ROOT / "classification.csv", index=False)
    forecast_data.to_csv(ROOT / "forecast_monthly.csv", index=False)
    write_workbook(
        ROOT / "dirty_data.xlsx",
        exploration_data,
        [("Uso", "Workbook auxiliar para pruebas de formato y perfilado.")],
    )
    write_reader_cases(ROOT / "excel_reader_cases.xlsx")
    regression_data.head(40).to_parquet(ROOT / "tabular.parquet", index=False)


if __name__ == "__main__":
    main()
