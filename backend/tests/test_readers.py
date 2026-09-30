import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame


def test_duplicate_headers_keep_distinct_ids():
    frame = pd.DataFrame([[1, 2]], columns=["valor", "valor"])
    normalized, mapping = normalize_columns(frame)
    assert list(normalized.columns) == ["c0001", "c0002"]
    assert mapping[1]["display_name"] == "valor (2)"


def test_continuous_numeric_not_id_when_small():
    frame, mapping = normalize_columns(pd.DataFrame({"valor": [1.1, 2.2, 3.3]}))
    assert profile_frame(frame, mapping)["columns"][0]["possible_id"] is False
