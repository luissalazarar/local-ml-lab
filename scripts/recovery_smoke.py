"""Crea o comprueba un job pendiente para validar caída y recuperación de cola."""

import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("APP_URL", "http://127.0.0.1:3000").rstrip("/") + "/api/v1"
cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
csrf = json.load(opener.open(BASE + "/session", timeout=10))["csrf_token"]


def request(path, method="GET"):
    return opener.open(
        urllib.request.Request(
            BASE + path,
            data=b"{}" if method == "POST" else None,
            method=method,
            headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
        ),
        timeout=10,
    )


if sys.argv[1] == "create":
    try:
        request("/datasets/from-example/regression", "POST")
    except urllib.error.HTTPError as error:
        body = json.load(error)
        detail = body["detail"]
        assert error.code == 503 and detail["code"] == "QUEUE_UNAVAILABLE", body
        print(json.dumps({"job_id": detail["job_id"], "http_status": error.code}))
    else:
        raise AssertionError("La API afirmó encolar aunque la cola estaba caída")
elif sys.argv[1] == "check":
    job_id = sys.argv[2]
    deadline = time.time() + 45
    while time.time() < deadline:
        job = json.load(request(f"/jobs/{job_id}"))
        if job["status"] == "succeeded":
            print(json.dumps({"job_id": job_id, "status": "recovered"}))
            break
        if job["status"] in {"failed", "cancelled", "interrupted"}:
            raise AssertionError(job)
        time.sleep(0.5)
    else:
        raise TimeoutError(job_id)
