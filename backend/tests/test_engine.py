import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.ml.engine import analyze


def test_real_regression_pipeline_and_baseline():
    raw = pd.DataFrame(
        {"x": list(range(24)), "grupo": ["a", "b"] * 12, "y": [2 * x + (x % 3) for x in range(24)]}
    )
    frame, mapping = normalize_columns(raw)
    profile = profile_frame(frame, mapping)
    result = analyze(
        frame,
        profile,
        {
            "goal": "estimate_value",
            "problem_type": "regression",
            "target_column_id": "c0003",
            "excluded_column_ids": [],
            "depth": "quick",
            "seed": 42,
        },
    )
    assert result["analytical_outcome"] == "completed"
    assert any(c["model_id"] == "dummy_median" for c in result["candidates"])
    assert all(c["status"] in {"succeeded", "failed"} for c in result["candidates"])


def test_singleton_class_is_not_evaluable():
    raw = pd.DataFrame({"x": range(6), "y": ["a", "a", "a", "a", "a", "b"]})
    frame, mapping = normalize_columns(raw)
    result = analyze(
        frame,
        profile_frame(frame, mapping),
        {
            "goal": "classify",
            "problem_type": "classification",
            "target_column_id": "c0002",
            "excluded_column_ids": [],
            "depth": "quick",
            "seed": 42,
        },
    )
    assert result["analytical_outcome"] == "not_evaluable"
