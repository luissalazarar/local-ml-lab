from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge


def _threads() -> int:
    try:
        configured = int(os.environ.get("ML_THREADS", "2"))
    except ValueError:
        configured = 2
    return min(2, max(1, configured))


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    task: str
    family: str
    complexity_rank: int
    build: Callable[[int], object]
    parameters: dict
    capabilities: tuple[str, ...]
    fit_requirements: dict
    preprocessing: str
    adapter_version: str = "1.0"
    uses_features: bool = True
    scale_numeric: bool = False

    def public(self) -> dict:
        return {
            "candidate_id": self.model_id,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "family": self.family,
            "parameters": self.parameters,
            "complexity_rank": self.complexity_rank,
            "capabilities": list(self.capabilities),
            "fit_requirements": self.fit_requirements,
            "preprocessing": self.preprocessing,
            "adapter_version": self.adapter_version,
            "uses_features": self.uses_features,
        }


TREE_PARAMETERS = {
    "n_estimators": 100,
    "max_depth": 12,
    "min_samples_leaf": 2,
    "n_jobs": "min(ML_THREADS,2)",
}


def regression_specs(primary_metric: str, depth: str) -> list[ModelSpec]:
    strategy = "median" if primary_metric == "mae" else "mean"
    values = [
        ModelSpec(
            f"dummy_{strategy}",
            f"Referencia: {'mediana' if strategy == 'median' else 'media'}",
            "regression",
            "reference",
            0,
            lambda seed, strategy=strategy: DummyRegressor(strategy=strategy),
            {"strategy": strategy},
            ("regression", "featureless"),
            {"minimum_train_rows": 1},
            "none",
            uses_features=False,
        ),
        ModelSpec(
            "ridge",
            "Regresión Ridge",
            "regression",
            "linear",
            1,
            lambda seed: Ridge(alpha=1.0),
            {"alpha": 1.0},
            ("regression", "numeric", "categorical"),
            {"minimum_train_rows": 2},
            "impute_encode_scale_train_only",
            scale_numeric=True,
        ),
    ]
    if depth == "recommended":
        values.extend(
            [
                ModelSpec(
                    "extra_trees_regressor",
                    "Extra Trees",
                    "regression",
                    "extra_trees",
                    3,
                    lambda seed: ExtraTreesRegressor(
                        n_estimators=100,
                        max_depth=12,
                        min_samples_leaf=2,
                        random_state=seed,
                        n_jobs=_threads(),
                    ),
                    TREE_PARAMETERS,
                    ("regression", "nonlinear", "numeric", "categorical"),
                    {"minimum_train_rows": 20},
                    "impute_encode_train_only",
                ),
                ModelSpec(
                    "random_forest_regressor",
                    "Random Forest",
                    "regression",
                    "random_forest",
                    4,
                    lambda seed: RandomForestRegressor(
                        n_estimators=100,
                        max_depth=12,
                        min_samples_leaf=2,
                        random_state=seed,
                        n_jobs=_threads(),
                    ),
                    TREE_PARAMETERS,
                    ("regression", "nonlinear", "numeric", "categorical"),
                    {"minimum_train_rows": 20},
                    "impute_encode_train_only",
                ),
            ]
        )
    return values


def classification_specs(depth: str) -> list[ModelSpec]:
    values = [
        ModelSpec(
            "dummy_prior",
            "Referencia: distribución observada",
            "classification",
            "reference",
            0,
            lambda seed: DummyClassifier(strategy="prior"),
            {"strategy": "prior"},
            ("classification", "featureless"),
            {"minimum_classes": 2},
            "none",
            uses_features=False,
        ),
        ModelSpec(
            "logistic_regression",
            "Regresión logística",
            "classification",
            "linear",
            1,
            lambda seed: LogisticRegression(C=1, max_iter=1000, class_weight=None),
            {"C": 1, "max_iter": 1000, "class_weight": None},
            ("classification", "numeric", "categorical"),
            {"minimum_classes": 2},
            "impute_encode_scale_train_only",
            scale_numeric=True,
        ),
        ModelSpec(
            "logistic_regression_balanced",
            "Regresión logística · pesos balanceados",
            "classification",
            "linear_balanced",
            2,
            lambda seed: LogisticRegression(C=1, max_iter=1000, class_weight="balanced"),
            {"C": 1, "max_iter": 1000, "class_weight": "balanced"},
            ("classification", "imbalanced_classes", "numeric", "categorical"),
            {"minimum_classes": 2},
            "impute_encode_scale_train_only",
            scale_numeric=True,
        ),
    ]
    if depth == "recommended":
        values.extend(
            [
                ModelSpec(
                    "extra_trees_classifier",
                    "Extra Trees",
                    "classification",
                    "extra_trees",
                    3,
                    lambda seed: ExtraTreesClassifier(
                        n_estimators=100,
                        max_depth=12,
                        min_samples_leaf=2,
                        class_weight=None,
                        random_state=seed,
                        n_jobs=_threads(),
                    ),
                    {**TREE_PARAMETERS, "class_weight": None},
                    ("classification", "nonlinear", "numeric", "categorical"),
                    {"minimum_train_rows": 20, "minimum_classes": 2},
                    "impute_encode_train_only",
                ),
                ModelSpec(
                    "random_forest_classifier",
                    "Random Forest",
                    "classification",
                    "random_forest",
                    4,
                    lambda seed: RandomForestClassifier(
                        n_estimators=100,
                        max_depth=12,
                        min_samples_leaf=2,
                        class_weight=None,
                        random_state=seed,
                        n_jobs=_threads(),
                    ),
                    {**TREE_PARAMETERS, "class_weight": None},
                    ("classification", "nonlinear", "numeric", "categorical"),
                    {"minimum_train_rows": 20, "minimum_classes": 2},
                    "impute_encode_train_only",
                ),
                ModelSpec(
                    "random_forest_classifier_balanced",
                    "Random Forest · pesos balanceados",
                    "classification",
                    "random_forest_balanced",
                    5,
                    lambda seed: RandomForestClassifier(
                        n_estimators=100,
                        max_depth=12,
                        min_samples_leaf=2,
                        class_weight="balanced",
                        random_state=seed,
                        n_jobs=_threads(),
                    ),
                    {**TREE_PARAMETERS, "class_weight": "balanced"},
                    ("classification", "nonlinear", "imbalanced_classes"),
                    {"minimum_train_rows": 20, "minimum_classes": 2},
                    "impute_encode_train_only",
                ),
            ]
        )
    return values


def specs(task: str, depth: str, primary_metric: str | None = None) -> list[ModelSpec]:
    if task == "regression":
        return regression_specs(primary_metric or "mae", depth)
    if task == "classification":
        return classification_specs(depth)
    raise ValueError("UNKNOWN_MODEL_TASK")
