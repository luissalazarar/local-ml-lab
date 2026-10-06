import pandas as pd
import pytest

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.ml.engine import analyze
from local_ml_lab.ml.scenario import (
    create_scenario_artifact,
    load_scenario_bundle,
    scenario_prediction,
)


def test_regression_scenario_uses_frozen_selected_model_and_observed_range(tmp_path):
    raw = pd.DataFrame(
        {
            "driver": [float(index) for index in range(120)],
            "segmento": ["norte", "sur"] * 60,
            "target": [5.0 * index + (8 if index % 2 else 0) for index in range(120)],
        }
    )
    frame, mapping = normalize_columns(raw)
    profile = profile_frame(frame, mapping)
    config = {
        "goal": "estimate_value",
        "problem_type": "regression",
        "target_column_id": "c0003",
        "included_column_ids": ["c0001", "c0002"],
        "excluded_column_ids": [],
        "depth": "quick",
        "primary_metric": "mae",
        "seed": 42,
    }
    result = analyze(frame, profile, config)
    artifact = tmp_path / "scenario.joblib"
    metadata = create_scenario_artifact(frame, profile, config, result, artifact)

    assert metadata["available"] is True
    assert metadata["fit_scope"] == "post_selection_refit_for_scenarios"
    assert artifact.is_file()
    bundle = load_scenario_bundle(str(artifact), metadata["model_sha256"])
    response = scenario_prediction(bundle, {"c0001": 50.0}, "c0001", None)
    assert response["driver_id"] == "c0001"
    assert len(response["curve"]) == 25
    assert response["curve"][0]["output"] < response["curve"][-1]["output"]
    assert response["curve_shape"] == "approximately_linear"
    assert response["sensitivity_direction"] == "increasing"
    assert "SCENARIO_NOT_CAUSAL" in response["warnings"]
    assert "SCENARIO_QUICK_CATALOG" in response["warnings"]

    with pytest.raises(ValueError, match="SCENARIO_VALUE_OUTSIDE_OBSERVED_RANGE"):
        scenario_prediction(bundle, {"c0001": 1_000_000.0}, "c0001", None)


def test_scenario_rejects_unselected_input(tmp_path):
    raw = pd.DataFrame({"x": range(30), "y": [2 * value for value in range(30)]})
    frame, mapping = normalize_columns(raw)
    profile = profile_frame(frame, mapping)
    config = {
        "goal": "estimate_value",
        "problem_type": "regression",
        "target_column_id": "c0002",
        "included_column_ids": ["c0001"],
        "excluded_column_ids": [],
        "depth": "quick",
        "primary_metric": "mae",
        "seed": 7,
    }
    result = analyze(frame, profile, config)
    metadata = create_scenario_artifact(frame, profile, config, result, tmp_path / "model.joblib")
    bundle = load_scenario_bundle(str(tmp_path / "model.joblib"), metadata["model_sha256"])
    with pytest.raises(ValueError, match="SCENARIO_VARIABLE_NOT_EDITABLE"):
        scenario_prediction(bundle, {"c9999": 3}, "c0001", None)
