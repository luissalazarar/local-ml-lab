from __future__ import annotations

import math
import signal
import time
from contextlib import contextmanager
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer, make_column_selector
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import (
    GroupKFold,
    GroupShuffleSplit,
    LeaveOneOut,
    StratifiedGroupKFold,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from local_ml_lab import __version__

from .forecasting import fit_predict as forecast_fit_predict
from .forecasting import specs as forecast_specs
from .metrics import (
    classification_diagnostics,
    classification_metrics,
    distribution,
    regression_metrics,
)
from .planning import exact_row_groups, freeze_plan, materialize_splits, stable_row_ids, stable_seed
from .registry import ModelSpec, specs
from .selection import select_candidate

SUPPORTED_PRIMARY = {
    "regression": {"mae": "min", "rmse": "min", "r2": "max"},
    "classification": {
        "balanced_accuracy": "max",
        "accuracy": "max",
        "macro_f1": "max",
    },
    "forecasting": {"mae": "min", "rmse": "min"},
}
DEFAULT_PRIMARY = {
    "regression": "mae",
    "classification": "balanced_accuracy",
    "forecasting": "mae",
}
TERMINAL_CANDIDATE_STATES = {"completed", "ineligible", "failed", "timeout", "cancelled"}


class FitTimedOut(TimeoutError):
    pass


class FeatureLimitGuard(BaseEstimator, TransformerMixin):
    def __init__(self, max_features=5000, max_dense_bytes=64 * 1024 * 1024):
        self.max_features = max_features
        self.max_dense_bytes = max_dense_bytes

    def fit(self, values, y=None):
        if values.shape[1] > self.max_features:
            raise ValueError("TRANSFORMED_FEATURE_LIMIT_EXCEEDED")
        if not sparse.issparse(values) and getattr(values, "nbytes", 0) > self.max_dense_bytes:
            raise ValueError("DENSE_MATRIX_LIMIT_EXCEEDED")
        self.n_features_in_ = values.shape[1]
        return self

    def transform(self, values):
        if values.shape[1] != self.n_features_in_:
            raise ValueError("TRANSFORMED_FEATURE_SHAPE_CHANGED")
        if not sparse.issparse(values) and getattr(values, "nbytes", 0) > self.max_dense_bytes:
            raise ValueError("DENSE_MATRIX_LIMIT_EXCEEDED")
        return values


@contextmanager
def fit_deadline(seconds: int):
    if not hasattr(signal, "SIGALRM") or seconds <= 0:
        yield
        return
    previous_handler = signal.getsignal(signal.SIGALRM)

    def timed_out(signum, frame):
        raise FitTimedOut("FIT_TIMEOUT")

    signal.signal(signal.SIGALRM, timed_out)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _publish(progress, event_type, stage, message_code, completed=0, total=None, **payload):
    event = {
        "event_version": "1.0",
        "event_type": event_type,
        "stage": stage,
        "message_code": message_code,
        "completed_units": completed,
        "total_units": total,
        **payload,
    }
    try:
        progress(event)
    except TypeError:
        progress(stage, message_code, completed, total)


def analyze(frame: pd.DataFrame, profile: dict, config: dict, progress=lambda *_: None) -> dict:
    problem = config["problem_type"]
    if problem == "exploration":
        return exploration_result(profile, config)
    primary_metric = resolve_primary_metric(problem, config.get("primary_metric"))
    if config.get("validation_context", "independent_records") != "independent_records":
        raise ValueError("UNSUPPORTED_VALIDATION_CONTEXT")
    if problem == "forecasting":
        return forecast_result(frame, profile, config, progress, primary_metric)
    return tabular_result(frame, profile, config, progress, primary_metric)


def tabular_result(frame, profile, config, progress, primary_metric):
    started = time.monotonic()
    problem = config["problem_type"]
    target = config.get("target_column_id")
    if not target or target not in frame:
        raise ValueError("TARGET_REQUIRED")
    usable = frame.loc[frame[target].notna()].copy()
    target_missing = int(len(frame) - len(usable))
    y = usable[target].copy()
    if problem == "regression":
        numeric = pd.to_numeric(y, errors="coerce")
        valid = numeric.notna()
        target_missing += int((~valid).sum())
        usable, y = usable.loc[valid].copy(), numeric.loc[valid]
    if target_missing:
        preparation = config.setdefault("_preparation", {})
        preparation["target_missing_rows"] = target_missing
        preparation["target_missing_note"] = (
            "Filas sin resultado válido apartadas para este análisis; el dataset original no cambió."
        )
    if len(y) < 2:
        return not_evaluable(profile, config, "INSUFFICIENT_ROWS", primary_metric)
    if problem == "classification":
        counts = y.astype(str).value_counts()
        if len(counts) < 2 or counts.min() < 2:
            return not_evaluable(profile, config, "CLASS_SUPPORT_INSUFFICIENT", primary_metric)
        y = y.astype(str)
        class_labels = sorted(y.unique().tolist())
    else:
        class_labels = None

    features = resolve_features(usable.columns, target, profile, config)
    x = usable[features].copy()
    row_ids = stable_row_ids(usable.index)
    groups = np.asarray(exact_row_groups(usable), dtype=object)
    root_seed = int(config.get("seed", 42))
    development, holdout, holdout_reason = reserve_tabular_holdout(y, groups, problem, root_seed)
    x_dev, y_dev, groups_dev = (
        x.iloc[development].reset_index(drop=True),
        y.iloc[development].reset_index(drop=True),
        groups[development],
    )
    dev_row_ids = [row_ids[int(index)] for index in development]
    splits, split_strategy, split_note = tabular_splits(y_dev, groups_dev, problem, root_seed)
    if not splits:
        return not_evaluable(profile, config, "NO_VALID_SPLIT_PLAN", primary_metric)

    candidate_specs = specs(problem, config.get("depth", "quick"), primary_metric)
    shortest_train = min(len(train) for train, _ in splits)
    candidates_plan = []
    eligible_specs = []
    reference_only = problem == "regression" and len(y_dev) <= 3
    for spec in candidate_specs:
        reason = candidate_ineligibility(spec, features, shortest_train, reference_only)
        planned = {**spec.public(), "eligible": reason is None, "ineligibility_reason": reason}
        candidates_plan.append(planned)
        if reason is None:
            eligible_specs.append(spec)
    plan_units = materialize_splits(splits, dev_row_ids)
    total_units = len(splits) * len(eligible_specs)
    plan = freeze_plan(
        {
            "prepared_dataset_version_id": config.get("dataset_version_id"),
            "objective": config["goal"],
            "problem_type": problem,
            "target_column_id": target,
            "included_column_ids": features,
            "units": "target_unit" if problem == "regression" else "class_label",
            "eligible_population": {
                "row_ids": dev_row_ids,
                "row_count": len(dev_row_ids),
                "excluded_target_rows": target_missing,
                "exact_duplicate_blocks": len(set(groups_dev)),
            },
            "class_universe": class_labels,
            "validation": {
                "strategy": split_strategy,
                "units": plan_units,
                "holdout_row_ids": [row_ids[int(index)] for index in holdout],
                "holdout_reason": holdout_reason,
                "note": split_note,
            },
            "candidates": candidates_plan,
            "primary_metric": primary_metric,
            "metric_direction": SUPPORTED_PRIMARY[problem][primary_metric],
            "baseline_candidate_id": eligible_specs[0].model_id if eligible_specs else None,
            "budgets": analysis_budgets(config.get("depth", "quick")),
            "root_seed": root_seed,
            "derived_seeds": {
                spec.model_id: {
                    unit["unit_id"]: stable_seed(root_seed, spec.model_id, unit["unit_id"])
                    for unit in plan_units
                }
                for spec in eligible_specs
            },
        }
    )
    _publish(
        progress,
        "plan_ready",
        "prepare",
        "PLAN_READY",
        0,
        total_units,
        plan_summary=plan_summary(plan),
        plan_sha256=plan["plan_sha256"],
    )
    candidates = []
    prediction_sets = {}
    completed_units = 0
    budget = analysis_budgets(config.get("depth", "quick"))
    for spec, planned in zip(candidate_specs, candidates_plan, strict=True):
        if not planned["eligible"]:
            candidate = candidate_shell(spec, "ineligible")
            candidate["reason_code"] = planned["ineligibility_reason"]
            candidates.append(candidate)
            _publish(
                progress,
                "candidate_skipped",
                "fit",
                planned["ineligibility_reason"],
                completed_units,
                total_units,
                candidate_id=spec.model_id,
            )
            continue
        if time.monotonic() - started > budget["selection_seconds"]:
            candidate = candidate_shell(spec, "timeout")
            candidate["reason_code"] = "SELECTION_BUDGET_EXHAUSTED"
            candidates.append(candidate)
            _publish(
                progress,
                "candidate_failed",
                "fit",
                "SELECTION_BUDGET_EXHAUSTED",
                completed_units,
                total_units,
                candidate_id=spec.model_id,
            )
            continue
        _publish(
            progress,
            "candidate_started",
            "fit",
            "CANDIDATE_STARTED",
            completed_units,
            total_units,
            candidate_id=spec.model_id,
            display_name=spec.display_name,
        )
        candidate, evidence = evaluate_tabular_candidate(
            spec,
            x_dev,
            y_dev,
            splits,
            plan_units,
            problem,
            primary_metric,
            class_labels,
            root_seed,
            budget["fit_seconds"],
            progress,
            completed_units,
            total_units,
        )
        completed_units += candidate["completed_unit_count"]
        candidates.append(candidate)
        prediction_sets[spec.model_id] = evidence
        event_type = (
            "candidate_completed" if candidate["status"] == "completed" else "candidate_failed"
        )
        _publish(
            progress,
            event_type,
            "fit",
            candidate.get("reason_code") or "CANDIDATE_COMPLETED",
            completed_units,
            total_units,
            candidate_id=spec.model_id,
            candidate=candidate_live_summary(candidate),
        )
    complete = [candidate for candidate in candidates if candidate["status"] == "completed"]
    if not complete:
        return not_evaluable(
            profile, config, "ALL_CANDIDATES_FAILED", primary_metric, candidates, plan
        )
    baseline_id = eligible_specs[0].model_id
    direction = SUPPORTED_PRIMARY[problem][primary_metric]
    target_scale = (
        float(np.max(np.abs(np.asarray(y_dev, dtype=float)))) if problem == "regression" else 1.0
    )
    decision = select_candidate(
        candidates, baseline_id, primary_metric, direction, target_scale=target_scale
    )
    selected_id = decision["selected_candidate_id"]
    selected = next(
        candidate for candidate in candidates if candidate["candidate_id"] == selected_id
    )
    selected_spec = next(spec for spec in candidate_specs if spec.model_id == selected_id)
    _publish(
        progress,
        "selection_completed",
        "compare",
        decision["reason_code"],
        completed_units,
        total_units,
        selection_decision=decision,
    )

    final_test = None
    test_predictions = []
    if len(holdout):
        final_test, test_predictions = evaluate_tabular_holdout(
            selected_spec,
            candidate_specs[0],
            x,
            y,
            development,
            holdout,
            row_ids,
            problem,
            primary_metric,
            class_labels,
            root_seed,
            budget["fit_seconds"],
        )
        _publish(
            progress,
            "final_test_completed",
            "evaluate",
            "FINAL_TEST_COMPLETED",
            completed_units,
            total_units,
            final_test=final_test,
        )
    drivers, explanation_scope = fold_permutation_importance(
        x_dev,
        y_dev,
        features,
        splits,
        selected_spec,
        problem,
        primary_metric,
        root_seed,
        progress,
    )
    selected_evidence = prediction_sets[selected_id]
    predictions = [
        prediction_row(
            evidence,
            target,
            column_name(profile, target),
            problem,
            selected_id,
            "selection_oof",
        )
        for evidence in sorted(selected_evidence, key=lambda item: item["position"])
    ] + test_predictions
    diagnostics = (
        classification_diagnostics(
            [item["actual"] for item in selected_evidence],
            [item["predicted"] for item in selected_evidence],
            class_labels,
        )
        if problem == "classification"
        else {}
    )
    if (
        problem == "classification"
        and primary_metric == "accuracy"
        and any(item["recall"] == 0 for item in diagnostics.get("per_class", []))
    ):
        diagnostics["warnings"] = ["CLASS_WITH_ZERO_RECALL"]
    result = build_result(
        profile,
        config,
        plan,
        candidates,
        selected,
        predictions,
        drivers,
        decision,
        split_strategy,
        primary_metric,
        diagnostics,
        final_test,
        explanation_scope,
        started,
    )
    _publish(
        progress,
        "snapshot_frozen",
        "freeze_result",
        "SNAPSHOT_FROZEN",
        total_units,
        total_units,
        result_summary={
            "selected_candidate_id": selected_id,
            "best_observed_candidate_id": decision["best_observed_candidate_id"],
        },
    )
    return result


def reserve_tabular_holdout(y, groups, problem, seed):
    indices = np.arange(len(y))
    if len(y) < 200:
        return indices, np.asarray([], dtype=int), "INSUFFICIENT_SUPPORT"
    if problem == "regression":
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
        development, test = next(splitter.split(indices, groups=groups))
        if len(test) >= 40 and len(development) >= 100:
            return development, test, None
        return indices, np.asarray([], dtype=int), "SUPPORT_REQUIREMENTS_NOT_MET"
    counts = pd.Series(y).value_counts()
    if counts.min() < 25:
        return indices, np.asarray([], dtype=int), "CLASS_SUPPORT_REQUIREMENTS_NOT_MET"
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    development, test = next(splitter.split(indices, y, groups))
    dev_counts = pd.Series(y.iloc[development]).value_counts()
    test_counts = pd.Series(y.iloc[test]).value_counts()
    if dev_counts.min() >= 10 and test_counts.min() >= 5:
        return development, test, None
    return indices, np.asarray([], dtype=int), "CLASS_SUPPORT_REQUIREMENTS_NOT_MET"


def tabular_splits(y, groups, problem, seed):
    n = len(y)
    if problem == "regression":
        if n <= 3:
            raw = list(LeaveOneOut().split(np.arange(n)))
            strategy = "leave_one_out_references"
        else:
            k = min(3, n // 2) if n < 10 else 5
            k = min(k, len(set(groups)))
            if k < 2:
                return [], "group_kfold", "INSUFFICIENT_DUPLICATE_BLOCKS"
            raw = list(
                GroupKFold(n_splits=k, shuffle=True, random_state=seed).split(
                    np.arange(n), groups=groups
                )
            )
            strategy = f"group_kfold_{k}"
        return [(np.asarray(a), np.asarray(b)) for a, b in raw], strategy, None
    minimum = int(pd.Series(y).value_counts().min())
    requested = min(5, minimum)
    for k in range(requested, 1, -1):
        splitter = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
        raw = list(splitter.split(np.arange(n), y, groups))
        if all(
            len(set(y.iloc[train])) == len(set(y))
            and len(set(y.iloc[validation])) == len(set(y))
            and not (set(groups[train]) & set(groups[validation]))
            for train, validation in raw
        ):
            note = None if k == requested else f"FOLDS_REDUCED_FOR_FEASIBILITY:{requested}->{k}"
            return (
                [(np.asarray(a), np.asarray(b)) for a, b in raw],
                f"stratified_group_kfold_{k}",
                note,
            )
    return [], "stratified_group_kfold", "NO_FEASIBLE_CLASS_SPLITS"


def candidate_ineligibility(spec, features, shortest_train, reference_only):
    if reference_only and spec.uses_features:
        return "ONLY_REFERENCE_RECOMMENDED_FOR_TINY_SAMPLE"
    if not features and spec.uses_features:
        return "NO_FEATURES_SELECTED"
    minimum = int(spec.fit_requirements.get("minimum_train_rows", 1))
    if shortest_train < minimum:
        return f"NEEDS_{minimum}_TRAIN_ROWS;SHORTEST_HAS_{shortest_train}"
    return None


def evaluate_tabular_candidate(
    spec,
    x,
    y,
    splits,
    units,
    problem,
    primary_metric,
    class_labels,
    root_seed,
    fit_seconds,
    progress,
    completed_before,
    total_units,
):
    candidate = candidate_shell(spec, "running")
    evidence = []
    unit_metrics = []
    try:
        for unit_index, ((train, validation), unit) in enumerate(
            zip(splits, units, strict=True), 1
        ):
            _publish(
                progress,
                "unit_started",
                "fit",
                "UNIT_STARTED",
                completed_before + unit_index - 1,
                total_units,
                candidate_id=spec.model_id,
                unit_id=unit["unit_id"],
                evaluation_role="selection",
            )
            seed = stable_seed(root_seed, spec.model_id, unit["unit_id"])
            with fit_deadline(fit_seconds):
                predicted = fit_tabular(
                    spec, x.iloc[train], y.iloc[train], x.iloc[validation], seed, problem
                )
            actual = y.iloc[validation].to_numpy()
            validate_tabular_predictions(actual, predicted, problem, class_labels)
            metrics = metric_set(problem, actual, predicted, unit["unit_id"], class_labels)
            primary = metric_value(metrics, primary_metric)
            unit_metrics.append(
                {
                    "unit_id": unit["unit_id"],
                    "primary_metric_id": primary_metric,
                    "primary_value": primary,
                    "metrics": metrics,
                    "n_predictions": len(validation),
                    "reason_code": next(
                        (
                            metric["reason_code"]
                            for metric in metrics
                            if metric["metric_id"] == primary_metric
                        ),
                        None,
                    ),
                }
            )
            for position, actual_value, predicted_value in zip(
                validation, actual, predicted, strict=True
            ):
                evidence.append(
                    {
                        "position": int(position),
                        "row_id": units[0]["train_row_ids"][0] if False else None,
                        "actual": json_value(actual_value),
                        "predicted": json_value(predicted_value),
                        "unit_id": unit["unit_id"],
                    }
                )
            # row ids are materialized in the plan; map validation order without relying on a filtered index.
            for item, row_id in zip(
                evidence[-len(validation) :], unit["validation_row_ids"], strict=True
            ):
                item["row_id"] = row_id
            cumulative_metrics = metric_set(
                problem,
                [item["actual"] for item in evidence],
                [item["predicted"] for item in evidence],
                "selection_partial",
                class_labels,
            )
            _publish(
                progress,
                "unit_completed",
                "evaluate",
                "UNIT_COMPLETED",
                completed_before + unit_index,
                total_units,
                candidate_id=spec.model_id,
                unit_id=unit["unit_id"],
                evaluation_role="selection",
                partial_metrics=cumulative_metrics,
                unit_metrics=metrics,
                preview=evidence[-min(200, len(validation)) :],
            )
        combined = metric_set(
            problem,
            [item["actual"] for item in evidence],
            [item["predicted"] for item in evidence],
            "selection_oof",
            class_labels,
        )
        primary = metric_value(combined, primary_metric)
        candidate.update(
            {
                "status": "completed",
                "eligible_for_selection": primary is not None,
                "primary_metric_id": primary_metric,
                "selection_metrics": combined,
                "primary_value": primary,
                "unit_metrics": unit_metrics,
                "unit_summary": distribution(
                    [
                        unit["primary_value"]
                        for unit in unit_metrics
                        if unit["primary_value"] is not None
                    ]
                ),
                "completed_unit_count": len(unit_metrics),
                "planned_unit_count": len(splits),
                "n_predictions": len(evidence),
                "n_unique_observations": len({item["row_id"] for item in evidence}),
            }
        )
    except FitTimedOut:
        candidate.update(
            {
                "status": "timeout",
                "eligible_for_selection": False,
                "reason_code": "FIT_TIMEOUT",
                "unit_metrics": unit_metrics,
                "completed_unit_count": len(unit_metrics),
                "planned_unit_count": len(splits),
            }
        )
    except Exception as exc:
        candidate.update(
            {
                "status": "failed",
                "eligible_for_selection": False,
                "reason_code": type(exc).__name__,
                "failure_detail": str(exc)[:240],
                "unit_metrics": unit_metrics,
                "completed_unit_count": len(unit_metrics),
                "planned_unit_count": len(splits),
            }
        )
    return candidate, evidence


def fit_tabular(spec, train_x, train_y, validation_x, seed, problem):
    if not spec.uses_features:
        if problem == "regression":
            strategy = spec.parameters["strategy"]
            center = float(np.median(train_y)) if strategy == "median" else float(np.mean(train_y))
            return np.repeat(center, len(validation_x))
        counts = pd.Series(train_y).value_counts()
        most_frequent = sorted(counts[counts == counts.max()].index.astype(str).tolist())[0]
        return np.asarray([most_frequent] * len(validation_x), dtype=object)
    pipeline = make_pipeline(spec, seed)
    pipeline.fit(train_x, train_y)
    return np.asarray(pipeline.predict(validation_x))


def build_transformer(scale_numeric=True):
    numeric_steps = [("impute", SimpleImputer(strategy="median", add_indicator=True))]
    if scale_numeric:
        numeric_steps.append(("scale", StandardScaler()))
    return ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(numeric_steps),
                make_column_selector(dtype_include=np.number),
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "encode",
                            OneHotEncoder(
                                handle_unknown="infrequent_if_exist",
                                min_frequency=2,
                                max_categories=1000,
                            ),
                        ),
                    ]
                ),
                make_column_selector(dtype_exclude=np.number),
            ),
        ],
        remainder="drop",
    )


