"""Smoke E2E de API con datos sintéticos y descargas reales."""

import http.cookiejar
import io
import json
import os
import time
import urllib.error
import urllib.request
import zipfile

BASE = os.getenv("APP_URL", "http://localhost:3000").rstrip("/") + "/api/v1"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
session = json.load(opener.open(BASE + "/session", timeout=10))
csrf = session["csrf_token"]


def call(path, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    return json.load(opener.open(request, timeout=30))


def download(path):
    return opener.open(BASE + path, timeout=30).read()


def expect_http(path, method, expected):
    try:
        call(path, method)
    except urllib.error.HTTPError as exc:
        assert exc.code == expected, exc.read().decode()
        return
    raise AssertionError(f"Se esperaba HTTP {expected} para {method} {path}")


def wait(job_id, timeout=240):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = call(f"/jobs/{job_id}")
        if job["status"] in {"succeeded", "succeeded_with_warnings"}:
            return job
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(job)
        time.sleep(0.5)
    raise TimeoutError(job_id)


def analyze_example(example, problem, target_name, *, date_name=None, primary="mae"):
    preset = next(item for item in call("/examples")["items"] if item["id"] == example)
    dataset = call(f"/datasets/from-example/{example}", "POST")
    wait(dataset["job_id"])
    version = call(f"/datasets/{dataset['dataset_id']}/versions", "POST", preset["parser_options"])
    wait(version["job_id"])
    version_id = version["dataset_version_id"]
    profile = call(f"/dataset-versions/{version_id}/profile")
    by_name = {column["display_name"]: column["column_id"] for column in profile["columns"]}
    target = by_name[target_name]
    date = by_name[date_name] if date_name else None
    config = {
        "schema_version": "1.0",
        "dataset_version_id": version_id,
        "goal": "forecast" if problem == "forecasting" else "classify" if problem == "classification" else "estimate_value",
        "problem_type": problem,
        "target_column_id": target,
        "date_column_id": date,
        "included_column_ids": [
            column["column_id"]
            for column in profile["columns"]
            if not column["possible_id"] and column["column_id"] != target
        ],
        "excluded_column_ids": [
            column["column_id"] for column in profile["columns"] if column["possible_id"]
        ],
        "depth": "quick",
        "primary_metric": primary,
        "validation_context": "independent_records",
        "seed": 42,
        "forecast_options": {"horizon": 3, "aggregation": "mean"}
        if problem == "forecasting"
        else None,
    }
    preflight = call("/preflights", "POST", {"config": config})
    wait(preflight["job_id"])
    ready = call(f"/preflights/{preflight['preflight_id']}")
    run = call(
        "/runs",
        "POST",
        {"preflight_id": preflight["preflight_id"], "config_sha256": ready["config_sha256"]},
    )
    duplicate = call(
        "/runs",
        "POST",
        {"preflight_id": preflight["preflight_id"], "config_sha256": ready["config_sha256"]},
    )
    assert duplicate["run_id"] == run["run_id"]
    assert duplicate["job_id"] == run["job_id"]
    assert duplicate["deduplicated"] is True
    wait(run["job_id"])
    live = call(f"/runs/{run['run_id']}/live")
    unit_events = [event for event in live["last_events"] if event["event_type"] == "unit_completed"]
    frozen = next(event for event in live["last_events"] if event["event_type"] == "snapshot_frozen")
    assert unit_events and live["active_preview"]
    assert min(event["seq"] for event in unit_events) < frozen["seq"]
    incremental = call(f"/jobs/{run['job_id']}/events?after=0&limit=200")["items"]
    assert 0 < len(incremental) <= 200
    result = call(f"/runs/{run['run_id']}/result")
    assert result["analytical_outcome"] == "completed"
    assert result["primary_metric_id"] == primary
    return dataset["dataset_id"], run, result


regression_dataset, regression_run, regression = analyze_example(
    "regression", "regression", "Gasto_mensual"
)
classification_dataset, classification_run, classification = analyze_example(
    "classification", "classification", "Resultado", primary="balanced_accuracy"
)
forecast_dataset, forecast_run, forecast = analyze_example(
    "forecast_monthly", "forecasting", "Ventas", date_name="Mes"
)
assert regression["drivers"] and all(
    driver["fit_scope"] == "fold_train_only" for driver in regression["drivers"]
)
assert classification["diagnostics"]["confusion_matrix"]
assert any(row["evaluation_role"] == "forecast_future" for row in forecast["predictions"])
assert not any(row["evaluation_role"] == "final_test" for row in forecast["predictions"])

report = call(
    f"/runs/{regression_run['run_id']}/exports", "POST", {"formats": ["xlsx", "pdf"]}
)
duplicate_report = call(
    f"/runs/{regression_run['run_id']}/exports", "POST", {"formats": ["xlsx", "pdf"]}
)
assert duplicate_report["job_id"] == report["job_id"]
assert duplicate_report["deduplicated"] is True
wait(report["job_id"])
artifacts = call(f"/runs/{regression_run['run_id']}/artifacts")["items"]
assert {artifact["kind"] for artifact in artifacts} == {"xlsx", "pdf"}
payloads = {
    artifact["kind"]: download(f"/artifacts/{artifact['id']}/download")
    for artifact in artifacts
}
with zipfile.ZipFile(io.BytesIO(payloads["xlsx"])) as workbook:
    worksheets = [name for name in workbook.namelist() if name.startswith("xl/worksheets/sheet")]
    assert len(worksheets) == 14
assert payloads["pdf"].startswith(b"%PDF") and len(payloads["pdf"]) > 2_000

context = call(
    f"/runs/{regression_run['run_id']}/ai-context/preview",
    "POST",
    {"privacy_level": 1, "detail": "summary", "format": "md"},
)
assert "Explícame" in context["content"]
assert "R001" not in context["content"]
history = call("/runs")["items"]
assert {regression_run["run_id"], classification_run["run_id"], forecast_run["run_id"]} <= {
    item["id"] for item in history
}
expect_http(f"/datasets/{classification_dataset}", "DELETE", 409)
call(f"/runs/{classification_run['run_id']}", "DELETE")
call(f"/datasets/{classification_dataset}", "DELETE")
remaining_runs = call("/runs")["items"]
assert classification_run["run_id"] not in {item["id"] for item in remaining_runs}
print(
    json.dumps(
        {
            "status": "healthy",
            "runs": 3,
            "artifacts_opened": sorted(payloads),
            "history_persisted": True,
            "private_sample_absent": True,
            "safe_deletion_verified": True,
        },
        ensure_ascii=False,
    )
)
