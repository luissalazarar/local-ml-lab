import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from local_ml_lab import main
from local_ml_lab.settings import Settings

ROOT = Path(__file__).resolve().parents[2]


class ChunkedUpload:
    filename = "large.csv"

    def __init__(self, size: int):
        self.remaining = size

    async def read(self, size: int) -> bytes:
        chunk_size = min(size, self.remaining)
        self.remaining -= chunk_size
        return b"x" * chunk_size


class FakeDb:
    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = "job-test"

    def commit(self) -> None:
        pass


def test_default_upload_limit_is_200_mib(monkeypatch):
    monkeypatch.delenv("MAX_UPLOAD_MIB", raising=False)
    configured = Settings()
    assert configured.max_upload_mib == 200
    assert configured.max_rows == 4_000_000
    assert configured.max_cells == 20_000_000


def test_large_upload_transport_streams_and_spills_to_data_volume():
    nginx = (ROOT / "docker" / "nginx.conf").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "client_max_body_size 201m;" in nginx
    assert "proxy_request_buffering off;" in nginx
    assert "TMPDIR: /data/tmp" in compose


def test_upload_limit_accepts_below_limit_and_rejects_above(tmp_path, monkeypatch):
    dataset_number = 0

    def create_dataset(*_args):
        nonlocal dataset_number
        dataset_number += 1
        return SimpleNamespace(id=f"dataset-{dataset_number}", size_bytes=0, raw_sha256="")

    monkeypatch.setattr(main.settings, "data_root", tmp_path)
    monkeypatch.setattr(main.settings, "max_upload_mib", 2)
    monkeypatch.setattr(main, "create_dataset_record", create_dataset)
    monkeypatch.setattr(main, "dispatch_or_503", lambda *_args: None)

    accepted = asyncio.run(
        main.upload_dataset(file=ChunkedUpload(2 * 1024 * 1024), db=FakeDb())
    )
    assert accepted["dataset_id"] == "dataset-1"

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            main.upload_dataset(file=ChunkedUpload(2 * 1024 * 1024 + 1), db=FakeDb())
        )
    assert exc_info.value.status_code == 413
    assert not (tmp_path / "uploads" / "dataset-2" / "original.csv").exists()