def make_pipeline(spec: ModelSpec, seed: int):
    return Pipeline(
        [
            ("prepare", build_transformer(spec.scale_numeric)),
            ("drop_constant", VarianceThreshold()),
            ("limits", FeatureLimitGuard()),
            ("model", spec.build(seed)),
        ]
    )


def validate_tabular_predictions(actual, predicted, problem, class_labels):
    if np.asarray(predicted).shape != np.asarray(actual).shape:
        raise ValueError("PREDICTION_SHAPE_MISMATCH")
    if problem == "regression":
        if not np.isfinite(np.asarray(predicted, dtype=float)).all():
            raise ValueError("NON_FINITE_PREDICTION")
    elif not set(map(str, predicted)).issubset(set(class_labels)):
        raise ValueError("PREDICTION_CLASS_OUTSIDE_UNIVERSE")


def evaluate_tabular_holdout(
    selected_spec,
    baseline_spec,
    x,
    y,
    development,
    holdout,
    row_ids,
    problem,
    primary_metric,
    class_labels,
    root_seed,
    fit_seconds,
):
    results = {}
    selected_predictions = None
    for role, spec in (("selected", selected_spec), ("baseline", baseline_spec)):
        if role == "baseline" and spec.model_id == selected_spec.model_id:
            results[role] = results["selected"]
            continue
        with fit_deadline(fit_seconds):
            predicted = fit_tabular(
                spec,
                x.iloc[development],
                y.iloc[development],
                x.iloc[holdout],
                stable_seed(root_seed, spec.model_id, "final-test"),
                problem,
            )
        actual = y.iloc[holdout].to_numpy()
        validate_tabular_predictions(actual, predicted, problem, class_labels)
        metrics = metric_set(problem, actual, predicted, "final_test", class_labels)
        results[role] = {
            "candidate_id": spec.model_id,
            "metrics": metrics,
            "primary_value": metric_value(metrics, primary_metric),
            "n_predictions": len(holdout),
        }
        if role == "selected":
            selected_predictions = predicted
    direction = SUPPORTED_PRIMARY[problem][primary_metric]
    results["selection_improvement_repeated"] = (
        results["selected"]["primary_value"] >= results["baseline"]["primary_value"]
        if direction == "max"
        else results["selected"]["primary_value"] <= results["baseline"]["primary_value"]
    )
    rows = []
    for index, actual, predicted in zip(
        holdout, y.iloc[holdout].to_numpy(), selected_predictions, strict=True
    ):
        rows.append(
            {
                "row_id": row_ids[int(index)],
                "actual": json_value(actual),
                "predicted": json_value(predicted),
                "error": (
                    json_value(float(predicted) - float(actual))
                    if problem == "regression"
                    else None
                ),
                "evaluation_role": "final_test",
                "model_id": selected_spec.model_id,
                "unit": "target_unit" if problem == "regression" else "class_label",
            }
        )
    return results, rows


