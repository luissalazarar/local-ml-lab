from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from local_ml_lab import __version__

from .metrics import classification_metrics, regression_metrics
from .registry import specs

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


def analyze(frame: pd.DataFrame, profile: dict, config: dict, progress=lambda *_: None) -> dict:
    problem = config["problem_type"]
    if problem == "exploration":
        return exploration_result(profile, config)
    primary_metric = resolve_primary_metric(problem, config.get("primary_metric"))
    if config.get("validation_context", "independent_records") != "independent_records":
        raise ValueError("UNSUPPORTED_VALIDATION_CONTEXT")
    if problem == "forecasting":
        return forecast_result(frame, profile, config, progress, primary_metric)
    target = config.get("target_column_id")
    if not target or target not in frame:
        raise ValueError("TARGET_REQUIRED")
    usable = frame[frame[target].notna()].copy()
    target_missing = int(frame[target].isna().sum())
    if target_missing:
        preparation = config.setdefault("_preparation", {})
        preparation["target_missing_rows"] = target_missing
        preparation["target_missing_note"] = (
            "Filas sin resultado apartadas para este análisis; el dataset original no cambió."
        )
    y = usable.pop(target)
    features = resolve_features(usable.columns, target, profile, config)
    x = usable[features]
    if not features:
        x = pd.DataFrame({"__constant": np.ones(len(usable))}, index=usable.index)
    transformer = build_transformer(x)
    if problem == "regression":
        y = pd.to_numeric(y, errors="coerce")
        mask = y.notna()
        x, y = x.loc[mask], y.loc[mask]
        if len(y) < 2:
            return not_evaluable(profile, config, "INSUFFICIENT_ROWS", primary_metric)
        splitter = KFold(n_splits=min(5, len(y)), shuffle=True, random_state=config.get("seed", 42))
    else:
        counts = y.value_counts()
        if len(counts) < 2 or counts.min() < 2:
            return not_evaluable(profile, config, "CLASS_SUPPORT_INSUFFICIENT", primary_metric)
        splitter = StratifiedKFold(
            n_splits=min(5, int(counts.min())),
            shuffle=True,
            random_state=config.get("seed", 42),
        )
    splits = list(splitter.split(x, y))
    model_specs = specs(problem, config.get("depth", "quick"))
    candidates = []
    prediction_sets = {}
    for idx, spec in enumerate(model_specs, 1):
        progress("fit", f"Comparando modelos · {spec.display_name}", idx - 1, len(model_specs))
        pipeline = make_pipeline(transformer, spec, config.get("seed", 42) + idx)
        try:
            pred = cross_val_predict(pipeline, x, y, cv=splits, method="predict")
            metrics = metric_set(problem, y, pred)
            score = metric_value(metrics, primary_metric)
            candidates.append(
                {
                    "candidate_id": spec.model_id,
                    "model_id": spec.model_id,
                    "display_name": spec.display_name,
                    "status": "succeeded",
                    "eligible_for_selection": score is not None,
                    "selection_metrics": metrics,
                    "primary_metric_id": primary_metric,
                    "primary_value": score,
                    "complexity_rank": spec.complexity_rank,
                }
            )
            prediction_sets[spec.model_id] = pred
        except Exception as exc:
            candidates.append(
                {
                    "candidate_id": spec.model_id,
                    "model_id": spec.model_id,
                    "display_name": spec.display_name,
                    "status": "failed",
                    "eligible_for_selection": False,
                    "reason_code": type(exc).__name__,
                    "selection_metrics": [],
                    "primary_metric_id": primary_metric,
                    "complexity_rank": spec.complexity_rank,
                }
            )
    eligible = [candidate for candidate in candidates if candidate["eligible_for_selection"]]
    if not eligible:
        return not_evaluable(profile, config, "ALL_CANDIDATES_FAILED", primary_metric, candidates)
    direction = SUPPORTED_PRIMARY[problem][primary_metric]
    winner = sorted(
        eligible,
        key=lambda candidate: (
            -candidate["primary_value"] if direction == "max" else candidate["primary_value"],
            candidate["complexity_rank"],
            candidate["model_id"],
        ),
    )[0]
    selected_pred = prediction_sets[winner["model_id"]]
    model_spec = next(spec for spec in model_specs if spec.model_id == winner["model_id"])
    drivers = fold_permutation_importance(
        x,
        y,
        features,
        splits,
        transformer,
        model_spec,
        problem,
        primary_metric,
        config.get("seed", 42),
        progress,
    )
    target_name = column_name(profile, target)
    predictions = [
        {
            "row_id": f"r{i:07d}",
            "actual": json_value(actual),
            "predicted": json_value(predicted),
            "error": json_value(predicted - actual) if problem == "regression" else None,
            "evaluation_role": "selection_oof",
            "model_id": winner["model_id"],
            "target_column_id": target,
            "target_name": target_name,
            "unit": "target_unit" if problem == "regression" else "class_label",
        }
        for i, (actual, predicted) in enumerate(
            zip(y.tolist(), selected_pred.tolist(), strict=False), 1
        )
    ]
    baseline = next(
        (candidate for candidate in candidates if candidate["complexity_rank"] == 0), None
    )
    diagnostics = {}
    if problem == "classification":
        labels = sorted({str(value) for value in y.tolist()})
        y_text = [str(value) for value in y.tolist()]
        pred_text = [str(value) for value in selected_pred.tolist()]
        diagnostics = {
            "class_labels": labels,
            "class_support": [{"label": label, "count": y_text.count(label)} for label in labels],
            "confusion_matrix": confusion_matrix(y_text, pred_text, labels=labels).tolist(),
        }
    return build_result(
        profile,
        config,
        candidates,
        winner,
        predictions,
        drivers,
        baseline,
        "selection_cv",
        primary_metric,
        diagnostics,
    )


