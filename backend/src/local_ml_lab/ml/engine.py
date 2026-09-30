from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .metrics import classification_metrics, regression_metrics
from .registry import specs


def analyze(frame: pd.DataFrame, profile: dict, config: dict, progress=lambda *_: None) -> dict:
    problem = config["problem_type"]
    if problem == "exploration":
        return exploration_result(profile, config)
    if problem == "forecasting":
        return forecast_result(frame, profile, config, progress)
    target = config.get("target_column_id")
    if not target or target not in frame:
        raise ValueError("TARGET_REQUIRED")
    usable = frame[frame[target].notna()].copy()
    y = usable.pop(target)
    excluded = set(config.get("excluded_column_ids", [])) | {target}
    ids = {c["column_id"] for c in profile["columns"] if c["possible_id"]}
    features = [c for c in usable.columns if c not in excluded and c not in ids]
    x = usable[features]
    if not features:
        x = pd.DataFrame({"__constant": np.ones(len(usable))}, index=usable.index)
    numeric = [c for c in x if pd.api.types.is_numeric_dtype(x[c])]
    categorical = [c for c in x if c not in numeric]
    transformer = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        ("encode", OneHotEncoder(handle_unknown="ignore", min_frequency=2)),
                    ]
                ),
                categorical,
            ),
        ],
        remainder="drop",
    )
    if problem == "regression":
        y = pd.to_numeric(y, errors="coerce")
        mask = y.notna()
        x, y = x.loc[mask], y.loc[mask]
        folds = min(5, len(y))
        splitter = (
            KFold(n_splits=max(2, folds), shuffle=True, random_state=config.get("seed", 42))
            if len(y) >= 2
            else None
        )
    else:
        counts = y.value_counts()
        if len(counts) < 2 or counts.min() < 2:
            return not_evaluable(profile, config, "CLASS_SUPPORT_INSUFFICIENT")
        folds = min(5, int(counts.min()))
        splitter = StratifiedKFold(
            n_splits=folds, shuffle=True, random_state=config.get("seed", 42)
        )
    if splitter is None:
        return not_evaluable(profile, config, "INSUFFICIENT_ROWS")
    candidates = []
    prediction_sets = {}
    for idx, spec in enumerate(specs(problem, config.get("depth", "quick")), 1):
        progress(
            "fit",
            f"Probando {spec.display_name}",
            idx - 1,
            len(specs(problem, config.get("depth", "quick"))),
        )
        pipeline = Pipeline(
            [("prepare", transformer), ("model", spec.build(config.get("seed", 42) + idx))]
        )
        try:
            pred = cross_val_predict(pipeline, x, y, cv=splitter, method="predict")
            metrics = (
                regression_metrics(y, pred)
                if problem == "regression"
                else classification_metrics(y, pred)
            )
            primary = "mae" if problem == "regression" else "balanced_accuracy"
            score = next(m["value"] for m in metrics if m["metric_id"] == primary)
            candidates.append(
                {
                    "candidate_id": spec.model_id,
                    "model_id": spec.model_id,
                    "display_name": spec.display_name,
                    "status": "succeeded",
                    "eligible_for_selection": True,
                    "selection_metrics": metrics,
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
                    "complexity_rank": spec.complexity_rank,
                }
            )
    eligible = [c for c in candidates if c["eligible_for_selection"]]
    if not eligible:
        return not_evaluable(profile, config, "ALL_CANDIDATES_FAILED")
    reverse = problem == "classification"
    ordered = sorted(
        eligible,
        key=lambda c: (
            (-c["primary_value"] if reverse else c["primary_value"]),
            c["complexity_rank"],
            c["model_id"],
        ),
    )
    winner = ordered[0]
    selected_pred = prediction_sets[winner["model_id"]]
    model_spec = next(
        s for s in specs(problem, config.get("depth", "quick")) if s.model_id == winner["model_id"]
    )
    final_pipeline = Pipeline(
        [("prepare", transformer), ("model", model_spec.build(config.get("seed", 42)))]
    )
    final_pipeline.fit(x, y)
    drivers = []
    if len(features) and len(y) >= 10:
        try:
            pfi = permutation_importance(
                final_pipeline,
                x,
                y,
                n_repeats=3,
                random_state=config.get("seed", 42),
                scoring="neg_mean_absolute_error"
                if problem == "regression"
                else "balanced_accuracy",
            )
            for col, mean, std in zip(
                features, pfi.importances_mean, pfi.importances_std, strict=False
            ):
                drivers.append(
                    {
                        "source_column_id": col,
                        "method": "permutation_importance",
                        "importance_mean": float(mean),
                        "importance_std": float(std),
                        "repeat_count": 3,
                        "evaluation_sample_count": len(y),
                        "warnings": ["PREDICTIVE_NOT_CAUSAL"],
                    }
                )
            drivers.sort(key=lambda d: d["importance_mean"], reverse=True)
        except Exception:
            pass
    predictions = [
        {
            "row_id": f"r{i:07d}",
            "actual": json_value(a),
            "predicted": json_value(p),
            "evaluation_role": "selection_oof",
            "model_id": winner["model_id"],
        }
        for i, (a, p) in enumerate(zip(y.tolist(), selected_pred.tolist(), strict=False), 1)
    ]
    baseline = next((c for c in candidates if c["complexity_rank"] == 0), None)
    return build_result(
        profile, config, candidates, winner, predictions, drivers, baseline, "selection_cv"
    )


