import math

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


def regression_metrics(y, pred, role="selection_oof"):
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mae = mean_absolute_error(y, pred)
    rmse = math.sqrt(mean_squared_error(y, pred))
    r2 = None if len(y) < 2 or np.all(y == y[0]) else float(r2_score(y, pred, force_finite=False))
    return metric_rows({"mae": mae, "rmse": rmse, "r2": r2}, role, len(y))


def classification_metrics(y, pred, role="selection_oof"):
    return metric_rows(
        {
            "accuracy": accuracy_score(y, pred),
            "balanced_accuracy": balanced_accuracy_score(y, pred),
            "macro_f1": f1_score(y, pred, average="macro", zero_division=0),
        },
        role,
        len(y),
    )


def metric_rows(values, role, n):
    return [
        {
            "metric_id": key,
            "name": key.upper().replace("_", " "),
            "value": None if value is None or not math.isfinite(float(value)) else float(value),
            "unit": "score"
            if key in {"r2", "accuracy", "balanced_accuracy", "macro_f1"}
            else "target_unit",
            "evaluation_role": role,
            "n_used": n,
            "n_excluded": 0,
            "reason_code": "NOT_DEFINED" if value is None else None,
        }
        for key, value in values.items()
    ]