def resolve_features(columns, target, profile, config):
    existing = set(columns) | {target}
    included = set(config.get("included_column_ids") or [])
    excluded = set(config.get("excluded_column_ids") or [])
    unknown = (included | excluded) - existing
    if unknown:
        raise ValueError("UNKNOWN_COLUMN_IDS")
    if (included & excluded) - {target}:
        raise ValueError("COLUMN_INCLUDED_AND_EXCLUDED")
    possible_ids = {column["column_id"] for column in profile["columns"] if column["possible_id"]}
    candidates = included if included else set(columns)
    return [
        column
        for column in columns
        if column in candidates and column not in excluded and column not in possible_ids
    ]


def build_transformer(x):
    numeric = [column for column in x if pd.api.types.is_numeric_dtype(x[column])]
    categorical = [column for column in x if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("encode", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
                    ]
                ),
                categorical,
            )
        )
    return ColumnTransformer(transformers, remainder="drop")


def make_pipeline(transformer, spec, seed):
    return Pipeline([("prepare", transformer), ("model", spec.build(seed))])


def fold_permutation_importance(
    x, y, features, splits, transformer, model_spec, problem, primary_metric, seed, progress
):
    if not features or len(y) < 10:
        return []
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
    for fold, (train_indices, validation_indices) in enumerate(splits, 1):
        progress(
            "explain",
            f"Midiendo importancia · partición de validación {fold} de {len(splits)}",
            fold - 1,
            len(splits),
        )
        pipeline = make_pipeline(transformer, model_spec, seed + 100 + fold)
        pipeline.fit(x.iloc[train_indices], y.iloc[train_indices])
        measured = permutation_importance(
            pipeline,
            x.iloc[validation_indices],
            y.iloc[validation_indices],
            n_repeats=3,
            random_state=seed + fold,
            scoring=scoring,
        )
        fold_values.append(measured.importances)
    combined = np.concatenate(fold_values, axis=1)
    drivers = [
        {
            "source_column_id": column,
            "method": "permutation_importance_validation_folds",
            "importance_mean": float(combined[index].mean()),
            "importance_std": float(combined[index].std()),
            "repeat_count": int(combined.shape[1]),
            "evaluation_sample_count": len(y),
            "evaluation_role": "selection_validation_folds",
            "fit_scope": "fold_train_only",
            "warnings": ["PREDICTIVE_NOT_CAUSAL", "VALIDATION_ALSO_USED_FOR_SELECTION"],
        }
        for index, column in enumerate(features)
    ]
    return sorted(drivers, key=lambda driver: driver["importance_mean"], reverse=True)