def fold_permutation_importance(
    x, y, features, splits, model_spec, problem, primary_metric, seed, progress
):
    if not model_spec.uses_features:
        return [], {
            "status": "not_applicable",
            "reason": "Esta referencia no utiliza las variables para predecir.",
        }
    if not features or len(y) < 10:
        return [], {"status": "not_available", "reason_code": "INSUFFICIENT_SUPPORT"}
    started = time.monotonic()
    fold_values = []
    scoring = (
        "neg_mean_absolute_error"
        if primary_metric == "mae"
        else "neg_root_mean_squared_error"
        if primary_metric == "rmse"
        else "f1_macro"
        if primary_metric == "macro_f1"
        else primary_metric
    )
    completed = 0
    for fold, (train, validation) in enumerate(splits[:3], 1):
        if time.monotonic() - started > 60:
            break
        _publish(
            progress,
            "explanation_updated",
            "explain",
            "EXPLANATION_FOLD_STARTED",
            fold - 1,
            min(3, len(splits)),
            unit_id=f"explanation-{fold:02d}",
        )
        pipeline = make_pipeline(
            model_spec, stable_seed(seed, model_spec.model_id, f"explanation-{fold}")
        )
        pipeline.fit(x.iloc[train], y.iloc[train])
        measured = permutation_importance(
            pipeline,
            x.iloc[validation],
            y.iloc[validation],
            n_repeats=3,
            random_state=stable_seed(seed, model_spec.model_id, f"permutation-{fold}"),
            scoring=scoring,
        )
        fold_values.append(measured.importances)
        completed += 1
        _publish(
            progress,
            "explanation_updated",
            "explain",
            "EXPLANATION_FOLD_COMPLETED",
            fold,
            min(3, len(splits)),
            unit_id=f"explanation-{fold:02d}",
        )
    if not fold_values:
        return [], {"status": "not_available", "reason_code": "EXPLANATION_BUDGET_EXHAUSTED"}
    combined = np.concatenate(fold_values, axis=1)
    drivers = [
        {
            "source_column_id": column,
            "method": "permutation_importance_validation_folds",
            "importance_mean": float(combined[index].mean()),
            "importance_std": float(combined[index].std(ddof=1)) if combined.shape[1] > 1 else None,
            "repeat_count": int(combined.shape[1]),
            "fold_count": completed,
            "evaluation_sample_count": int(
                sum(len(validation) for _, validation in splits[:completed])
            ),
            "evaluation_role": "selection_validation_folds",
            "fit_scope": "fold_train_only",
            "warnings": ["PREDICTIVE_NOT_CAUSAL", "VALIDATION_ALSO_USED_FOR_SELECTION"],
        }
        for index, column in enumerate(features)
    ]
    return sorted(drivers, key=lambda driver: driver["importance_mean"], reverse=True), {
        "status": "completed" if completed == min(3, len(splits)) else "partial",
        "folds_completed": completed,
        "repetitions_per_fold": 3,
        "deterministic_sample": True,
        "used_for_selection": False,
    }


