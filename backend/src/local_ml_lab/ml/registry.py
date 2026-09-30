from dataclasses import dataclass

from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.linear_model import LogisticRegression, Ridge


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    task: str
    complexity_rank: int
    build: object


REGISTRY = {
    "regression": [
        ModelSpec(
            "dummy_median",
            "Referencia: mediana",
            "regression",
            0,
            lambda seed: DummyRegressor(strategy="median"),
        ),
        ModelSpec("ridge", "Regresión Ridge", "regression", 1, lambda seed: Ridge(alpha=1.0)),
        ModelSpec(
            "extra_trees_regressor",
            "Extra Trees",
            "regression",
            2,
            lambda seed: ExtraTreesRegressor(
                n_estimators=100, min_samples_leaf=2, random_state=seed, n_jobs=2
            ),
        ),
        ModelSpec(
            "random_forest_regressor",
            "Random Forest",
            "regression",
            3,
            lambda seed: RandomForestRegressor(
                n_estimators=100, min_samples_leaf=2, random_state=seed, n_jobs=2
            ),
        ),
    ],
    "classification": [
        ModelSpec(
            "dummy_prior",
            "Referencia: clase frecuente",
            "classification",
            0,
            lambda seed: DummyClassifier(strategy="prior"),
        ),
        ModelSpec(
            "logistic_regression",
            "Regresión logística",
            "classification",
            1,
            lambda seed: LogisticRegression(max_iter=1000, random_state=seed),
        ),
        ModelSpec(
            "extra_trees_classifier",
            "Extra Trees",
            "classification",
            2,
            lambda seed: ExtraTreesClassifier(
                n_estimators=100, min_samples_leaf=2, random_state=seed, n_jobs=2
            ),
        ),
        ModelSpec(
            "random_forest_classifier",
            "Random Forest",
            "classification",
            3,
            lambda seed: RandomForestClassifier(
                n_estimators=100, min_samples_leaf=2, random_state=seed, n_jobs=2
            ),
        ),
    ],
}


def specs(task: str, depth: str):
    values = REGISTRY[task]
    if depth == "quick":
        return values[:3]
    return values
