#!/usr/bin/env python3
"""Fail clearly when a release mirror drifts from version.json."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> None:
    release = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    display = release.get("display")
    semver = release.get("semver")
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(\d{4})", str(display))
    if not match:
        fail("version.json: display debe usar MAJOR.MINOR.BUILD con BUILD de cuatro dígitos")
    expected_semver = f"{int(match[1])}.{int(match[2])}.{int(match[3])}"
    if semver != expected_semver:
        fail(f"version.json: {display} debe corresponder a SemVer {expected_semver}, no {semver!r}")

    pyproject_text = (ROOT / "backend/pyproject.toml").read_text(encoding="utf-8")
    project_block = pyproject_text.split("[project]", 1)[1].split("\n[", 1)[0]
    backend_match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', project_block, re.MULTILINE)
    init_text = (ROOT / "backend/src/local_ml_lab/__init__.py").read_text(encoding="utf-8")
    init_match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    frontend = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    uv_text = (ROOT / "backend/uv.lock").read_text(encoding="utf-8")
    uv_match = re.search(r'\[\[package\]\]\s+name = "local-ml-lab"\s+version = "([^"]+)"', uv_text)
    mirrors = {
        "backend/pyproject.toml": backend_match.group(1) if backend_match else None,
        "backend/src/local_ml_lab/__init__.py": init_match.group(1) if init_match else None,
        "frontend/package.json": frontend.get("version"),
        "frontend/package-lock.json": lock.get("version"),
        "frontend/package-lock.json packages['']": lock.get("packages", {}).get("", {}).get("version"),
        "backend/uv.lock local package": uv_match.group(1) if uv_match else None,
    }
    drift = {path: value for path, value in mirrors.items() if value != semver}
    if drift:
        details = ", ".join(f"{path}={value!r}" for path, value in drift.items())
        fail(f"Drift de versión: version.json={semver!r}; {details}")
    print(f"PASS versión v{display} (SemVer {semver}) sincronizada en {len(mirrors)} mirrors")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL version check: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