def forecast_result(frame, profile, config, progress, primary_metric):
    started = time.monotonic()
    target = config.get("target_column_id")
    date_col = config.get("date_column_id")
    if not target or not date_col or target not in frame or date_col not in frame:
        raise ValueError("FORECAST_COLUMNS_REQUIRED")
    raw = pd.DataFrame(
        {
            "date": pd.to_datetime(frame[date_col], errors="coerce"),
            "value": pd.to_numeric(frame[target], errors="coerce"),
        }
    )
    if raw["date"].isna().any() or raw["value"].isna().any():
        raise ValueError("FORECAST_INVALID_DATE_OR_VALUE")
    options = config.get("forecast_options") or {}
    horizon = int(options.get("horizon", 3))
    if not 1 <= horizon <= 24:
        raise ValueError("FORECAST_HORIZON_OUT_OF_RANGE")
    periods = raw["date"].dt.to_period("M")
    has_duplicates = periods.duplicated().any()
    aggregation = options.get("aggregation")
    if has_duplicates and aggregation not in {"sum", "mean"}:
        raise ValueError("DUPLICATE_MONTHS_REQUIRE_AGGREGATION")
    if aggregation not in {None, "sum", "mean"}:
        raise ValueError("UNSUPPORTED_FORECAST_AGGREGATION")
    data = raw.assign(period=periods).sort_values("date")
    if has_duplicates:
        data = data.groupby("period", as_index=False)["value"].agg(aggregation)
    else:
        data = data[["period", "value"]].drop_duplicates("period")
    data = data.sort_values("period").reset_index(drop=True)
    expected = pd.period_range(data["period"].iloc[0], data["period"].iloc[-1], freq="M")
    if len(expected.difference(pd.PeriodIndex(data["period"], freq="M"))):
        raise ValueError("MISSING_MONTHLY_PERIODS")
    values = data["value"].to_numpy(float)
    dates = pd.PeriodIndex(data["period"], freq="M")
    n = len(values)
    if n < horizon + 2:
        return not_evaluable(profile, config, "INSUFFICIENT_HISTORY", primary_metric)
    minimum_window = (
        36
        if n >= 36 + 3 * horizon
        else 24
        if n >= 24 + 3 * horizon
        else 12
        if n >= 12 + 3 * horizon
        else 2
    )
    has_test = n >= minimum_window + 4 * horizon
    development_count = n - horizon if has_test else n
    maximum = 3 if config.get("depth", "quick") == "quick" else 6
    k = min(maximum, math.floor((development_count - minimum_window) / horizon))
    if k < 1:
        return not_evaluable(profile, config, "NO_FORECAST_BACKTEST_ORIGIN", primary_metric)
    origins = [development_count - k * horizon + index * horizon for index in range(k)]
    forecast_catalog = forecast_specs(config.get("depth", "quick"))
    shortest_prefix = origins[0]
    candidate_plan = [
        {
            **spec.public(),
            "eligible": shortest_prefix >= spec.minimum_train_months,
            "ineligibility_reason": (
                None
                if shortest_prefix >= spec.minimum_train_months
                else f"NEEDS_{spec.minimum_train_months}_MONTHS;FIRST_PREFIX_HAS_{shortest_prefix}"
            ),
        }
        for spec in forecast_catalog
    ]
    unit_plan = [
        {
            "unit_id": f"origin-{index + 1:02d}",
            "role": "selection_backtest",
            "origin_index": origin,
            "train_periods": [str(period) for period in dates[:origin]],
            "validation_periods": [str(period) for period in dates[origin : origin + horizon]],
            "train_count": origin,
            "validation_count": horizon,
        }
        for index, origin in enumerate(origins)
    ]
    eligible_count = sum(item["eligible"] for item in candidate_plan)
    total_units = eligible_count * k
    root_seed = int(config.get("seed", 42))
    plan = freeze_plan(
        {
            "prepared_dataset_version_id": config.get("dataset_version_id"),
            "objective": config["goal"],
            "problem_type": "forecasting",
            "target_column_id": target,
            "date_column_id": date_col,
            "units": "target_unit",
            "eligible_population": {
                "periods": [str(period) for period in dates],
                "month_count": n,
                "aggregation": aggregation or "one_observation_per_month",
            },
            "forecast_horizon": horizon,
            "validation": {
                "strategy": "expanding_window_non_overlapping_targets",
                "minimum_window": minimum_window,
                "units": unit_plan,
                "reserved_test_periods": [str(period) for period in dates[-horizon:]]
                if has_test
                else [],
                "holdout_reason": None
                if has_test
                else "No se reservó una prueba final por soporte insuficiente.",
            },
            "candidates": candidate_plan,
            "primary_metric": primary_metric,
            "metric_direction": "min",
            "baseline_candidate_ids": [
                item.model_id for item in forecast_catalog if item.reference
            ],
            "budgets": analysis_budgets(config.get("depth", "quick")),
            "root_seed": root_seed,
            "derived_seeds": {},
        }
    )
    _publish(
        progress,
        "plan_ready",
        "prepare",
        "PLAN_READY",
        0,
        total_units,
        plan_summary=plan_summary(plan),
        plan_sha256=plan["plan_sha256"],
    )
    candidates = []
    prediction_sets = {}
    completed_units = 0
    for spec, planned in zip(forecast_catalog, candidate_plan, strict=True):
        if not planned["eligible"]:
            candidate = forecast_candidate_shell(spec, "ineligible")
            candidate["reason_code"] = planned["ineligibility_reason"]
            candidates.append(candidate)
            _publish(
                progress,
                "candidate_skipped",
                "fit",
                planned["ineligibility_reason"],
                completed_units,
                total_units,
                candidate_id=spec.model_id,
            )
            continue
        _publish(
            progress,
            "candidate_started",
            "fit",
            "CANDIDATE_STARTED",
            completed_units,
            total_units,
            candidate_id=spec.model_id,
            display_name=spec.display_name,
        )
        candidate = forecast_candidate_shell(spec, "running")
        evidence = []
        units = []
        try:
            for unit_index, (origin, unit) in enumerate(zip(origins, unit_plan, strict=True), 1):
                _publish(
                    progress,
                    "unit_started",
                    "fit",
                    "FORECAST_ORIGIN_STARTED",
                    completed_units + unit_index - 1,
                    total_units,
                    candidate_id=spec.model_id,
                    unit_id=unit["unit_id"],
                    evaluation_role="selection_backtest",
                )
                future_dates = dates[origin : origin + horizon]
                with fit_deadline(analysis_budgets(config.get("depth", "quick"))["fit_seconds"]):
                    predicted = forecast_fit_predict(
                        spec, values[:origin], dates[:origin], future_dates, options
                    )
                actual = values[origin : origin + horizon]
                metrics = regression_metrics(actual, predicted, unit["unit_id"])
                primary = metric_value(metrics, primary_metric)
                unit_evidence = []
                for step, (period, actual_value, predicted_value) in enumerate(
                    zip(future_dates, actual, predicted, strict=True), 1
                ):
                    item = {
                        "record_id": f"{spec.model_id}-{unit['unit_id']}-{step:02d}",
                        "unit_id": unit["unit_id"],
                        "origin_period": str(dates[origin - 1]),
                        "target_period": period.to_timestamp().date().isoformat(),
                        "horizon": step,
                        "actual": float(actual_value),
                        "predicted": float(predicted_value),
                        "error": float(predicted_value - actual_value),
                    }
                    evidence.append(item)
                    unit_evidence.append(item)
                units.append(
                    {
                        "unit_id": unit["unit_id"],
                        "primary_metric_id": primary_metric,
                        "primary_value": primary,
                        "metrics": metrics,
                        "n_predictions": horizon,
                    }
                )
                cumulative = regression_metrics(
                    [item["actual"] for item in evidence],
                    [item["predicted"] for item in evidence],
                    "selection_backtest_partial",
                )
                _publish(
                    progress,
                    "unit_completed",
                    "evaluate",
                    "FORECAST_ORIGIN_COMPLETED",
                    completed_units + unit_index,
                    total_units,
                    candidate_id=spec.model_id,
                    unit_id=unit["unit_id"],
                    evaluation_role="selection_backtest",
                    partial_metrics=cumulative,
                    unit_metrics=metrics,
                    preview=unit_evidence,
                    training_end=str(dates[origin - 1]),
                )
            combined = regression_metrics(
                [item["actual"] for item in evidence],
                [item["predicted"] for item in evidence],
                "selection_backtest",
            )
            candidate.update(
                {
                    "status": "completed",
                    "eligible_for_selection": True,
                    "primary_metric_id": primary_metric,
                    "selection_metrics": combined,
                    "primary_value": metric_value(combined, primary_metric),
                    "unit_metrics": units,
                    "unit_summary": distribution([unit["primary_value"] for unit in units]),
                    "completed_unit_count": len(units),
                    "planned_unit_count": k,
                    "n_predictions": len(evidence),
                    "n_unique_observations": len({item["target_period"] for item in evidence}),
                }
            )
        except FitTimedOut:
            candidate.update(
                {
                    "status": "timeout",
                    "eligible_for_selection": False,
                    "reason_code": "FIT_TIMEOUT",
                    "unit_metrics": units,
                    "completed_unit_count": len(units),
                    "planned_unit_count": k,
                }
            )
        except Exception as exc:
            candidate.update(
                {
                    "status": "failed",
                    "eligible_for_selection": False,
                    "reason_code": type(exc).__name__,
                    "failure_detail": str(exc)[:240],
                    "unit_metrics": units,
                    "completed_unit_count": len(units),
                    "planned_unit_count": k,
                }
            )
        completed_units += candidate["completed_unit_count"]
        candidates.append(candidate)
        prediction_sets[spec.model_id] = evidence
        _publish(
            progress,
            "candidate_completed" if candidate["status"] == "completed" else "candidate_failed",
            "fit",
            candidate.get("reason_code") or "CANDIDATE_COMPLETED",
            completed_units,
            total_units,
            candidate_id=spec.model_id,
            candidate=candidate_live_summary(candidate),
        )
    complete = [item for item in candidates if item["status"] == "completed"]
    references = [
        item
        for item in complete
        if next(spec for spec in forecast_catalog if spec.model_id == item["model_id"]).reference
    ]
    if not references:
        return not_evaluable(
            profile, config, "NO_FORECAST_REFERENCE_COMPLETED", primary_metric, candidates, plan
        )
    baseline = sorted(
        references,
        key=lambda item: (item["primary_value"], item["complexity_rank"], item["candidate_id"]),
    )[0]
    target_scale = float(np.max(np.abs(values[:development_count]))) if development_count else 1.0
    decision = select_candidate(
        candidates,
        baseline["candidate_id"],
        primary_metric,
        "min",
        target_scale=target_scale,
        methodology_blocked=k < 3,
    )
    selected_id = decision["selected_candidate_id"]
    selected = next(item for item in candidates if item["candidate_id"] == selected_id)
    selected_spec = next(item for item in forecast_catalog if item.model_id == selected_id)
    baseline_spec = next(
        item for item in forecast_catalog if item.model_id == baseline["candidate_id"]
    )
    _publish(
        progress,
        "selection_completed",
        "compare",
        decision["reason_code"],
        completed_units,
        total_units,
        selection_decision=decision,
    )
    final_test = None
    final_test_rows = []
    if has_test:
        actual = values[development_count:]
        selected_pred = forecast_fit_predict(
            selected_spec,
            values[:development_count],
            dates[:development_count],
            dates[development_count:],
            options,
        )
        baseline_pred = (
            selected_pred
            if baseline_spec.model_id == selected_spec.model_id
            else forecast_fit_predict(
                baseline_spec,
                values[:development_count],
                dates[:development_count],
                dates[development_count:],
                options,
            )
        )
        selected_metrics = regression_metrics(actual, selected_pred, "final_test")
        baseline_metrics = regression_metrics(actual, baseline_pred, "final_test")
        final_test = {
            "selected": {
                "candidate_id": selected_id,
                "metrics": selected_metrics,
                "primary_value": metric_value(selected_metrics, primary_metric),
            },
            "baseline": {
                "candidate_id": baseline_spec.model_id,
                "metrics": baseline_metrics,
                "primary_value": metric_value(baseline_metrics, primary_metric),
            },
        }
        final_test["selection_improvement_repeated"] = (
            final_test["selected"]["primary_value"] <= final_test["baseline"]["primary_value"]
        )
        for step, (period, actual_value, predicted_value) in enumerate(
            zip(dates[development_count:], actual, selected_pred, strict=True), 1
        ):
            final_test_rows.append(
                {
                    "record_id": f"final-test-{step:02d}",
                    "actual": float(actual_value),
                    "predicted": float(predicted_value),
                    "error": float(predicted_value - actual_value),
                    "evaluation_role": "final_test",
                    "horizon": step,
                    "target_period": period.to_timestamp().date().isoformat(),
                    "unit": "target_unit",
                    "model_id": selected_id,
                }
            )
        _publish(
            progress,
            "final_test_completed",
            "evaluate",
            "FINAL_TEST_COMPLETED",
            completed_units,
            total_units,
            final_test=final_test,
        )
    future_dates = pd.period_range(dates[-1] + 1, periods=horizon, freq="M")
    forecast_failure = None
    fallback_candidate_id = None
    try:
        future = forecast_fit_predict(selected_spec, values, dates, future_dates, options)
    except Exception as exc:
        forecast_failure = {"reason_code": type(exc).__name__, "detail": str(exc)[:240]}
        fallback_candidate_id = baseline_spec.model_id
        future = forecast_fit_predict(baseline_spec, values, dates, future_dates, options)
    iqr = float(np.subtract(*np.percentile(values, [75, 25])))
    scale_epsilon = max(1e-12, float(np.max(np.abs(values))) * 1e-12)
    excursion = 3 * max(iqr, scale_epsilon)
    extrapolation_periods = [
        future_dates[index].to_timestamp().date().isoformat()
        for index, value in enumerate(future)
        if value < float(np.min(values)) - excursion or value > float(np.max(values)) + excursion
    ]
    _publish(
        progress,
        "forecast_ready",
        "evaluate",
        "FORECAST_READY",
        completed_units,
        total_units,
        candidate_id=selected_id,
        fallback_candidate_id=fallback_candidate_id,
    )
    history_rows = [
        {
            "record_id": f"history-{index:04d}",
            "actual": float(value),
            "predicted": None,
            "error": None,
            "evaluation_role": "history",
            "target_period": period.to_timestamp().date().isoformat(),
            "unit": "target_unit",
        }
        for index, (period, value) in enumerate(zip(dates, values, strict=True), 1)
    ]
    selection_rows = [
        {
            **item,
            "evaluation_role": "selection_backtest",
            "unit": "target_unit",
            "model_id": selected_id,
        }
        for item in prediction_sets[selected_id]
    ]
    future_rows = [
        {
            "record_id": f"future-{index:02d}",
            "actual": None,
            "predicted": float(value),
            "error": None,
            "evaluation_role": "forecast_future",
            "horizon": index,
            "target_period": period.to_timestamp().date().isoformat(),
            "unit": "target_unit",
            "model_id": fallback_candidate_id or selected_id,
        }
        for index, (period, value) in enumerate(zip(future_dates, future, strict=True), 1)
    ]
    diagnostics = {
        "frequency": "monthly",
        "aggregation": aggregation or "one_observation_per_month",
        "missing_period_count": 0,
        "backtest_origin_count": k,
        "forecast_extrapolation": {
            "policy_version": "forecast-extrapolation-1.0",
            "threshold": excursion,
            "periods": extrapolation_periods,
            "descriptive_only": True,
        },
        "forecast_generation_failure": forecast_failure,
        "technical_fallback_candidate_id": fallback_candidate_id,
    }
    result = build_result(
        profile,
        config,
        plan,
        candidates,
        selected,
        history_rows + selection_rows + final_test_rows + future_rows,
        [],
        decision,
        "expanding_window_non_overlapping_targets",
        primary_metric,
        diagnostics,
        final_test,
        {
            "status": "not_applicable",
            "reason": "La importancia por permutación corresponde a modelos tabulares, no a este pronóstico.",
        },
        started,
    )
    result["uncertainty"] = {
        "available": False,
        "reason_code": "UNCERTAINTY_BANDS_OUT_OF_SCOPE",
    }
    result["forecast"] = {
        "selected_candidate_id": selected_id,
        "generated_by_candidate_id": fallback_candidate_id or selected_id,
        "horizon": horizon,
        "future_period_count": len(future_rows),
        "failure": forecast_failure,
    }
    _publish(
        progress,
        "snapshot_frozen",
        "freeze_result",
        "SNAPSHOT_FROZEN",
        total_units,
        total_units,
        result_summary={"selected_candidate_id": selected_id},
    )
    return result