def forecast_result(frame, profile, config, progress):
    target = config.get("target_column_id")
    date_col = config.get("date_column_id")
    if not target or not date_col:
        raise ValueError("FORECAST_COLUMNS_REQUIRED")
    data = (
        pd.DataFrame(
            {
                "date": pd.to_datetime(frame[date_col], errors="coerce"),
                "value": pd.to_numeric(frame[target], errors="coerce"),
            }
        )
        .dropna()
        .sort_values("date")
    )
    values = data["value"].to_numpy(float)
    horizon = int(
        (config.get("forecast_options") or {}).get("horizon", min(3, max(1, len(values) // 10)))
    )
    if len(values) < horizon + 3:
        return not_evaluable(profile, config, "INSUFFICIENT_HISTORY")
    actual = values[-horizon:]
    train = values[:-horizon]
    last_pred = np.repeat(train[-1], horizon)
    candidates = [
        {
            "candidate_id": "last_value",
            "model_id": "last_value",
            "display_name": "Último valor",
            "status": "succeeded",
            "eligible_for_selection": True,
            "selection_metrics": regression_metrics(actual, last_pred),
            "primary_value": float(np.mean(np.abs(actual - last_pred))),
            "complexity_rank": 0,
        }
    ]
    seasonal_pred = None
    if len(train) >= 2 * 12:
        seasonal_pred = np.array([train[-12 + (i % 12)] for i in range(horizon)])
        candidates.append(
            {
                "candidate_id": "seasonal_naive",
                "model_id": "seasonal_naive",
                "display_name": "Referencia estacional (12)",
                "status": "succeeded",
                "eligible_for_selection": True,
                "selection_metrics": regression_metrics(actual, seasonal_pred),
                "primary_value": float(np.mean(np.abs(actual - seasonal_pred))),
                "complexity_rank": 0,
            }
        )
    winner = min(
        candidates, key=lambda c: (c["primary_value"], c["complexity_rank"], c["model_id"])
    )
    eval_pred = last_pred if winner["model_id"] == "last_value" else seasonal_pred
    future_pred = (
        np.repeat(values[-1], horizon)
        if winner["model_id"] == "last_value"
        else np.array([values[-12 + (i % 12)] for i in range(horizon)])
    )
    last_date = data["date"].iloc[-1]
    future_dates = [last_date + pd.DateOffset(months=i) for i in range(1, horizon + 1)]
    predictions = [
        {
            "record_id": f"eval-{i}",
            "actual": float(a),
            "predicted": float(p),
            "evaluation_role": "final_test",
            "horizon": i,
        }
        for i, (a, p) in enumerate(zip(actual, eval_pred, strict=False), 1)
    ]
    predictions += [
        {
            "record_id": f"future-{i}",
            "actual": None,
            "predicted": float(p),
            "evaluation_role": "forecast",
            "horizon": i,
            "target_period": d.date().isoformat(),
        }
        for i, (d, p) in enumerate(zip(future_dates, future_pred, strict=False), 1)
    ]
    result = build_result(
        profile,
        config,
        candidates,
        winner,
        predictions,
        [],
        candidates[0],
        "selection_single_split",
    )
    result["uncertainty"] = {
        "available": False,
        "reason_code": "INSUFFICIENT_INDEPENDENT_CALIBRATION",
    }
    return result


def build_result(profile, config, candidates, winner, predictions, drivers, baseline, evidence):
    metrics = winner["selection_metrics"]
    baseline_value = baseline["primary_value"] if baseline else None
    utility = "similar_to_baseline"
    if baseline_value not in (None, 0):
        if config["problem_type"] == "classification":
            utility = (
                "better_than_baseline"
                if winner["primary_value"] > baseline_value + 0.01
                else utility
            )
        else:
            utility = (
                "better_than_baseline"
                if winner["primary_value"] < baseline_value * 0.99
                else utility
            )
    return {
        "schema_version": "1.0",
        "engine_version": "0.1.0",
        "goal": config["goal"],
        "problem_type": config["problem_type"],
        "dataset_summary": {
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
        },
        "requested_config": config,
        "resolved_config": config,
        "data_quality": profile,
        "validation_plan": {
            "strategy": evidence,
            "evidence_mode": evidence,
            "limitations": ["La misma validación participó en la selección"]
            if evidence != "holdout_final"
            else [],
        },
        "candidates": candidates,
        "selection_decision": {
            "selected_candidate_id": winner["candidate_id"],
            "model_id": winner["model_id"],
            "reason": "Mejor evidencia comparable; los empates favorecen menor complejidad",
        },
        "evaluation_metrics": metrics,
        "baseline_comparison": {
            "baseline_model_id": baseline["model_id"] if baseline else None,
            "observed_predictive_utility": utility,
        },
        "predictions": predictions,
        "drivers": drivers[:20],
        "reliability": {
            "policy_version": "reliability-policy-1.0",
            "primary_level": "low" if evidence != "holdout_final" else "medium",
            "evaluation_level": evidence,
            "observed_predictive_utility": utility,
            "is_probability": False,
            "reasons": [
                "La evidencia es exploratoria"
                if evidence != "holdout_final"
                else "Existe una prueba reservada"
            ],
        },
        "findings": ["PREDICTIVE_NOT_CAUSAL", "BASELINE_IS_REQUIRED"],
        "recommended_actions": ["Revisar calidad y disponibilidad futura de las variables"],
        "limitations": ["La importancia predictiva no demuestra necesariamente causalidad."],
        "environment": {"generated_at": datetime.now(UTC).isoformat()},
        "analytical_outcome": "completed",
    }


def exploration_result(profile, config):
    return {
        "schema_version": "1.0",
        "engine_version": "0.1.0",
        "goal": "explore",
        "problem_type": "exploration",
        "dataset_summary": {
            "row_count": profile["row_count"],
            "column_count": profile["column_count"],
        },
        "data_quality": profile,
        "requested_config": config,
        "resolved_config": config,
        "candidates": [],
        "evaluation_metrics": [],
        "predictions": [],
        "drivers": [],
        "reliability": {
            "policy_version": "reliability-policy-1.0",
            "primary_level": "not_evaluable",
            "is_probability": False,
            "reasons": ["La exploración no entrena modelos"],
        },
        "findings": [],
        "limitations": ["No se realizó una evaluación predictiva"],
        "analytical_outcome": "exploration_only",
    }


def not_evaluable(profile, config, reason):
    result = exploration_result(profile, config)
    result["analytical_outcome"] = "not_evaluable"
    result["reliability"]["reasons"] = [reason]
    result["limitations"] = [reason]
    return result


def json_value(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v
