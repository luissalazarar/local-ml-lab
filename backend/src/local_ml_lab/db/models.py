from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def uid() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    original_filename: Mapped[str] = mapped_column(String)
    safe_extension: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    raw_sha256: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"))
    status: Mapped[str] = mapped_column(String, default="queued")
    parser_options: Mapped[dict] = mapped_column(JSON, default=dict)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    profile_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    canonical_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    version_kind: Mapped[str] = mapped_column(String, default="original")
    parent_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recipe_json: Mapped[dict] = mapped_column(JSON, default=dict)
    recipe_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    quarantine_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    quality_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    prepared_excel_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    input_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    recipe_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    input_row_count: Mapped[int] = mapped_column(Integer, default=0)
    quarantined_row_count: Mapped[int] = mapped_column(Integer, default=0)
    transformation_count: Mapped[int] = mapped_column(Integer, default=0)
    preparation_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Preflight(Base):
    __tablename__ = "preflights"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    job_id: Mapped[str] = mapped_column(String)
    requested_config: Mapped[dict] = mapped_column(JSON)
    resolved_config: Mapped[dict] = mapped_column(JSON, default=dict)
    config_sha256: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="queued")
    can_run: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_codes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    dataset_version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    preflight_id: Mapped[str] = mapped_column(ForeignKey("preflights.id"))
    display_name: Mapped[str] = mapped_column(String, default="Análisis")
    goal: Mapped[str] = mapped_column(String)
    problem_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    analytical_outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    result_available: Mapped[bool] = mapped_column(Boolean, default=False)
    result_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    result_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    latest_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    dataset_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    job_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued")
    progress: Mapped[dict] = mapped_column(JSON, default=dict)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Event(Base):
    __tablename__ = "events"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="info")
    message_code: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Artifact(Base):
    __tablename__ = "artifacts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="ready")
    relative_path: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    route: Mapped[str] = mapped_column(String, primary_key=True)
    request_sha256: Mapped[str] = mapped_column(String)
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