def candidate_shell(spec, status):
    return {
        **spec.public(),
        "status": status,
        "eligible_for_selection": False,
        "primary_metric_id": None,
        "primary_value": None,
        "selection_metrics": [],
        "unit_metrics": [],
        "completed_unit_count": 0,
        "planned_unit_count": 0,
    }


def forecast_candidate_shell(spec, status):
    return {
        **spec.public(),
        "status": status,
        "eligible_for_selection": False,
        "primary_metric_id": None,
        "primary_value": None,
        "selection_metrics": [],
        "unit_metrics": [],
        "completed_unit_count": 0,
        "planned_unit_count": 0,
    }


def candidate_live_summary(candidate):
    return {
        key: candidate.get(key)
        for key in (
            "candidate_id",
            "model_id",
            "display_name",
            "status",
            "eligible_for_selection",
            "primary_metric_id",
            "primary_value",
            "complexity_rank",
            "completed_unit_count",
            "planned_unit_count",
            "reason_code",
        )
    }


def prediction_row(item, target, target_name, problem, model_id, role):
    return {
        "row_id": item["row_id"],
        "actual": item["actual"],
        "predicted": item["predicted"],
        "error": (
            json_value(float(item["predicted"]) - float(item["actual"]))
            if problem == "regression"
            else None
        ),
        "evaluation_role": role,
        "unit_id": item["unit_id"],
        "model_id": model_id,
        "target_column_id": target,
        "target_name": target_name,
        "unit": "target_unit" if problem == "regression" else "class_label",
    }


