import pandas as pd
import pytest

from local_ml_lab.data.readers import inspect_file, normalize_columns, profile_frame, read_frame


def test_duplicate_headers_keep_distinct_ids():
    frame = pd.DataFrame([[1, 2]], columns=["valor", "valor"])
    normalized, mapping = normalize_columns(frame)
    assert list(normalized.columns) == ["c0001", "c0002"]
    assert mapping[1]["display_name"] == "valor (2)"


def test_continuous_numeric_not_id_when_small():
    frame, mapping = normalize_columns(pd.DataFrame({"valor": [1.1, 2.2, 3.3]}))
    assert profile_frame(frame, mapping)["columns"][0]["possible_id"] is False


def test_age_sequence_is_not_an_id_but_named_id_is():
    frame, mapping = normalize_columns(
        pd.DataFrame({"edad": range(20, 40), "cliente_id": range(100, 120)})
    )
    columns = profile_frame(frame, mapping)["columns"]
    assert columns[0]["possible_id"] is False
    assert columns[1]["possible_id"] is True


def test_operation_identifier_with_accent_is_detected():
    frame, mapping = normalize_columns(
        pd.DataFrame({"Operación ID": [f"OP-{index:04d}" for index in range(20)]})
    )
    assert profile_frame(frame, mapping)["columns"][0]["possible_id"] is True


def test_high_cardinality_text_profile_is_json_serializable():
    frame, mapping = normalize_columns(
        pd.DataFrame({"categoria extensa": [f"Categoría número {index}" for index in range(130)]})
    )
    profile = profile_frame(frame, mapping)
    assert profile["columns"][0]["possible_id"] is True
    assert type(profile["columns"][0]["possible_id"]) is bool


def test_profile_builds_backend_visualizations_without_identifiers():
    frame, mapping = normalize_columns(
        pd.DataFrame(
            {
                "registro_id": range(100),
                "ventas": range(100),
                "costos": [value * 2 + (value % 3) for value in range(100)],
                "margen": [value % 11 for value in range(100)],
            }
        )
    )

    visualizations = profile_frame(frame, mapping)["visualizations"]

    assert [item["display_name"] for item in visualizations["numeric_columns"]] == [
        "ventas",
        "costos",
        "margen",
    ]
    assert visualizations["correlation"]["method"] == "pearson"
    assert len(visualizations["correlation"]["values"]) == 3
    assert visualizations["boxplots"][0]["median"] == pytest.approx(49.5)
    assert visualizations["scatterplots"][0]["points"]


def test_reads_real_csv_xlsx_and_parquet(tmp_path):
    expected = pd.DataFrame({"valor": [1, 2], "grupo": ["a", "b"]})
    csv_path = tmp_path / "data.csv"
    xlsx_path = tmp_path / "data.xlsx"
    parquet_path = tmp_path / "data.parquet"
    expected.to_csv(csv_path, index=False, sep=";")
    with pd.ExcelWriter(xlsx_path) as writer:
        expected.to_excel(writer, sheet_name="Datos", index=False, startrow=1)
        expected.to_excel(writer, sheet_name="Otra", index=False)
    expected.to_parquet(parquet_path, index=False)
    assert read_frame(csv_path).to_dict("records") == expected.to_dict("records")
    assert inspect_file(xlsx_path)["sheet_names"] == ["Datos", "Otra"]
    with pytest.raises(ValueError, match="XLSX_SHEET_REQUIRED"):
        read_frame(xlsx_path)
    assert read_frame(xlsx_path, {"sheet_name": "Datos", "header_row": 1}).equals(expected)
    assert read_frame(parquet_path).equals(expected)


def test_rejects_invalid_header_and_limits_options(tmp_path):
    path = tmp_path / "data.xlsx"
    pd.DataFrame({"a": [1]}).to_excel(path, index=False)
    with pytest.raises(ValueError, match="INVALID_HEADER_ROW"):
        read_frame(path, {"sheet_name": "Sheet1", "header_row": -1})
