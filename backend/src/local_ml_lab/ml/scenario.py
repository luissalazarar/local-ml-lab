from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .engine import make_pipeline
from .planning import stable_seed
from .registry import specs

MAX_SCENARIO_TRAIN_ROWS = 20_000
MAX_CONTROLS = 8
MAX_CATEGORY_OPTIONS = 20
CURVE_POINTS = 25


def create_scenario_artifact(
    frame: pd.DataFrame,
    profile: dict,
    config: dict,
    result: dict,
    destination: str | Path,
) -> dict:
    """Fit one bounded post-selection model for local, descriptive what-if predictions."""
    if result.get("analytical_outcome") != "completed":
        return {"available": False, "reason_code": "ANALYSIS_NOT_COMPLETED"}
    problem = result.get("problem_type")
    if problem not in {"regression", "classification"}:
        return {"available": False, "reason_code": "SCENARIOS_NOT_APPLICABLE"}
    target = config.get("target_column_id")
    selected_id = result.get("selection_decision", {}).get("selected_candidate_id")
    features = result.get("analysis_plan", {}).get("included_column_ids", [])
    if not target or target not in frame or not selected_id or not features:
        return {"available": False, "reason_code": "SCENARIO_INPUTS_NOT_AVAILABLE"}

    usable = frame.loc[frame[target].notna(), [*features, target]].copy()
    y = usable[target]
    if problem == "regression":
        y = pd.to_numeric(y, errors="coerce")
        valid = y.notna()
        usable, y = usable.loc[valid], y.loc[valid]
    else:
        y = y.astype(str)
    if len(usable) < 2:
        return {"available": False, "reason_code": "INSUFFICIENT_SCENARIO_ROWS"}

    source_row_count = len(usable)
    if source_row_count > MAX_SCENARIO_TRAIN_ROWS:
        positions = np.linspace(0, source_row_count - 1, MAX_SCENARIO_TRAIN_ROWS, dtype=int)
        usable = usable.iloc[positions]
        y = y.iloc[positions]
        sample_method = "deterministic_stride"
    else:
        sample_method = "all_eligible_rows"
    x = usable[features].copy()

    primary_metric = result.get("primary_metric_id")
    catalog = specs(problem, config.get("depth", "quick"), primary_metric)
    selected_spec = next((item for item in catalog if item.model_id == selected_id), None)
    if not selected_spec:
        return {"available": False, "reason_code": "SELECTED_MODEL_NOT_IN_CATALOG"}
    seed = stable_seed(int(config.get("seed", 42)), selected_id, "scenario-model")
    model = make_pipeline(selected_spec, seed) if selected_spec.uses_features else selected_spec.build(seed)
    model.fit(x, y)

    names = {
        item.get("column_id"): item.get("display_name", item.get("column_id"))
        for item in profile.get("columns", [])
    }
    importance = {
        item["source_column_id"]: item.get("importance_mean")
        for item in result.get("drivers", [])
    }
    ranked = [item["source_column_id"] for item in result.get("drivers", []) if item.get("source_column_id") in features]
    ranked.extend(column for column in features if column not in ranked)
    controls = []
    defaults = {}
    for column in features:
        control = _control(column, names.get(column, column), x[column], importance.get(column))
        defaults[column] = control["default"]
        if control.get("editable") and len(controls) < MAX_CONTROLS and column in ranked[:MAX_CONTROLS]:
            controls.append(control)
    controls.sort(key=lambda item: ranked.index(item["column_id"]))
    if not controls:
        return {"available": False, "reason_code": "NO_EDITABLE_SCENARIO_VARIABLES"}

    classes = [str(value) for value in getattr(model, "classes_", [])]
    metadata = {
        "available": True,
        "schema_version": "1.1",
        "model_id": selected_id,
        "model_name": selected_spec.display_name,
        "model_family": selected_spec.family,
        "training_depth": config.get("depth", "recommended"),
        "target_column_id": target,
        "target_name": names.get(target, target),
        "problem_type": problem,
        "fit_scope": "post_selection_refit_for_scenarios",
        "fit_row_count": len(x),
        "source_row_count": source_row_count,
        "sample_method": sample_method,
        "controls": controls,
        "class_labels": classes,
        "warnings": [
            "SCENARIO_NOT_EVALUATION",
            "SCENARIO_NOT_CAUSAL",
            "SCENARIO_WITHIN_OBSERVED_RANGE",
            *(["SCENARIO_QUICK_CATALOG"] if config.get("depth") == "quick" else []),
        ],
    }
    bundle = {"model": model, "metadata": metadata, "defaults": defaults, "features": features}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, destination, compress=3)
    metadata["model_sha256"] = _sha256(destination)
    return metadata


def _control(column: str, display_name: str, series: pd.Series, importance) -> dict:
    non_null = series.dropna()
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(non_null, errors="coerce").dropna().astype(float)
        if numeric.empty:
            return {"column_id": column, "display_name": display_name, "kind": "numeric", "editable": False, "default": 0.0}
        low, high = float(numeric.quantile(0.01)), float(numeric.quantile(0.99))
        if not math.isfinite(low) or not math.isfinite(high) or low == high:
            low, high = float(numeric.min()), float(numeric.max())
        default = float(numeric.median())
        editable = math.isfinite(low) and math.isfinite(high) and low < high
        return {
            "column_id": column,
            "display_name": display_name,
            "kind": "numeric",
            "editable": editable,
            "minimum": low,
            "maximum": high,
            "step": (high - low) / 100 if editable else 1.0,
            "default": default,
            "importance_mean": importance,
        }
    values = non_null.astype(str)
    if values.empty:
        return {"column_id": column, "display_name": display_name, "kind": "categorical", "editable": False, "default": ""}
    counts = values.value_counts()
    options = [str(value) for value in counts.index[:MAX_CATEGORY_OPTIONS]]
    return {
        "column_id": column,
        "display_name": display_name,
        "kind": "categorical",
        "editable": len(options) > 1,
        "options": options,
        "default": options[0],
        "importance_mean": importance,
        "options_truncated": len(counts) > len(options),
    }