def build_result(
    profile,
    config,
    plan,
    candidates,
    selected,
    predictions,
    drivers,
    decision,
    evidence,
    primary_metric,
    diagnostics=None,
    final_test=None,
    explanation_scope=None,
    started=None,
):
    baseline_id = decision["baseline_candidate_id"]
    baseline = next(item for item in candidates if item["candidate_id"] == baseline_id)
    selected_is_baseline = selected["candidate_id"] == baseline_id
    utility = "reference_preferred" if selected_is_baseline else "practical_consistent_improvement"
    limitations = [
        "La importancia predictiva no demuestra causalidad.",
        "Los umbrales de selección son decisiones del producto, no pruebas de significancia estadística.",
    ]
    if not final_test:
        limitations.append(
            "La misma validación participó en la selección del modelo; no es una prueba final independiente."
        )
    if config["problem_type"] in {"regression", "classification"}:
        limitations.append(
            "La validación aleatoria solo es adecuada para registros independientes; grupos, entidades repetidas y usos temporales no están soportados."
        )
    else:
        limitations.append(
            "El alcance de forecasting es una sola serie mensual regular y sin bandas de incertidumbre."
        )
    if profile.get("duplicate_count", 0):
        limitations.append(
            "Las filas exactamente duplicadas se conservaron y se mantuvieron juntas al partir los datos."
        )
    if final_test and not final_test.get("selection_improvement_repeated", True):
        limitations.append("La mejora de selección no se repitió en la prueba reservada.")
    reasons = [
        "La confiabilidad describe el modo y cobertura de la evidencia; no es una probabilidad."
    ]
    if len(selected.get("unit_metrics", [])) < 3:
        reasons.append("Hay menos de tres comparaciones por unidad para respaldar consistencia.")
    return {
        "schema_version": "2.0",
        "engine_version": __version__,
        "goal": config["goal"],
        "problem_type": config["problem_type"],
        "primary_metric_id": primary_metric,
        "dataset_summary": {
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
        },
        "requested_config": config,
        "resolved_config": {**config, "primary_metric": primary_metric},
        "data_quality": profile,
        "data_preparation": config.get("_preparation", {}),
        "analysis_plan": plan,
        "plan_sha256": plan["plan_sha256"],
        "validation_plan": {
            **plan["validation"],
            "strategy": evidence,
            "evidence_mode": ("selection_plus_reserved_test" if final_test else "selection_only"),
            "population_scope": (
                "independent_records"
                if config["problem_type"] != "forecasting"
                else "regular_monthly_series"
            ),
            "limitations": [] if final_test else ["VALIDATION_ALSO_USED_FOR_SELECTION"],
        },
        "catalog_executed": [
            {
                "candidate_id": item["candidate_id"],
                "status": item["status"],
                "completed_units": item.get("completed_unit_count", 0),
                "planned_units": item.get("planned_unit_count", 0),
                "reason_code": item.get("reason_code"),
            }
            for item in candidates
        ],
        "candidates": candidates,
        "selection_decision": decision,
        "evaluation_metrics": selected["selection_metrics"],
        "unit_metrics": selected.get("unit_metrics", []),
        "final_test": final_test,
        "baseline_comparison": {
            "baseline_model_id": baseline["model_id"],
            "best_observed_model_id": decision["best_observed_candidate_id"],
            "selected_model_id": selected["model_id"],
            "observed_predictive_utility": utility,
        },
        "predictions": predictions,
        "drivers": drivers[:20],
        "explanation_scope": explanation_scope or {},
        "diagnostics": diagnostics or {},
        "reliability": {
            "policy_version": "reliability-policy-1.2",
            "primary_level": "medium" if final_test else "low",
            "evaluation_level": "reserved_test" if final_test else evidence,
            "observed_predictive_utility": utility,
            "is_probability": False,
            "reasons": reasons,
        },
        "findings": ["PREDICTIVE_NOT_CAUSAL", "BASELINE_IS_REQUIRED"],
        "recommended_actions": ["Revisar calidad y disponibilidad futura de las variables"],
        "limitations": limitations,
        "integrity": {
            "all_ranked_candidates_complete": all(
                item["status"] == "completed"
                for item in candidates
                if item.get("eligible_for_selection")
            ),
            "same_plan_sha256": plan["plan_sha256"],
            "non_finite_values_serialized": False,
            "snapshot_immutable": True,
        },
        "duration": {
            "analysis_seconds": round(time.monotonic() - started, 6) if started else None,
            "budget": plan["budgets"],
        },
        "environment": {"generated_at": datetime.now(UTC).isoformat()},
        "analytical_outcome": "completed",
    }


