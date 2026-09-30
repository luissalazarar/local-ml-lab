"""Deterministic v0.6 engine acceptance using synthetic data only."""

from __future__ import annotations

import json
import math
import time

import numpy as np
import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.ml.engine import analyze


def forecast(values, horizon, depth):
    raw = pd.DataFrame(
        {
            "date": pd.date_range("2018-01-01", periods=len(values), freq="MS").astype(str),
            "value": np.asarray(values, dtype=float),
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


def finite_json(result):
    json.dumps(result, ensure_ascii=False, allow_nan=False)


def main():
    rng = np.random.default_rng(42)
    t72 = np.arange(72)
    t96 = np.arange(96)
    cases = {
        "A_constant": np.repeat(100.0, 72),
        "B_trend": 100 + 4 * t72,
        "C_seasonal": 100 + 20 * np.sin(2 * np.pi * t96 / 12) + 8 * np.cos(4 * np.pi * t96 / 12),
        "D_trend_seasonal": 100 + 4 * t96 + 20 * np.sin(2 * np.pi * t96 / 12) + rng.normal(0, 2, 96),
        "E_noise": rng.normal(100, 12, 72),
        "F_level_change": np.r_[np.repeat(80.0, 36), np.repeat(125.0, 36)],
        "G_zero_negative": 5 * np.sin(2 * np.pi * t72 / 12) - 2,
        "H_short": 100 + np.arange(20),
    }
    rows = []
    for case_id, values in cases.items():
        for horizon in (1, 3, 6, 12, 24):
            depth = "recommended" if horizon == 3 else "quick"
            started = time.perf_counter()
            result = forecast(values, horizon, depth)
            elapsed = time.perf_counter() - started
            finite_json(result)
            decision = result.get("selection_decision", {})
            candidates = {
                item["model_id"]: item
                for item in result.get("candidates", [])
            }
            future = [
                item
                for item in result.get("predictions", [])
                if item.get("evaluation_role") == "forecast_future"
            ]
            if result["analytical_outcome"] == "completed":
                assert len(future) == horizon
                assert all(item["actual"] is None and item["error"] is None for item in future)
            rows.append(
                {
                    "case": case_id,
                    "horizon": horizon,
                    "depth": depth,
                    "outcome": result["analytical_outcome"],
                    "selected": decision.get("selected_candidate_id"),
                    "baseline": decision.get("baseline_candidate_id"),
                    "best_observed": decision.get("best_observed_candidate_id"),
                    "baseline_mae": candidates.get(decision.get("baseline_candidate_id"), {}).get(
                        "primary_value"
                    ),
                    "selected_mae": candidates.get(decision.get("selected_candidate_id"), {}).get(
                        "primary_value"
                    ),
                    "units": len(result.get("analysis_plan", {}).get("validation", {}).get("units", [])),
                    "seconds": round(elapsed, 4),
                }
            )
    indexed = {(row["case"], row["horizon"]): row for row in rows}
    assert indexed[("A_constant", 3)]["selected"] == "last_value"
    assert indexed[("B_trend", 3)]["selected"] == "linear_trend"
    assert indexed[("C_seasonal", 3)]["selected"] == "seasonal_naive"
    assert all(
        row["selected_mae"] is None or math.isfinite(float(row["selected_mae"]))
        for row in rows
    )
    print(json.dumps({"status": "PASS", "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
