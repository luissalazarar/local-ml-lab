import numpy as np
import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.ml.engine import analyze
from local_ml_lab.ml.forecasting import FORECAST_SPECS, fit_predict


def tabular_result(raw, problem, target, included=None, depth="recommended"):
    frame, mapping = normalize_columns(raw)
    config = {
        "goal": "estimate_value" if problem == "regression" else "classify",
        "problem_type": problem,
        "target_column_id": target,
        "excluded_column_ids": [],
        "depth": depth,
        "seed": 42,
    }
    if included is not None:
        config["included_column_ids"] = included
    return analyze(frame, profile_frame(frame, mapping), config)


def forecast_result(values, horizon=3, depth="recommended"):
    raw = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=len(values), freq="MS").astype(str),
            "value": values,
        }
    )
    frame, mapping = normalize_columns(raw)
    return analyze(
        frame,
        profile_frame(frame, mapping),
        {
            "goal": "forecast",
            "problem_type": "forecasting",
            "target_column_id": "c0002",
            "date_column_id": "c0001",
            "included_column_ids": [],
            "excluded_column_ids": [],
            "depth": depth,
            "primary_metric": "mae",
            "forecast_options": {"horizon": horizon, "aggregation": "mean"},
            "seed": 42,
        },
    )


def test_empty_feature_selection_runs_only_reference():
    raw = pd.DataFrame({"x": range(30), "y": np.arange(30, dtype=float)})
    result = tabular_result(raw, "regression", "c0002", included=[])
    assert result["selection_decision"]["selected_candidate_id"] == "dummy_median"
    assert next(c for c in result["candidates"] if c["model_id"] == "ridge")["status"] == "ineligible"
    assert result["drivers"] == []
    assert "no utiliza las variables" in result["explanation_scope"]["reason"]


def test_omitted_features_use_eligible_defaults_but_empty_does_not():
    raw = pd.DataFrame({"x": range(30), "y": np.arange(30, dtype=float) * 4})
    default_result = tabular_result(raw, "regression", "c0002", included=None, depth="quick")
    empty_result = tabular_result(raw, "regression", "c0002", included=[], depth="quick")
    assert next(c for c in default_result["candidates"] if c["model_id"] == "ridge")["status"] == "completed"
    assert next(c for c in empty_result["candidates"] if c["model_id"] == "ridge")["status"] == "ineligible"


def test_exact_duplicate_rows_never_cross_a_split():
    base = pd.DataFrame({"x": range(20), "y": [value * 3 for value in range(20)]})
    raw = pd.concat([base, base.iloc[[3, 3, 9, 9]]], ignore_index=True)
    result = tabular_result(raw, "regression", "c0002", included=["c0001"], depth="quick")
    row_to_block = {}
    normalized, _ = normalize_columns(raw)
    from local_ml_lab.ml.planning import exact_row_groups

    for index, block in enumerate(exact_row_groups(normalized), 1):
        row_to_block[f"row-{index:07d}"] = block
    for unit in result["analysis_plan"]["validation"]["units"]:
        train_blocks = {row_to_block[row] for row in unit["train_row_ids"]}
        validation_blocks = {row_to_block[row] for row in unit["validation_row_ids"]}
        assert train_blocks.isdisjoint(validation_blocks)


def test_forecast_catalog_and_plan_follow_fixed_formula():
    result = forecast_result(100 + 4 * np.arange(72), horizon=3)
    assert [item["model_id"] for item in result["candidates"]] == [
        "last_value",
        "historical_mean",
        "seasonal_naive",
        "linear_trend",
        "ridge_trend_month",
        "holt_damped",
        "holt_winters_add_damped",
    ]
    plan = result["analysis_plan"]
    assert plan["validation"]["minimum_window"] == 36
    assert len(plan["validation"]["units"]) == 6
    assert plan["validation"]["reserved_test_periods"] == ["2025-10", "2025-11", "2025-12"]
    assert result["selection_decision"]["selected_candidate_id"] == "linear_trend"
    assert result["final_test"] is not None


def test_constant_forecast_allows_simplest_reference_and_future_is_exact():
    result = forecast_result(np.repeat(100.0, 72), horizon=6)
    assert result["selection_decision"]["selected_candidate_id"] == "last_value"
    future = [row for row in result["predictions"] if row["evaluation_role"] == "forecast_future"]
    assert len(future) == 6
    assert {row["predicted"] for row in future} == {100.0}
    assert all(row["actual"] is None and row["error"] is None for row in future)


def test_exact_seasonality_can_select_seasonal_reference():
    index = np.arange(96)
    result = forecast_result(100 + 20 * np.sin(2 * np.pi * index / 12), horizon=3)
    assert result["selection_decision"]["selected_candidate_id"] == "seasonal_naive"


def test_future_values_after_origin_never_enter_fit_predict():
    spec = next(item for item in FORECAST_SPECS if item.model_id == "linear_trend")
    dates = pd.period_range("2020-01", periods=40, freq="M")
    prefix = np.arange(24, dtype=float)
    first = fit_predict(spec, prefix, dates[:24], dates[24:27], {})
    changed_future = np.concatenate([prefix, np.repeat(99999.0, 16)])
    second = fit_predict(spec, changed_future[:24], dates[:24], dates[24:27], {})
    assert np.array_equal(first, second)


def test_every_selection_prediction_has_alignment_keys_and_finite_value():
    result = forecast_result(100 + np.arange(72), horizon=3)
    rows = [row for row in result["predictions"] if row["evaluation_role"] == "selection_backtest"]
    assert rows
    assert all(row["unit_id"] and row["target_period"] and row["horizon"] for row in rows)
    assert all(np.isfinite(row["predicted"]) for row in rows)