def exploration_result(profile, config):
    return {
        "schema_version": "2.0",
        "engine_version": __version__,
        "goal": config["goal"],
        "problem_type": config["problem_type"],
        "primary_metric_id": None,
        "dataset_summary": {
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
        },
        "data_quality": profile,
        "data_preparation": config.get("_preparation", {}),
        "requested_config": config,
        "resolved_config": config,
        "validation_plan": {"strategy": "none", "limitations": []},
        "candidates": [],
        "evaluation_metrics": [],
        "predictions": [],
        "drivers": [],
        "diagnostics": {},
        "reliability": {
            "policy_version": "reliability-policy-1.2",
            "primary_level": "not_evaluable",
            "is_probability": False,
            "reasons": ["La exploración no entrena modelos"],
        },
        "findings": [],
        "limitations": ["No se realizó una evaluación predictiva"],
        "analytical_outcome": "exploration_only",
    }


def not_evaluable(profile, config, reason, primary_metric=None, candidates=None, plan=None):
    result = exploration_result(profile, config)
    result["analytical_outcome"] = "not_evaluable"
    result["primary_metric_id"] = primary_metric
    result["candidates"] = candidates or []
    result["reliability"]["reasons"] = [reason]
    result["limitations"] = [reason]
    if plan:
        result["analysis_plan"] = plan
        result["plan_sha256"] = plan["plan_sha256"]
    return result