def forecast_result(frame, profile, config, progress, primary_metric):
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
    missing = expected.difference(pd.PeriodIndex(data["period"], freq="M"))
    if len(missing):
        raise ValueError("MISSING_MONTHLY_PERIODS")
    values = data["value"].to_numpy(float)
    if len(values) < horizon + 3:
        return not_evaluable(profile, config, "INSUFFICIENT_HISTORY", primary_metric)
    progress("fit", "Comparando referencias mensuales", 0, 2)
    actual = values[-horizon:]
    train = values[:-horizon]
    last_pred = np.repeat(train[-1], horizon)
    candidates = [
        forecast_candidate("last_value", "Último valor", actual, last_pred, primary_metric)
    ]
    seasonal_pred = None
    if len(train) >= 12:
        seasonal_pred = np.array([train[-12 + (index % 12)] for index in range(horizon)])
        candidates.append(
            forecast_candidate(
                "seasonal_naive",
                "Referencia estacional (12 meses)",
                actual,
                seasonal_pred,
                primary_metric,
            )
        )
    winner = min(
        candidates,
        key=lambda candidate: (
            candidate["primary_value"],
            candidate["complexity_rank"],
            candidate["model_id"],
        ),
    )
    eval_pred = last_pred if winner["model_id"] == "last_value" else seasonal_pred
    future_pred = (
        np.repeat(values[-1], horizon)
        if winner["model_id"] == "last_value"
        else np.array([values[-12 + (index % 12)] for index in range(horizon)])
    )
    future_periods = pd.period_range(data["period"].iloc[-1] + 1, periods=horizon, freq="M")
    predictions = [
        {
            "record_id": f"history-{index}",
            "actual": float(value),
            "predicted": None,
            "evaluation_role": "history",
            "target_period": period.to_timestamp().date().isoformat(),
            "unit": "target_unit",
        }
        for index, (period, value) in enumerate(zip(data["period"], values, strict=False), 1)
    ]
    predictions += [
        {
            "record_id": f"validation-{index}",
            "actual": float(actual_value),
            "predicted": float(predicted_value),
            "error": float(predicted_value - actual_value),
            "evaluation_role": "selection_validation",
            "horizon": index,
            "target_period": data["period"]
            .iloc[-horizon + index - 1]
            .to_timestamp()
            .date()
            .isoformat(),
            "unit": "target_unit",
        }
        for index, (actual_value, predicted_value) in enumerate(
            zip(actual, eval_pred, strict=False), 1
        )
    ]
    predictions += [
        {
            "record_id": f"future-{index}",
            "actual": None,
            "predicted": float(predicted_value),
            "evaluation_role": "forecast_future",
            "horizon": index,
            "target_period": period.to_timestamp().date().isoformat(),
            "unit": "target_unit",
        }
        for index, (period, predicted_value) in enumerate(
            zip(future_periods, future_pred, strict=False), 1
        )
    ]
    result = build_result(
        profile,
        config,
        candidates,
        winner,
        predictions,
        [],
        candidates[0],
        "selection_monthly_holdout",
        primary_metric,
        {
            "frequency": "monthly",
            "aggregation": aggregation or "one_observation_per_month",
            "missing_period_count": 0,
        },
    )
    result["uncertainty"] = {
        "available": False,
        "reason_code": "NO_INDEPENDENT_CALIBRATION",
    }
    return result


def forecast_candidate(model_id, display_name, actual, predicted, primary_metric):
    metrics = regression_metrics(actual, predicted, role="selection_validation")
    return {
        "candidate_id": model_id,
        "model_id": model_id,
        "display_name": display_name,
        "status": "succeeded",
        "eligible_for_selection": True,
        "selection_metrics": metrics,
        "primary_metric_id": primary_metric,
        "primary_value": metric_value(metrics, primary_metric),
        "complexity_rank": 0,
    }


