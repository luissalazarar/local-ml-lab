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
