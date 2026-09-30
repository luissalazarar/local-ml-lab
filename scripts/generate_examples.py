from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "examples"


def main():
    dirty = pd.DataFrame(
        {
            "codigo": ["001", "002", "003", "003"],
            "monto": ["1.234,50", "2.100,00", None, "999.999,00"],
            "porcentaje": ["15%", "20%", "0.15", "15%"],
            "categoria": ["Norte", " Sur ", "NA", "Norte"],
        }
    )
    with pd.ExcelWriter(ROOT / "dirty_data.xlsx", engine="xlsxwriter") as writer:
        dirty.to_excel(writer, sheet_name="Datos", index=False)
        pd.DataFrame({"nota": ["Hoja auxiliar sintética"]}).to_excel(writer, sheet_name="Auxiliar", index=False)
        writer.sheets["Datos"].write_formula(5, 1, "=SUM(1,2)")
    pd.DataFrame({"id": ["P001", "P002", "P003"], "valor": [10.5, 12.0, 11.2], "grupo": ["A", "B", "A"]}).to_parquet(ROOT / "tabular.parquet", index=False)


if __name__ == "__main__": main()

