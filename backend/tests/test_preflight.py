import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.domain.contracts import AnalysisConfig
from local_ml_lab.preflight import evaluate_preflight


def prepared(raw, config):
    frame, mapping = normalize_columns(raw)
    return evaluate_preflight(frame, profile_frame(frame, mapping), config)


def test_new_analysis_defaults_to_recommended_model_comparison():
    config = AnalysisConfig(
        dataset_version_id="version-1",
        goal="estimate_value",
        problem_type="regression",
    )
    assert config.depth == "recommended"


def test_blocks_continuous_classification_and_categorical_regression():
    continuous = prepared(
        pd.DataFrame({"x": range(30), "target": [value / 3 for value in range(30)]}),
        {"problem_type": "classification", "target_column_id": "c0002", "included_column_ids": ["c0001"]},
    )
    assert not continuous["can_run"]
    assert "CONTINUOUS_TARGET_FOR_CLASSIFICATION" in {item["code"] for item in continuous["blockers"]}
    categorical = prepared(
        pd.DataFrame({"x": range(30), "target": ["alto", "bajo"] * 15}),
        {"problem_type": "regression", "target_column_id": "c0002", "included_column_ids": ["c0001"]},
    )
    assert not categorical["can_run"]
    assert "REGRESSION_TARGET_NOT_NUMERIC" in {item["code"] for item in categorical["blockers"]}


def test_blocks_singleton_no_features_and_bad_months():
    singleton = prepared(
        pd.DataFrame({"id": [f"X-{i}" for i in range(20)], "target": ["a"] * 19 + ["b"]}),
        {"problem_type": "classification", "target_column_id": "c0002", "included_column_ids": []},
    )
    codes = {item["code"] for item in singleton["blockers"]}
    warning_codes = {item["code"] for item in singleton["warnings"]}
    assert "CLASS_SUPPORT_INSUFFICIENT" in codes
    assert "NO_USABLE_FEATURES" in warning_codes

    raw = pd.DataFrame({
        "fecha": ["2025-01-01", "2025-02-01", "2025-04-01", "2025-04-15", "2025-05-01", "2025-06-01"],
        "valor": [1, 2, 3, 4, 5, 6],
    })
    forecast = prepared(raw, {
        "problem_type": "forecasting",
        "target_column_id": "c0002",
        "date_column_id": "c0001",
        "forecast_options": {"horizon": 2},
    })
    assert not forecast["can_run"]
    assert "DUPLICATE_MONTHS_REQUIRE_AGGREGATION" in {item["code"] for item in forecast["blockers"]}


def test_good_classification_can_run_with_human_summary():
    result = prepared(
        pd.DataFrame({"x": range(30), "target": ["sí", "no"] * 15}),
        {"problem_type": "classification", "target_column_id": "c0002", "included_column_ids": ["c0001"]},
    )
    assert result["can_run"]
    assert result["explanation"] == "La configuración está lista para ejecutar."


def test_blocks_constant_target_and_missing_month_and_warns_small_duplicates():
    constant = prepared(
        pd.DataFrame({"x": range(12), "target": [5.0] * 12}),
        {"goal": "estimate_value", "problem_type": "regression", "target_column_id": "c0002", "included_column_ids": ["c0001"]},
    )
    assert "CONSTANT_TARGET" in {item["code"] for item in constant["blockers"]}

    missing_month = prepared(
        pd.DataFrame({"fecha": ["2025-01-01", "2025-02-01", "2025-04-01", "2025-05-01", "2025-06-01", "2025-07-01"], "valor": [1, 2, 3, 4, 5, 6]}),
        {"goal": "forecast", "problem_type": "forecasting", "target_column_id": "c0002", "date_column_id": "c0001", "forecast_options": {"horizon": 2, "aggregation": "mean"}},
    )
    assert "MISSING_MONTHLY_PERIODS" in {item["code"] for item in missing_month["blockers"]}

    duplicated = prepared(
        pd.DataFrame({"x": [1, 1, 2, 3, 4, 5], "target": [2.0, 2.0, 4.0, 6.0, 8.0, 10.0]}),
        {"goal": "estimate_value", "problem_type": "regression", "target_column_id": "c0002", "included_column_ids": ["c0001"]},
    )
    warning_codes = {item["code"] for item in duplicated["warnings"]}
    assert {"SMALL_DATASET", "DEPENDENT_DUPLICATES_REQUIRE_REVIEW"} <= warning_codes


def test_blocks_goal_problem_mismatch():
    result = prepared(
        pd.DataFrame({"x": range(30), "target": ["a", "b"] * 15}),
        {"goal": "estimate_value", "problem_type": "classification", "target_column_id": "c0002", "included_column_ids": ["c0001"]},
    )
    assert "GOAL_PROBLEM_MISMATCH" in {item["code"] for item in result["blockers"]}
