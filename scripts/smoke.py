"""Smoke de API sin dependencias externas a la biblioteca estándar."""
import http.cookiejar
import json
import os
import time
import urllib.request

BASE = os.getenv("APP_URL", "http://localhost:3000").rstrip("/") + "/api/v1"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
session = json.load(opener.open(BASE + "/session", timeout=10))
csrf = session["csrf_token"]


def call(path, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json", "X-CSRF-Token": csrf})
    return json.load(opener.open(request, timeout=30))


def wait(job_id, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = call(f"/jobs/{job_id}")
        if job["status"] in {"succeeded", "succeeded_with_warnings"}: return job
        if job["status"] in {"failed", "cancelled", "interrupted"}: raise RuntimeError(job)
        time.sleep(1)
    raise TimeoutError(job_id)


dataset = call("/datasets/from-example/regression", "POST"); wait(dataset["job_id"])
version = call(f"/datasets/{dataset['dataset_id']}/versions", "POST", {}); wait(version["job_id"])
profile = call(f"/dataset-versions/{version['dataset_version_id']}/profile")
config = {"schema_version": "1.0", "dataset_version_id": version["dataset_version_id"], "goal": "estimate_value", "problem_type": "regression", "target_column_id": "c0005", "included_column_ids": [c["column_id"] for c in profile["columns"]], "excluded_column_ids": ["c0001"], "depth": "quick", "seed": 42}
pf = call("/preflights", "POST", {"config": config}); wait(pf["job_id"]); ready = call(f"/preflights/{pf['preflight_id']}")
run = call("/runs", "POST", {"preflight_id": pf["preflight_id"], "config_sha256": ready["config_sha256"]}); wait(run["job_id"])
result = call(f"/runs/{run['run_id']}/result")
assert result["analytical_outcome"] == "completed" and result["evaluation_metrics"]
report = call(f"/runs/{run['run_id']}/exports", "POST", {"formats": ["xlsx", "pdf"]}); wait(report["job_id"])
artifacts = call(f"/runs/{run['run_id']}/artifacts")
assert {a["kind"] for a in artifacts["items"]} == {"xlsx", "pdf"}
context = call(f"/runs/{run['run_id']}/ai-context/preview", "POST", {"privacy_level": 1, "detail": "summary", "format": "md"})
assert "Explícame" in context["content"]
print(json.dumps({"status": "healthy", "run_id": run["run_id"], "metrics": len(result["evaluation_metrics"]), "artifacts": len(artifacts["items"])}, ensure_ascii=False))