def resolve_features(columns, target, profile, config):
    existing = set(columns) | {target}
    included_value = config.get("included_column_ids", None)
    included = None if included_value is None else set(included_value)
    excluded = set(config.get("excluded_column_ids") or [])
    unknown = ((included or set()) | excluded) - existing
    if unknown:
        raise ValueError("UNKNOWN_COLUMN_IDS")
    if ((included or set()) & excluded) - {target}:
        raise ValueError("COLUMN_INCLUDED_AND_EXCLUDED")
    manual_roles = {
        column["column_id"]: column.get("configured_role") for column in profile.get("columns", [])
    }
    possible_ids = {
        column["column_id"]
        for column in profile.get("columns", [])
        if column.get("possible_id") and column.get("configured_role") != "variable"
    }
    candidates = set(columns) if included is None else included
    return [
        column
        for column in columns
        if column in candidates
        and column != target
        and column not in excluded
        and column not in possible_ids
        and manual_roles.get(column) not in {"identifier", "ignore"}
    ]


def resolve_primary_metric(problem, requested):
    primary = requested or DEFAULT_PRIMARY[problem]
    if primary not in SUPPORTED_PRIMARY[problem]:
        raise ValueError("UNSUPPORTED_PRIMARY_METRIC")
    return primary


def metric_set(problem, y, predicted, role="selection_oof", labels=None):
    return (
        regression_metrics(y, predicted, role)
        if problem == "regression"
        else classification_metrics(y, predicted, role, labels)
    )


def metric_value(metrics, metric_id):
    return next(metric["value"] for metric in metrics if metric["metric_id"] == metric_id)


def column_name(profile, column_id):
    return next(
        (
            column["display_name"]
            for column in profile.get("columns", [])
            if column["column_id"] == column_id
        ),
        column_id,
    )


def json_value(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("NON_FINITE_VALUE")
        return number
    return value


def analysis_budgets(depth):
    return {
        "selection_seconds": 120 if depth == "quick" else 360,
        "fit_seconds": 20 if depth == "quick" else 60,
        "final_and_forecast_seconds": 120,
        "explanation_seconds": 60,
        "exports_independent": True,
    }


def plan_summary(plan):
    validation = plan["validation"]
    return {
        "plan_sha256": plan["plan_sha256"],
        "problem_type": plan["problem_type"],
        "primary_metric": plan["primary_metric"],
        "metric_direction": plan["metric_direction"],
        "candidate_count": len(plan["candidates"]),
        "eligible_candidate_count": sum(
            1 for candidate in plan["candidates"] if candidate["eligible"]
        ),
        "evaluation_unit_count": len(validation["units"]),
        "validation_strategy": validation["strategy"],
        "population_count": plan["eligible_population"].get(
            "row_count", plan["eligible_population"].get("month_count")
        ),
        "reserved_test": bool(
            validation.get("holdout_row_ids") or validation.get("reserved_test_periods")
        ),
    }
