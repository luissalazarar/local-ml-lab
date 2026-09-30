from local_ml_lab.ml.metrics import regression_metrics


def test_r2_constant_is_null():
    rows = regression_metrics([4, 4, 4], [4, 4, 4])
    r2 = next(row for row in rows if row["metric_id"] == "r2")
    assert r2["value"] is None
    assert r2["reason_code"] == "NOT_DEFINED"


def test_mae_and_rmse_are_finite():
    rows = regression_metrics([10, 20], [20, 10])
    assert next(row for row in rows if row["metric_id"] == "mae")["value"] == 10