def build_result(
    profile,
    config,
    candidates,
    winner,
    predictions,
    drivers,
    baseline,
    evidence,
    primary_metric,
    diagnostics=None,
):
    metrics = winner["selection_metrics"]
    baseline_value = baseline["primary_value"] if baseline else None
    direction = SUPPORTED_PRIMARY[config["problem_type"]][primary_metric]
    utility = "similar_to_baseline"
    if baseline_value is not None and winner["primary_value"] is not None:
        if direction == "max" and winner["primary_value"] > baseline_value + 0.01:
            utility = "better_than_baseline"
        elif (
            direction == "min"
            and baseline_value != 0
            and winner["primary_value"] < baseline_value * 0.99
        ):
            utility = "better_than_baseline"
    limitations = [
        "La misma validación participó en la selección del modelo; no es una prueba final independiente.",
        "La importancia predictiva no demuestra causalidad.",
    ]
    if config["problem_type"] in {"regression", "classification"}:
        limitations.append(
            "La validación aleatoria solo es adecuada para registros independientes; grupos, entidades repetidas y usos temporales no están soportados."
        )
    if profile.get("duplicate_count", 0):
        limitations.append(
            "Se detectaron filas duplicadas; confirma que no representen observaciones dependientes."
        )
    if config["problem_type"] == "forecasting":
        limitations.append("El alcance de forecasting es una sola serie mensual regular.")
    return {
        "schema_version": "1.1",
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
        "validation_plan": {
            "strategy": evidence,
            "evidence_mode": evidence,
            "population_scope": "independent_records"
            if config["problem_type"] != "forecasting"
            else "regular_monthly_series",
            "limitations": ["VALIDATION_ALSO_USED_FOR_SELECTION"],
        },
        "candidates": candidates,
        "selection_decision": {
            "selected_candidate_id": winner["candidate_id"],
            "model_id": winner["model_id"],
            "primary_metric_id": primary_metric,
            "reason": "Mejor evidencia comparable; los empates favorecen menor complejidad",
        },
        "evaluation_metrics": metrics,
        "baseline_comparison": {
            "baseline_model_id": baseline["model_id"] if baseline else None,
            "observed_predictive_utility": utility,
        },
        "predictions": predictions,
        "drivers": drivers[:20],
        "diagnostics": diagnostics or {},
        "reliability": {
            "policy_version": "reliability-policy-1.1",
            "primary_level": "low",
            "evaluation_level": evidence,
            "observed_predictive_utility": utility,
            "is_probability": False,
            "reasons": ["Evidencia exploratoria sin prueba final independiente"],
        },
        "findings": ["PREDICTIVE_NOT_CAUSAL", "BASELINE_IS_REQUIRED"],
        "recommended_actions": ["Revisar calidad y disponibilidad futura de las variables"],
        "limitations": limitations,
        "environment": {"generated_at": datetime.now(UTC).isoformat()},
        "analytical_outcome": "completed",
    }


def exploration_result(profile, config):
    return {
        "schema_version": "1.1",
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
            "policy_version": "reliability-policy-1.1",
            "primary_level": "not_evaluable",
            "is_probability": False,
            "reasons": ["La exploración no entrena modelos"],
        },
        "findings": [],
        "limitations": ["No se realizó una evaluación predictiva"],
        "analytical_outcome": "exploration_only",
    }


def not_evaluable(profile, config, reason, primary_metric=None, candidates=None):
    result = exploration_result(profile, config)
    result["analytical_outcome"] = "not_evaluable"
    result["primary_metric_id"] = primary_metric
    result["candidates"] = candidates or []
    result["reliability"]["reasons"] = [reason]
    result["limitations"] = [reason]
    return result


def resolve_primary_metric(problem, requested):
    primary = requested or DEFAULT_PRIMARY[problem]
    if primary not in SUPPORTED_PRIMARY[problem]:
        raise ValueError("UNSUPPORTED_PRIMARY_METRIC")
    return primary


def metric_set(problem, y, predicted):
    return (
        regression_metrics(y, predicted)
        if problem == "regression"
        else classification_metrics(y, predicted)
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
        return float(value)
    return value
