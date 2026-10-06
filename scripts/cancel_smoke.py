"""Comprueba cancelación acotada durante un candidato costoso con datos sintéticos."""

import csv
import http.cookiejar
import io
import json
import os
import time
import urllib.request
import uuid

BASE = os.getenv("APP_URL", "http://localhost:3000").rstrip("/") + "/api/v1"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
csrf = json.load(opener.open(BASE + "/session", timeout=10))["csrf_token"]


def call(path, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    return json.load(opener.open(request, timeout=30))


def wait(job_id, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = call(f"/jobs/{job_id}")
        if job["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.1)
    raise TimeoutError(job_id)


def synthetic_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", *[f"x{i}" for i in range(10)], "target"])
    for row in range(8_000):
        values = [row, *[((row * (column + 3)) % 997) / 13 for column in range(10)]]
        writer.writerow([f"S{row:05d}", *values[1:], values[2] * 1.7 + values[4] * 0.2])
    return output.getvalue().encode()


def upload_csv(payload):
    boundary = "----lml" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"cancel.csv\"\r\nContent-Type: text/csv\r\n\r\n".encode()
        + payload
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        BASE + "/datasets",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-CSRF-Token": csrf},
    )
    return json.load(opener.open(request, timeout=30))


dataset = upload_csv(synthetic_csv())
assert wait(dataset["job_id"])["status"] == "succeeded"
version = call(f"/datasets/{dataset['dataset_id']}/versions", "POST", {})
assert wait(version["job_id"])["status"] == "succeeded"
version_id = version["dataset_version_id"]
profile = call(f"/dataset-versions/{version_id}/profile")
target = profile["columns"][-1]["column_id"]
config = {
    "schema_version": "1.0",
    "dataset_version_id": version_id,
    "goal": "estimate_value",
    "problem_type": "regression",
    "target_column_id": target,
    "included_column_ids": [column["column_id"] for column in profile["columns"][1:-1]],
    "excluded_column_ids": [profile["columns"][0]["column_id"]],
    "depth": "recommended",
    "primary_metric": "mae",
    "validation_context": "independent_records",
    "seed": 42,
}
preflight = call("/preflights", "POST", {"config": config})
assert wait(preflight["job_id"])["status"] == "succeeded"
ready = call(f"/preflights/{preflight['preflight_id']}")
run = call(
    "/runs",
    "POST",
    {"preflight_id": preflight["preflight_id"], "config_sha256": ready["config_sha256"]},
)
deadline = time.time() + 120
cancelled_stage = None
after = 0
while time.time() < deadline:
    events = call(f"/jobs/{run['job_id']}/events?after={after}&limit=50")["items"]
    for event in events:
        after = max(after, event["seq"])
        payload = event.get("payload") or {}
        candidate_id = payload.get("candidate_id") or ""
        if event["event_type"] == "candidate_started" and candidate_id.startswith(
            "extra_trees"
        ):
            cancelled_stage = candidate_id
            break
        if event["event_type"] in {"completed", "failed", "cancelled"}:
            raise AssertionError(
                "El job terminó antes de alcanzar un candidato costoso: "
                + event["event_type"]
            )
    if cancelled_stage:
        break
    time.sleep(0.05)
assert cancelled_stage
started = time.monotonic()
response = call(f"/jobs/{run['job_id']}/cancel", "POST")
assert response["status"] in {"cancel_requested", "cancelled"}
final = wait(run["job_id"], timeout=15)
elapsed = time.monotonic() - started
assert final["status"] == "cancelled", final
assert elapsed < 10, elapsed
run_state = call(f"/runs/{run['run_id']}")
assert run_state["status"] == "cancelled" and not run_state["result_available"]
print(json.dumps({"status": "cancelled", "stage": cancelled_stage, "seconds": round(elapsed, 3)}))