def scenario_prediction(bundle: dict, values: dict, driver_id: str | None, class_label: str | None) -> dict:
    metadata = bundle["metadata"]
    controls = {item["column_id"]: item for item in metadata["controls"]}
    unknown = set(values) - set(controls)
    if unknown:
        raise ValueError("SCENARIO_VARIABLE_NOT_EDITABLE")
    row = dict(bundle["defaults"])
    for column, value in values.items():
        row[column] = _validated_value(controls[column], value)
    selected_driver = driver_id or metadata["controls"][0]["column_id"]
    if selected_driver not in controls:
        raise ValueError("SCENARIO_DRIVER_NOT_EDITABLE")

    model = bundle["model"]
    frame = pd.DataFrame([row], columns=bundle["features"])
    current = _prediction(model, frame, metadata["problem_type"], class_label)
    driver = controls[selected_driver]
    grid = (
        np.linspace(driver["minimum"], driver["maximum"], CURVE_POINTS).tolist()
        if driver["kind"] == "numeric"
        else driver["options"]
    )
    rows = []
    for value in grid:
        candidate = dict(row)
        candidate[selected_driver] = value
        rows.append(candidate)
    curve_frame = pd.DataFrame(rows, columns=bundle["features"])
    curve = _prediction(model, curve_frame, metadata["problem_type"], class_label)
    curve_values = curve["curve_values"]
    return {
        "prediction": current["prediction"],
        "class_label": current.get("class_label"),
        "probability": current.get("probability"),
        "driver_id": selected_driver,
        "driver_name": driver["display_name"],
        "curve_unit": "target_unit" if metadata["problem_type"] == "regression" else "class_probability",
        "model_family": metadata.get("model_family"),
        "training_depth": metadata.get("training_depth"),
        "curve_shape": _curve_shape(grid, curve_values, driver["kind"]),
        "sensitivity_direction": _sensitivity_direction(curve_values, driver["kind"]),
        "curve": [
            {"input": _json_value(value), "output": _json_value(output)}
            for value, output in zip(grid, curve_values, strict=True)
        ],
        "warnings": metadata["warnings"],
    }


def _prediction(model, frame: pd.DataFrame, problem: str, class_label: str | None) -> dict:
    predicted = model.predict(frame)
    if problem == "regression":
        values = [float(value) for value in predicted]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("NON_FINITE_SCENARIO_PREDICTION")
        return {"prediction": values[0], "curve_values": values}
    classes = [str(value) for value in model.classes_]
    selected_class = class_label or str(predicted[0])
    if selected_class not in classes:
        raise ValueError("SCENARIO_CLASS_NOT_AVAILABLE")
    probabilities = model.predict_proba(frame)
    index = classes.index(selected_class)
    values = [float(row[index]) for row in probabilities]
    return {
        "prediction": str(predicted[0]),
        "class_label": selected_class,
        "probability": values[0],
        "curve_values": values,
    }


def _validated_value(control: dict, value):
    if control["kind"] == "numeric":
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("SCENARIO_VALUE_NOT_NUMERIC") from exc
        if not math.isfinite(numeric):
            raise ValueError("SCENARIO_VALUE_NOT_FINITE")
        if numeric < control["minimum"] or numeric > control["maximum"]:
            raise ValueError("SCENARIO_VALUE_OUTSIDE_OBSERVED_RANGE")
        return numeric
    text = str(value)
    if text not in control["options"]:
        raise ValueError("SCENARIO_CATEGORY_NOT_AVAILABLE")
    return text


def _curve_shape(inputs, outputs, kind: str) -> str:
    if kind != "numeric" or len(outputs) < 3:
        return "categorical"
    x = np.asarray(inputs, dtype=float)
    y = np.asarray(outputs, dtype=float)
    span = float(np.ptp(y))
    tolerance = max(1e-9, float(np.max(np.abs(y))) * 1e-9)
    if span <= tolerance:
        return "flat"
    fitted = np.polyval(np.polyfit(x, y, 1), x)
    residual = float(np.sum((y - fitted) ** 2))
    total = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = 1.0 - residual / total if total > 0 else 1.0
    return "approximately_linear" if r_squared >= 0.999 else "nonlinear"


def _sensitivity_direction(outputs, kind: str) -> str:
    if kind != "numeric" or len(outputs) < 2:
        return "categorical"
    y = np.asarray(outputs, dtype=float)
    tolerance = max(1e-9, float(np.max(np.abs(y))) * 1e-9)
    differences = np.diff(y)
    has_increase = bool(np.any(differences > tolerance))
    has_decrease = bool(np.any(differences < -tolerance))
    if not has_increase and not has_decrease:
        return "flat"
    if has_increase and not has_decrease:
        return "increasing"
    if has_decrease and not has_increase:
        return "decreasing"
    return "mixed"


@lru_cache(maxsize=4)
def load_scenario_bundle(path: str, expected_sha256: str) -> dict:
    source = Path(path)
    if not source.is_file() or _sha256(source) != expected_sha256:
        raise ValueError("SCENARIO_ARTIFACT_INTEGRITY_ERROR")
    return joblib.load(source)


def clear_scenario_cache() -> None:
    load_scenario_bundle.cache_clear()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_value(value):
    return value.item() if isinstance(value, np.generic) else value
