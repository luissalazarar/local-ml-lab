"""Prueba el camino Excel con varias hojas y encabezado después de introducción."""

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
    request = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    return json.load(opener.open(request, timeout=30))


def wait(job_id):
    deadline = time.time() + 120
    while time.time() < deadline:
        job = call(f"/jobs/{job_id}")
        if job["status"] in {"succeeded", "succeeded_with_warnings"}:
            return
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(job)
        time.sleep(0.25)
    raise TimeoutError(job_id)


dataset = call("/datasets/from-example/excel_reader_cases", "POST")
wait(dataset["job_id"])
info = call(f"/datasets/{dataset['dataset_id']}")
assert info["safe_extension"] == ".xlsx"
assert info["metadata_json"]["sheet_names"] == ["Datos", "Auxiliar"]
version = call(
    f"/datasets/{dataset['dataset_id']}/versions",
    "POST",
    {"sheet_name": "Datos", "header_row": 2},
)
wait(version["job_id"])
profile = call(f"/dataset-versions/{version['dataset_version_id']}/profile")
by_name = {column["display_name"]: column for column in profile["columns"]}
assert profile["row_count"] == 24
assert by_name["Caso_ID"]["possible_id"] is True
assert by_name["Cantidad"]["null_count"] == 1
assert by_name["Cantidad"]["inferred_semantic_type"] == "numeric"
assert by_name["Categoría"]["inferred_semantic_type"] == "categorical"
assert by_name["Fecha"]["inferred_semantic_type"] == "datetime"
print(json.dumps({"status": "PASS", "sheets": info["metadata_json"]["sheet_names"], "header_row": 3, "rows": profile["row_count"]}, ensure_ascii=False))
