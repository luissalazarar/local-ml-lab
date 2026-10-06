import json

import numpy as np
import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.ml.engine import analyze, tabular_confirmation_splits


def _regression_config(depth="recommended"):
    return {
        "goal": "estimate_value",
        "problem_type": "regression",
        "target_column_id": "c0002",
        "included_column_ids": ["c0001"],
        "excluded_column_ids": [],
        "depth": depth,
        "primary_metric": "mae",
        "seed": 42,
    }


def test_recommended_tabular_confirmation_uses_development_only(tmp_path):
    raw = pd.DataFrame({"x": np.arange(120, dtype=float), "y": 3 * np.arange(120, dtype=float) + 2})
    frame, mapping = normalize_columns(raw)
    events = []
    result = analyze(
        frame,
        profile_frame(frame, mapping),
        _regression_config(),
        events.append,
        live_dir=tmp_path,
    )
    assert result["selection_decision"]["policy_version"] == "selection-policy-2.1"
    assert result["confirmation"]["status"] == "confirmed"
    assert result["confirmation"]["uses_holdout"] is False
    confirmation = result["analysis_plan"]["validation"]["confirmation"]
    assert len(confirmation["units"]) == 3
    assert all(unit["unit_id"].startswith("confirmation-") for unit in confirmation["units"])
    holdout = set(result["analysis_plan"]["validation"]["holdout_row_ids"])
    assert all(
        holdout.isdisjoint(unit["train_row_ids"] + unit["validation_row_ids"])
        for unit in confirmation["units"]
    )
    confirmation_events = [
        event for event in events if event["event_type"] == "confirmation_unit_completed"
    ]
    assert len(confirmation_events) == 6
    assert all(event.get("preview_ref") for event in confirmation_events)
    assert all(
        (tmp_path / event["preview_ref"].removeprefix("live/")).is_file()
        for event in confirmation_events
    )


def test_confirmation_failure_reverts_to_baseline(monkeypatch):
    from local_ml_lab.ml import engine

    raw = pd.DataFrame({"x": np.arange(120, dtype=float), "y": 4 * np.arange(120, dtype=float) + 1})
    frame, mapping = normalize_columns(raw)
    monkeypatch.setattr(
        engine,
        "confirmation_gate",
        lambda *args, **kwargs: {
            "status": "not_confirmed",
            "reason_code": "GAIN_NOT_REPEATED_IN_CONFIRMATION",
            "joint_improvement": 0.0,
            "minimum_practical_gain": 1.0,
            "paired_improvements": [1.0, -1.0, -1.0],
            "won_pairs": 1,
            "required_wins": 2,
            "median_paired_improvement": -1.0,
        },
    )
    result = analyze(frame, profile_frame(frame, mapping), _regression_config())
    assert result["confirmation"]["status"] == "not_confirmed"
    assert result["selection_decision"]["selected_candidate_id"] == "dummy_median"
    assert result["selection_decision"]["reason_code"] == "GAIN_NOT_REPEATED_IN_CONFIRMATION"


def test_confirmation_support_is_not_relaxed():
    y = pd.Series(np.arange(79, dtype=float))
    splits, reason, _ = tabular_confirmation_splits(
        y, np.asarray([f"g-{index}" for index in range(79)]), "regression", 42, "recommended"
    )
    assert splits == []
    assert reason == "NEEDS_80_DEVELOPMENT_ROWS"


def test_recommended_mode_can_select_a_nonlinear_family():
    x = np.linspace(-4, 4, 240)
    raw = pd.DataFrame({"x": x, "y": 120 * x**2 + 15 * np.sin(4 * x)})
    frame, mapping = normalize_columns(raw)
    result = analyze(frame, profile_frame(frame, mapping), _regression_config())

    assert result["selection_decision"]["selected_candidate_id"] in {
        "extra_trees_regressor",
        "random_forest_regressor",
    }
    completed = {item["model_id"] for item in result["candidates"] if item["status"] == "completed"}
    assert {"ridge", "extra_trees_regressor", "random_forest_regressor"} <= completed


def test_live_preview_is_atomic_bounded_and_event_contains_only_reference(tmp_path):
    raw = pd.DataFrame({"x": np.arange(620, dtype=float), "y": 2 * np.arange(620, dtype=float) + 5})
    frame, mapping = normalize_columns(raw)
    events = []
    analyze(
        frame,
        profile_frame(frame, mapping),
        _regression_config(depth="quick"),
        events.append,
        live_dir=tmp_path,
    )
    completed = [event for event in events if event["event_type"] == "unit_completed"]
    assert completed
    assert all("preview" not in event for event in completed)
    assert all(event.get("preview_ref") for event in completed)
    payload = json.loads(next(tmp_path.rglob("*.json")).read_text(encoding="utf-8"))
    assert payload["count_preview"] <= 500
    assert payload["count_complete"] >= payload["count_preview"]
    assert len(payload["predictions"]) == payload["count_preview"]
    assert len(payload["sha256"]) == 64
