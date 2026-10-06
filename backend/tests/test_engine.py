import pandas as pd
import pytest
from sklearn.preprocessing import StandardScaler

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
    assert all(c["status"] in {"completed", "failed"} for c in result["candidates"])
    assert result["selection_decision"]["policy_version"] == "selection-policy-2.1"
    assert result["plan_sha256"] == result["analysis_plan"]["plan_sha256"]


def test_prepared_analysis_preserves_original_prepared_and_target_counts():
    raw = pd.DataFrame({"x": list(range(12)), "y": [float(i) for i in range(10)] + [None, None]})
    frame, mapping = normalize_columns(raw)
    result = analyze(
        frame,
        profile_frame(frame, mapping),
        {
            "goal": "estimate_value",
            "problem_type": "regression",
            "target_column_id": "c0002",
            "included_column_ids": ["c0001"],
            "excluded_column_ids": [],
            "depth": "quick",
            "seed": 42,
            "_preparation": {"rows_input": 14, "rows_analyzed": 12, "rows_quarantined": 2},
        },
    )
    counts = result["data_preparation"]
    assert counts["rows_input"] == 14
    assert counts["rows_analyzed"] == 12
    assert counts["rows_quarantined"] == 2
    assert counts["target_missing_rows"] == 2
    assert counts["rows_analyzed"] - counts["target_missing_rows"] == 10


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
    assert result["goal"] == "classify"
    assert result["problem_type"] == "classification"


def test_included_columns_primary_metric_and_oof_pfi(monkeypatch):
    raw = pd.DataFrame(
        {
            "permitida": [float(i) + 0.1 for i in range(30)],
            "prohibida": [float(i % 4) + 0.2 for i in range(30)],
            "target": ["minoritaria" if i % 5 == 0 else "mayoritaria" for i in range(30)],
        }
    )
    frame, mapping = normalize_columns(raw)
    lengths = []
    original_fit = StandardScaler.fit

    def tracked_fit(self, values, y=None, sample_weight=None):
        lengths.append(len(values))
        return original_fit(self, values, y, sample_weight=sample_weight)

    monkeypatch.setattr(StandardScaler, "fit", tracked_fit)
    result = analyze(
        frame,
        profile_frame(frame, mapping),
        {
            "goal": "classify",
            "problem_type": "classification",
            "target_column_id": "c0003",
            "included_column_ids": ["c0001"],
            "excluded_column_ids": [],
            "depth": "quick",
            "primary_metric": "macro_f1",
            "validation_context": "independent_records",
            "seed": 42,
        },
    )
    assert result["primary_metric_id"] == "macro_f1"
    assert result["selection_decision"]["primary_metric_id"] == "macro_f1"
    assert {driver["source_column_id"] for driver in result["drivers"]} <= {"c0001"}
    assert all(driver["fit_scope"] == "fold_train_only" for driver in result["drivers"])
    assert lengths and max(lengths) < len(frame)
    assert result["diagnostics"]["confusion_matrix"]


def test_rejects_unsupported_metric_and_overlapping_columns():
    raw = pd.DataFrame({"x": [float(i) for i in range(12)], "y": [float(i * 2) for i in range(12)]})
    frame, mapping = normalize_columns(raw)
    profile = profile_frame(frame, mapping)
    base = {
        "goal": "estimate_value",
        "problem_type": "regression",
        "target_column_id": "c0002",
        "included_column_ids": ["c0001"],
        "excluded_column_ids": [],
        "depth": "quick",
        "seed": 42,
    }
    with pytest.raises(ValueError, match="UNSUPPORTED_PRIMARY_METRIC"):
        analyze(frame, profile, {**base, "primary_metric": "accuracy"})
    with pytest.raises(ValueError, match="COLUMN_INCLUDED_AND_EXCLUDED"):
        analyze(frame, profile, {**base, "excluded_column_ids": ["c0001"]})


def test_monthly_forecast_calendar_horizon_and_missing_periods():
    raw = pd.DataFrame(
        {
            "fecha": pd.date_range("2022-01-01", periods=36, freq="MS").astype(str),
            "valor": [100 + (i % 12) for i in range(36)],
        }
    )
    frame, mapping = normalize_columns(raw)
    config = {
        "goal": "forecast",
        "problem_type": "forecasting",
        "target_column_id": "c0002",
        "date_column_id": "c0001",
        "included_column_ids": [],
        "excluded_column_ids": [],
        "depth": "quick",
        "primary_metric": "mae",
        "forecast_options": {"horizon": 4, "aggregation": "mean"},
        "seed": 42,
    }
    result = analyze(frame, profile_frame(frame, mapping), config)
    future = [row for row in result["predictions"] if row["evaluation_role"] == "forecast_future"]
    assert [row["target_period"] for row in future] == [
        "2025-01-01",
        "2025-02-01",
        "2025-03-01",
        "2025-04-01",
    ]
    assert not any(row["evaluation_role"] == "final_test" for row in result["predictions"])
    missing = raw.drop(index=10)
    missing_frame, missing_mapping = normalize_columns(missing)
    with pytest.raises(ValueError, match="MISSING_MONTHLY_PERIODS"):
        analyze(missing_frame, profile_frame(missing_frame, missing_mapping), config)


def test_long_horizon_uses_shortest_prefix_for_seasonal_eligibility():
    raw = pd.DataFrame(
        {
            "fecha": pd.date_range("2020-01-01", periods=60, freq="MS").astype(str),
            "valor": [float(i % 12) for i in range(60)],
        }
    )
    frame, mapping = normalize_columns(raw)
    result = analyze(
        frame,
        profile_frame(frame, mapping),
        {
            "goal": "forecast",
            "problem_type": "forecasting",
            "target_column_id": "c0002",
            "date_column_id": "c0001",
            "included_column_ids": [],
            "excluded_column_ids": [],
            "depth": "quick",
            "primary_metric": "mae",
            "forecast_options": {"horizon": 13, "aggregation": "mean"},
            "seed": 42,
        },
    )
    future = [row for row in result["predictions"] if row["evaluation_role"] == "forecast_future"]
    seasonal = next(item for item in result["candidates"] if item["model_id"] == "seasonal_naive")
    assert seasonal["status"] == "ineligible"
    assert "FIRST_PREFIX_HAS_21" in seasonal["reason_code"]
    assert len(future) == 13
