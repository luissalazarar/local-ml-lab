"""Observed local timings for the four public v0.7 acceptance paths."""

from __future__ import annotations

import json
import platform
import time

import numpy as np
import pandas as pd

from local_ml_lab.data.readers import normalize_columns, profile_frame
from local_ml_lab.ml.engine import analyze


def tabular(problem: str, depth: str):
    rng = np.random.default_rng(42)
    x = np.linspace(-4, 4, 240)
    if problem == "regression":
        raw = pd.DataFrame(
            {"x": x, "group": np.arange(240) % 7, "result": 3 * x + rng.normal(0, 0.7, 240)}
        )
        metric = "mae"
        goal = "estimate_value"
    else:
        raw = pd.DataFrame(
            {
                "x": x,
                "group": np.arange(240) % 7,
                "result": np.where(x + rng.normal(0, 0.8, 240) > 0, "Sí", "No"),
            }
        )
        metric = "balanced_accuracy"
        goal = "classify"
    frame, mapping = normalize_columns(raw)
    return analyze(
        frame,
        profile_frame(frame, mapping),
        {
            "goal": goal,
            "problem_type": problem,
            "target_column_id": "c0003",
            "included_column_ids": ["c0001", "c0002"],
            "excluded_column_ids": [],
            "depth": depth,
            "primary_metric": metric,
            "seed": 42,
        },
    )


def forecast():
    index = np.arange(84)
    raw = pd.DataFrame(
        {
            "month": pd.date_range("2019-01-01", periods=84, freq="MS").astype(str),
            "result": 100 + 1.2 * index + 12 * np.sin(2 * np.pi * index / 12),
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
            "depth": "recommended",
            "primary_metric": "mae",
            "forecast_options": {"horizon": 6, "aggregation": "mean"},
            "seed": 42,
        },
    )


def main():
    cases = [
        ("Regresión Quick", lambda: tabular("regression", "quick")),
        ("Regresión Recommended", lambda: tabular("regression", "recommended")),
        ("Clasificación Recommended", lambda: tabular("classification", "recommended")),
        ("Forecast Recommended", forecast),
    ]
    rows = []
    for name, run in cases:
        started = time.perf_counter()
        result = run()
        assert result["analytical_outcome"] == "completed"
        rows.append(
            {
                "case": name,
                "seconds": round(time.perf_counter() - started, 4),
                "selected": result["selection_decision"]["selected_candidate_id"],
            }
        )
    print(
        json.dumps(
            {
                "status": "PASS",
                "hardware": {
                    "system": platform.system(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                },
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
