from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from statsmodels.tsa.holtwinters import ExponentialSmoothing


@dataclass(frozen=True)
class ForecastSpec:
    model_id: str
    display_name: str
    complexity_rank: int
    minimum_train_months: int
    reference: bool
    explanation: str
    predict: Callable
    parameters: dict
    adapter_version: str = "1.0"

    def public(self) -> dict:
        return {
            "candidate_id": self.model_id,
            "model_id": self.model_id,
            "display_name": self.display_name,
            "family": "forecasting",
            "complexity_rank": self.complexity_rank,
            "minimum_train_months": self.minimum_train_months,
            "reference": self.reference,
            "parameters": self.parameters,
            "preprocessing": "prefix_only",
            "adapter_version": self.adapter_version,
            "explanation": self.explanation,
        }


def _last(values, dates, future_dates, config):
    return np.repeat(float(values[-1]), len(future_dates))


def _mean(values, dates, future_dates, config):
    return np.repeat(float(np.mean(values)), len(future_dates))


def _seasonal(values, dates, future_dates, config):
    return np.asarray([float(values[-12 + (index % 12)]) for index in range(len(future_dates))])


def _linear(values, dates, future_dates, config):
    observed = np.arange(len(values), dtype=float).reshape(-1, 1)
    future = np.arange(len(values), len(values) + len(future_dates), dtype=float).reshape(-1, 1)
    return LinearRegression().fit(observed, values).predict(future)


def _ridge_month(values, dates, future_dates, config):
    train_index = np.arange(len(values), dtype=float)
    center = float(train_index.mean())
    scale = float(train_index.std()) or 1.0

    def features(indices, periods):
        time = ((np.asarray(indices, dtype=float) - center) / scale).reshape(-1, 1)
        month = np.zeros((len(periods), 12), dtype=float)
        for row, period in enumerate(periods):
            month[row, int(period.month) - 1] = 1.0
        return np.column_stack([time, month])

    future_index = np.arange(len(values), len(values) + len(future_dates), dtype=float)
    model = Ridge(alpha=1.0, fit_intercept=True)
    model.fit(features(train_index, dates), values)
    return model.predict(features(future_index, future_dates))


def _holt(values, dates, future_dates, config):
    model = ExponentialSmoothing(
        np.asarray(values, dtype=float),
        trend="add",
        damped_trend=True,
        seasonal=None,
        initialization_method="estimated",
        bounds={"damping_trend": (0.80, 0.98)},
    )
    fitted = model.fit(optimized=True, use_brute=False, remove_bias=False)
    _check_holt_fit(fitted)
    return np.asarray(fitted.forecast(len(future_dates)), dtype=float)


def _holt_winters(values, dates, future_dates, config):
    model = ExponentialSmoothing(
        np.asarray(values, dtype=float),
        trend="add",
        damped_trend=True,
        seasonal="add",
        seasonal_periods=12,
        initialization_method="estimated",
        bounds={"damping_trend": (0.80, 0.98)},
    )
    fitted = model.fit(optimized=True, use_brute=False, remove_bias=False)
    _check_holt_fit(fitted)
    return np.asarray(fitted.forecast(len(future_dates)), dtype=float)


def _check_holt_fit(fitted) -> None:
    values = np.asarray(fitted.fittedvalues, dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("NON_FINITE_FIT")
    optimization = getattr(fitted, "mle_retvals", {}) or {}
    if optimization.get("success") is False:
        raise RuntimeError("FORECAST_OPTIMIZATION_DID_NOT_CONVERGE")


FORECAST_SPECS = [
    ForecastSpec(
        "last_value",
        "Último valor",
        0,
        2,
        True,
        "Mantiene el último valor observado como referencia sencilla.",
        _last,
        {},
    ),
    ForecastSpec(
        "historical_mean",
        "Media histórica",
        1,
        2,
        True,
        "Usa la media del histórico disponible; es útil cuando domina el ruido sin tendencia.",
        _mean,
        {},
    ),
    ForecastSpec(
        "seasonal_naive",
        "Referencia estacional",
        2,
        24,
        True,
        "Repite cíclicamente los últimos doce meses observados.",
        _seasonal,
        {"seasonal_periods": 12},
    ),
    ForecastSpec(
        "linear_trend",
        "Tendencia lineal",
        3,
        12,
        False,
        "Prolonga una tendencia lineal estimada únicamente con el prefijo disponible.",
        _linear,
        {"fit_intercept": True},
    ),
    ForecastSpec(
        "ridge_trend_month",
        "Ridge con tendencia y mes",
        4,
        24,
        False,
        "Combina tiempo y mes del calendario; incluir el componente mensual no demuestra estacionalidad.",
        _ridge_month,
        {"alpha": 1.0, "fit_intercept": True, "calendar_categories": 12},
    ),
    ForecastSpec(
        "holt_damped",
        "Holt amortiguado",
        5,
        12,
        False,
        "Continúa una tendencia, reduciendo gradualmente su fuerza hacia adelante.",
        _holt,
        {
            "trend": "add",
            "damped_trend": True,
            "seasonal": None,
            "damping_trend_bounds": [0.80, 0.98],
            "use_brute": False,
            "remove_bias": False,
        },
    ),
    ForecastSpec(
        "holt_winters_add_damped",
        "Holt-Winters aditivo amortiguado",
        6,
        36,
        False,
        "Combina nivel, tendencia y diferencias que se repiten entre meses.",
        _holt_winters,
        {
            "trend": "add",
            "damped_trend": True,
            "seasonal": "add",
            "seasonal_periods": 12,
            "damping_trend_bounds": [0.80, 0.98],
            "use_brute": False,
            "remove_bias": False,
        },
    ),
]


def specs(depth: str) -> list[ForecastSpec]:
    return FORECAST_SPECS[:5] if depth == "quick" else FORECAST_SPECS


def fit_predict(
    spec: ForecastSpec,
    prefix_values,
    prefix_dates,
    future_dates,
    frozen_config: dict,
) -> np.ndarray:
    values = np.asarray(prefix_values, dtype=float)
    dates = pd.PeriodIndex(prefix_dates, freq="M")
    future = pd.PeriodIndex(future_dates, freq="M")
    if len(values) < spec.minimum_train_months:
        raise ValueError("FORECAST_CANDIDATE_INELIGIBLE")
    if len(values) != len(dates):
        raise ValueError("FORECAST_PREFIX_ALIGNMENT")
    expected = pd.period_range(dates[-1] + 1, periods=len(future), freq="M")
    if not expected.equals(future):
        raise ValueError("FORECAST_FUTURE_CALENDAR_MISMATCH")
    predicted = np.asarray(spec.predict(values, dates, future, frozen_config), dtype=float)
    if predicted.shape != (len(future),):
        raise ValueError("PREDICTION_SHAPE_MISMATCH")
    if not np.isfinite(predicted).all():
        raise ValueError("NON_FINITE_PREDICTION")
    return predicted
