from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from local_ml_lab import __version__

PLAN_POLICY_VERSION = "analysis-plan-2.0"


def canonical_hash(value: dict) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def stable_seed(root_seed: int, candidate_id: str, unit_id: str) -> int:
    digest = hashlib.sha256(f"{root_seed}:{candidate_id}:{unit_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def json_scalar(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        if not np.isfinite(number):
            raise ValueError("NON_FINITE_VALUE")
        return number
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def stable_row_ids(index) -> list[str]:
    return [f"row-{position:07d}" for position, _ in enumerate(index, 1)]


def exact_row_groups(frame: pd.DataFrame) -> list[str]:
    columns = [column for column in frame.columns if not str(column).startswith("__lineage_")]
    groups = []
    for values in frame[columns].itertuples(index=False, name=None):
        payload = [json_scalar(value) for value in values]
        groups.append(
            hashlib.sha256(
                json.dumps(
                    payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
        )
    return groups


def materialize_splits(
    splits: list[tuple[np.ndarray, np.ndarray]],
    row_ids: list[str],
    role: str = "selection",
) -> list[dict]:
    return [
        {
            "unit_id": f"{role}-{index:02d}",
            "role": role,
            "train_row_ids": [row_ids[int(value)] for value in train],
            "validation_row_ids": [row_ids[int(value)] for value in validation],
            "train_count": len(train),
            "validation_count": len(validation),
        }
        for index, (train, validation) in enumerate(splits, 1)
    ]


def freeze_plan(payload: dict) -> dict:
    plan = {
        "plan_version": PLAN_POLICY_VERSION,
        "application_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        **payload,
    }
    # created_at is audit metadata, not part of the reproducible analytical identity.
    hashable = {key: value for key, value in plan.items() if key != "created_at"}
    plan["plan_sha256"] = canonical_hash(hashable)
    return plan
