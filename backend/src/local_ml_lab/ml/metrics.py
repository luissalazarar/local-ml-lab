from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    mean_absolute_error,
    mean_squared_error,
)


def _finite(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def regression_metrics(y, pred, role="selection_oof"):
    actual = np.asarray(y, dtype=float)
    predicted = np.asarray(pred, dtype=float)
    if actual.shape != predicted.shape or actual.ndim != 1:
        raise ValueError("PREDICTION_SHAPE_MISMATCH")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("NON_FINITE_PREDICTION")
    values = {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(math.sqrt(mean_squared_error(actual, predicted))),
        "median_absolute_error": float(np.median(np.abs(predicted - actual))),
        "p90_absolute_error": float(np.percentile(np.abs(predicted - actual), 90)),
        "r2": None,
    }
    reasons = {"r2": None}
    if len(actual) < 2:
        reasons["r2"] = "INSUFFICIENT_SUPPORT"
    elif np.all(actual == actual[0]):
        reasons["r2"] = "CONSTANT_TARGET"
    else:
        residual = float(np.sum((actual - predicted) ** 2))
        total = float(np.sum((actual - actual.mean()) ** 2))
        values["r2"] = _finite(1.0 - residual / total)
        if values["r2"] is None:
            reasons["r2"] = "NUMERICALLY_UNDEFINED"
    return metric_rows(values, role, len(actual), reasons)


def classification_diagnostics(y, pred, labels: Iterable) -> dict:
    actual = np.asarray([str(value) for value in y], dtype=object)
    predicted = np.asarray([str(value) for value in pred], dtype=object)
    universe = [str(value) for value in labels]
    if actual.shape != predicted.shape or actual.ndim != 1:
        raise ValueError("PREDICTION_SHAPE_MISMATCH")
    if not set(predicted).issubset(set(universe)):
        raise ValueError("PREDICTION_CLASS_OUTSIDE_UNIVERSE")
    matrix = []
    per_class = []
    for real_label in universe:
        row = [int(np.sum((actual == real_label) & (predicted == guessed))) for guessed in universe]
        matrix.append(row)
    for index, label in enumerate(universe):
        tp = matrix[index][index]
        support = sum(matrix[index])
        predicted_count = sum(row[index] for row in matrix)
        recall = tp / support if support else None
        precision = tp / predicted_count if predicted_count else None
        f1_denominator = 2 * tp + (predicted_count - tp) + (support - tp)
        f1 = 2 * tp / f1_denominator if f1_denominator else None
        per_class.append(
            {
                "label": label,
                "support": support,
                "predicted_count": predicted_count,
                "true_positive": tp,
                "recall": _finite(recall),
                "precision": _finite(precision),
                "f1": _finite(f1),
                "precision_reason": None if predicted_count else "NO_PREDICTED_CASES",
                "recall_reason": None if support else "NO_ACTUAL_CASES",
            }
        )
    return {
        "class_labels": universe,
        "class_support": [{"label": item["label"], "count": item["support"]} for item in per_class],
        "confusion_matrix": matrix,
        "per_class": per_class,
    }


def classification_metrics(y, pred, role="selection_oof", labels=None):
    universe = list(labels) if labels is not None else sorted({str(value) for value in y})
    diagnostics = classification_diagnostics(y, pred, universe)
    recalls = [item["recall"] for item in diagnostics["per_class"]]
    f1_values = [item["f1"] for item in diagnostics["per_class"]]
    values = {
        "accuracy": float(accuracy_score([str(v) for v in y], [str(v) for v in pred])),
        "balanced_accuracy": (
            float(balanced_accuracy_score([str(v) for v in y], [str(v) for v in pred]))
            if all(value is not None for value in recalls)
            else None
        ),
        "macro_f1": (
            float(sum(f1_values) / len(f1_values))
            if f1_values and all(value is not None for value in f1_values)
            else None
        ),
    }
    reasons = {
        "balanced_accuracy": None
        if values["balanced_accuracy"] is not None
        else "CLASS_RECALL_UNDEFINED",
        "macro_f1": None if values["macro_f1"] is not None else "CLASS_F1_UNDEFINED",
    }
    return metric_rows(values, role, len(list(y)), reasons)


def metric_rows(values, role, n, reasons=None):
    reasons = reasons or {}
    rows = []
    for key, value in values.items():
        finite = _finite(value)
        rows.append(
            {
                "metric_id": key,
                "name": key.upper().replace("_", " "),
                "value": finite,
                "unit": (
                    "score"
                    if key in {"r2", "accuracy", "balanced_accuracy", "macro_f1"}
                    else "target_unit"
                ),
                "evaluation_role": role,
                "n_used": n,
                "n_excluded": 0,
                "reason_code": reasons.get(key) if finite is None else None,
            }
        )
    return rows


def distribution(values: list[float]) -> dict:
    clean = np.asarray([float(value) for value in values if _finite(value) is not None])
    if not len(clean):
        return {"mean": None, "median": None, "sample_std": None, "range": None}
    return {
        "mean": float(clean.mean()),
        "median": float(np.median(clean)),
        "sample_std": float(clean.std(ddof=1)) if len(clean) > 1 else None,
        "range": float(clean.max() - clean.min()),
    }
