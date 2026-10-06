"""E2E de preparación conservadora desde un XLSX real hasta regresión y descargas."""

import http.cookiejar
import io
import json
import os
import time
import urllib.request
import zipfile

BASE = os.getenv("APP_URL", "http://127.0.0.1:3000").rstrip("/") + "/api/v1"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
csrf = json.load(opener.open(BASE + "/session", timeout=10))["csrf_token"]


def call(path, method="GET", body=None):
    request = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    return json.load(opener.open(request, timeout=30))


def download(path):
    return opener.open(BASE + path, timeout=30).read()


def wait(job_id, timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = call(f"/jobs/{job_id}")
        if job["status"] in {"succeeded", "succeeded_with_warnings"}:
            return
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise RuntimeError(job)
        time.sleep(0.25)
    raise TimeoutError(job_id)


dataset = call("/datasets/from-example/preparation", "POST")
wait(dataset["job_id"])
original_record = call(f"/datasets/{dataset['dataset_id']}")
version = call(
    f"/datasets/{dataset['dataset_id']}/versions",
    "POST",
    {"sheet_name": "Datos", "header_row": 0},
)
wait(version["job_id"])
original_id = version["dataset_version_id"]
profile = call(f"/dataset-versions/{original_id}/profile")
by_name = {item["display_name"]: item["column_id"] for item in profile["columns"]}
recipe = {
    "schema_version": "1.0",
    "expected_columns": {column_id: name for name, column_id in by_name.items()},
    "columns": {
        by_name["Fecha venta"]: {
            "type": "date",
            "role": "variable",
            "date_format": "DMY",
            "invalid": "segregate",
        },
        by_name["Monto texto"]: {
            "type": "numeric",
            "role": "variable",
            "decimal_separator": ",",
            "thousands_separator": ".",
            "invalid": "segregate",
        },
        by_name["Zona"]: {
            "type": "categorical",
            "role": "variable",
            "trim": True,
            "empty_to_missing": True,
        },
        by_name["Operación ID"]: {"type": "auto", "role": "identifier"},
    },
    "exact_duplicates": "exclude",
    "filters": [],
}
preview = call(
    f"/dataset-versions/{original_id}/preparation-preview", "POST", {"recipe": recipe}
)
assert preview["rows_quarantined"] >= 2
assert preview["preview"]


def make_prepared():
    made = call(
        f"/dataset-versions/{original_id}/preparations", "POST", {"recipe": recipe}
    )
    wait(made["job_id"])
    return made["dataset_version_id"], call(
        f"/dataset-versions/{made['dataset_version_id']}/preparation"
    )


prepared_id, details = make_prepared()
second_id, second = make_prepared()
assert details["lineage"]["input_sha256"] == second["lineage"]["input_sha256"]
assert details["lineage"]["recipe_sha256"] == second["lineage"]["recipe_sha256"]
assert details["lineage"]["output_sha256"] == second["lineage"]["output_sha256"]
assert details["parent_version_id"] == original_id
assert call(f"/datasets/{dataset['dataset_id']}")["raw_sha256"] == original_record["raw_sha256"]

recipe_download = json.loads(
    download(f"/dataset-versions/{prepared_id}/recipe/download").decode()
)
assert recipe_download["schema_version"] == recipe["schema_version"]
assert recipe_download["expected_columns"] == recipe["expected_columns"]
for column_id, options in recipe["columns"].items():
    assert all(recipe_download["columns"][column_id][key] == value for key, value in options.items())
xlsx = download(f"/dataset-versions/{prepared_id}/prepared-excel/download")
with zipfile.ZipFile(io.BytesIO(xlsx)) as workbook:
    strings = b"".join(
        workbook.read(name)
        for name in workbook.namelist()
        if name in {"xl/workbook.xml", "xl/sharedStrings.xml"}
    )
    for sheet in [
        b"01_Datos_Preparados",
        b"02_Filas_Apartadas",
        b"03_Transformaciones",
        b"04_Calidad",
        b"05_Diccionario",
    ]:
        assert sheet in strings

prepared_profile = call(f"/dataset-versions/{prepared_id}/profile")
prepared_by_name = {
    item["display_name"]: item for item in prepared_profile["columns"]
}
assert prepared_by_name["Fecha venta"]["inferred_semantic_type"] == "datetime"
assert prepared_by_name["Monto texto"]["inferred_semantic_type"] == "numeric"
assert prepared_by_name["Operación ID"]["configured_role"] == "identifier"

config = {
    "schema_version": "1.0",
    "dataset_version_id": prepared_id,
    "goal": "estimate_value",
    "problem_type": "regression",
    "target_column_id": by_name["Ventas"],
    "date_column_id": None,
    "included_column_ids": [by_name["Monto texto"], by_name["Zona"], by_name["Visitas"]],
    "excluded_column_ids": [by_name["Operación ID"], by_name["Fecha venta"]],
    "depth": "quick",
    "primary_metric": "mae",
    "validation_context": "independent_records",
    "seed": 42,
    "forecast_options": None,
}
preflight = call("/preflights", "POST", {"config": config})
wait(preflight["job_id"])
ready = call(f"/preflights/{preflight['preflight_id']}")
assert ready["can_run"] is True
run = call(
    "/runs",
    "POST",
    {"preflight_id": preflight["preflight_id"], "config_sha256": ready["config_sha256"]},
)
wait(run["job_id"], 240)
result = call(f"/runs/{run['run_id']}/result")
assert result["analytical_outcome"] == "completed"
assert result["data_preparation"]["dataset_version_id"] == prepared_id

print(
    json.dumps(
        {
            "status": "PASS",
            "original_intact": True,
            "prepared_version": prepared_id,
            "repeat_version": second_id,
            "quarantined_rows": details["lineage"]["rows_quarantined"],
            "deterministic": True,
            "xlsx_opened": True,
            "analysis_completed": True,
        },
        ensure_ascii=False,
    )
)
