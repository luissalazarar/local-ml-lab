"""Ejecuta los cinco presets Excel-first contra el stack real."""

import http.cookiejar
import json
import os
import time
import urllib.request

BASE = os.getenv("APP_URL", "http://127.0.0.1:3000").rstrip("/") + "/api/v1"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
session = json.load(opener.open(BASE + "/session", timeout=10))
csrf = session["csrf_token"]


def call(path, method="GET", body=None):
    request = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    return json.load(opener.open(request, timeout=30))


def wait(job_id, timeout=300):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = call(f"/jobs/{job_id}")
        if job["status"] in {"succeeded", "succeeded_with_warnings"}:
            return
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(job)
        time.sleep(0.5)
    raise TimeoutError(job_id)


results = {}
for preset in call("/examples")["items"]:
    assert preset["format"] == "xlsx" and preset["parser_options"]["sheet_name"] == "Datos"
    dataset = call(f"/datasets/from-example/{preset['id']}", "POST")
    wait(dataset["job_id"])
    version = call(
        f"/datasets/{dataset['dataset_id']}/versions", "POST", preset["parser_options"]
    )
    wait(version["job_id"])
    profile = call(f"/dataset-versions/{version['dataset_version_id']}/profile")
    by_name = {column["display_name"]: column["column_id"] for column in profile["columns"]}
    target = by_name[preset["target"]["name"]] if preset["target"] else None
    date_column = by_name[preset["date_column"]["name"]] if preset["date_column"] else None
    included = [by_name[name] for name in preset["included_columns"]]
    config = {
        "schema_version": "1.0",
        "dataset_version_id": version["dataset_version_id"],
        "goal": preset["goal"],
        "problem_type": preset["problem_type"],
        "target_column_id": target,
        "date_column_id": date_column,
        "included_column_ids": included,
        "excluded_column_ids": [
            column["column_id"] for column in profile["columns"] if column["possible_id"]
        ],
        "depth": preset["depth"],
        "primary_metric": preset["primary_metric"],
        "validation_context": "independent_records",
        "seed": 42,
        "forecast_options": {
            "horizon": preset["forecast_horizon"],
            "aggregation": preset["aggregation"],
        }
        if preset["problem_type"] == "forecasting"
        else None,
    }
    preflight = call("/preflights", "POST", {"config": config})
    wait(preflight["job_id"])
    ready = call(f"/preflights/{preflight['preflight_id']}")
    assert ready["can_run"], {preset["id"]: ready["blockers"]}
    run = call(
        "/runs",
        "POST",
        {"preflight_id": ready["id"], "config_sha256": ready["config_sha256"]},
    )
    wait(run["job_id"])
    result = call(f"/runs/{run['run_id']}/result")
    expected = "exploration_only" if preset["id"] == "exploration" else "completed"
    assert result["analytical_outcome"] == expected
    results[preset["id"]] = result

assert results["regression"]["evaluation_metrics"] and results["regression"]["predictions"]
assert results["classification"]["diagnostics"]["confusion_matrix"]
assert {row["metric_id"] for row in results["classification"]["evaluation_metrics"]} >= {
    "accuracy", "balanced_accuracy", "macro_f1"
}
assert any(row["evaluation_role"] == "forecast_future" for row in results["forecast_monthly"]["predictions"])
assert results["drivers"]["drivers"]
assert not results["exploration"]["evaluation_metrics"]
print(json.dumps({"status": "PASS", "examples": {key: value["analytical_outcome"] for key, value in results.items()}}, ensure_ascii=False))
