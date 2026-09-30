import hashlib
import json
from datetime import UTC, datetime

import pandas as pd
from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer

from local_ml_lab.data.readers import inspect_file, normalize_columns, profile_frame, read_frame
from local_ml_lab.db.models import Artifact, Dataset, DatasetVersion, Event, Job, Preflight, Run
from local_ml_lab.db.session import SessionLocal
from local_ml_lab.ml.engine import analyze
from local_ml_lab.reports import create_excel, create_pdf, sha
from local_ml_lab.settings import settings


def enqueue(job_id: str) -> bool:
    try:
        queue = Queue(
            "analysis",
            connection=Redis.from_url(settings.queue_url),
            default_timeout=1500,
            serializer=JSONSerializer,
        )
        queue.enqueue(process_job, job_id, job_id=job_id, result_ttl=3600, failure_ttl=86400)
        return True
    except Exception:
        return False


def emit(db, job, event_type, stage, message, completed=0, total=None):
    job.progress = {
        "stage": stage,
        "completed_units": completed,
        "total_units": total,
        "message": message,
    }
    job.heartbeat_at = datetime.now(UTC)
    db.add(
        Event(
            job_id=job.id,
            run_id=job.run_id,
            event_type=event_type,
            stage=stage,
            message_code=message,
            payload=job.progress,
        )
    )
    db.commit()


def process_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.status != "queued":
            return
        if job.cancel_requested_at:
            job.status = "cancelled"
            db.commit()
            return
        job.status = "running"
        db.commit()
        try:
            if job.job_type == "inspect_dataset":
                inspect_dataset(db, job)
            elif job.job_type == "prepare_dataset":
                prepare_dataset(db, job)
            elif job.job_type == "preflight":
                preflight(db, job)
            elif job.job_type == "analyze":
                run_analysis(db, job)
            elif job.job_type == "render_export":
                render_export(db, job)
            job.status = "succeeded"
            job.finished_at = datetime.now(UTC)
            emit(db, job, "completed", "finished", "Trabajo completado", 1, 1)
        except Exception as exc:
            job.status = "failed"
            job.error_code = type(exc).__name__
            job.finished_at = datetime.now(UTC)
            db.add(
                Event(
                    job_id=job.id,
                    run_id=job.run_id,
                    event_type="failed",
                    stage=job.progress.get("stage", "unknown"),
                    severity="error",
                    message_code=type(exc).__name__,
                    payload={},
                )
            )
            if job.run_id:
                run = db.get(Run, job.run_id)
                if run:
                    run.status = "failed"
            db.commit()
            raise


def inspect_dataset(db, job):
    dataset = db.get(Dataset, job.payload["dataset_id"])
    path = settings.data_root / job.payload["relative_path"]
    emit(db, job, "stage_started", "inspect", "Inspeccionando archivo")
    dataset.metadata_json = inspect_file(path)
    dataset.status = "ready"
    db.commit()


def prepare_dataset(db, job):
    version = db.get(DatasetVersion, job.dataset_version_id)
    dataset = db.get(Dataset, version.dataset_id)
    path = settings.data_root / f"uploads/{dataset.id}/original{dataset.safe_extension}"
    emit(db, job, "stage_started", "parse", "Interpretando datos")
    frame, mapping = normalize_columns(read_frame(path, version.parser_options))
    out = settings.data_root / "datasets" / version.id
    out.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out / "canonical.parquet", index=False)
    emit(db, job, "stage_started", "profile", "Revisando calidad")
    profile = profile_frame(frame, mapping)
    (out / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    version.status = "ready"
    version.row_count = len(frame)
    version.column_count = len(frame.columns)
    version.profile_ref = f"datasets/{version.id}/profile.json"
    version.canonical_ref = f"datasets/{version.id}/canonical.parquet"
    db.commit()


def preflight(db, job):
    pf = db.get(Preflight, job.payload["preflight_id"])
    config = pf.requested_config
    emit(db, job, "stage_started", "preflight", "Diseñando una evaluación sin fugas")
    version = db.get(DatasetVersion, config["dataset_version_id"])
    if not version or version.status != "ready":
        raise ValueError("DATASET_VERSION_NOT_READY")
    warnings = []
    if version.row_count < 20:
        warnings.append("SMALL_DATASET")
    if config["problem_type"] != "exploration" and not config.get("target_column_id"):
        raise ValueError("TARGET_REQUIRED")
    pf.resolved_config = config
    pf.config_sha256 = canonical_hash(config)
    pf.can_run = True
    pf.status = "ready"
    pf.warning_codes = warnings
    db.commit()


def run_analysis(db, job):
    run = db.get(Run, job.run_id)
    pf = db.get(Preflight, run.preflight_id)
    version = db.get(DatasetVersion, run.dataset_version_id)
    run.status = "running"
    db.commit()
    emit(db, job, "stage_started", "prepare", "Preparando variables")
    frame = pd.read_parquet(settings.data_root / version.canonical_ref)
    profile = json.loads((settings.data_root / version.profile_ref).read_text(encoding="utf-8"))

    def progress(stage, message, done, total):
        db.refresh(job)
        if job.cancel_requested_at:
            raise RuntimeError("CANCELLED")
        emit(db, job, "candidate_started", stage, message, done, total)

    result = analyze(frame, profile, pf.resolved_config, progress)
    result["run_id"] = run.id
    out = settings.data_root / "runs" / run.id
    out.mkdir(parents=True, exist_ok=True)
    path = out / "analysis_result.json"
    raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode()
    path.write_bytes(raw)
    (out / "analysis_config.json").write_text(
        json.dumps(pf.resolved_config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.result_available = True
    run.result_ref = f"runs/{run.id}/analysis_result.json"
    run.result_sha256 = hashlib.sha256(raw).hexdigest()
    run.status = "succeeded"
    run.evidence_mode = result.get("validation_plan", {}).get("evidence_mode")
    run.analytical_outcome = result["analytical_outcome"]
    run.finished_at = datetime.now(UTC)
    db.commit()


def render_export(db, job):
    run = db.get(Run, job.run_id)
    result = json.loads((settings.data_root / run.result_ref).read_text(encoding="utf-8"))
    out = settings.data_root / "runs" / run.id / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    for kind in job.payload["formats"]:
        path = out / f"reporte.{kind}"
        create_excel(result, path) if kind == "xlsx" else create_pdf(result, path)
        db.add(
            Artifact(
                run_id=run.id,
                kind=kind,
                relative_path=str(path.relative_to(settings.data_root)).replace("\\", "/"),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if kind == "xlsx"
                else "application/pdf",
                size_bytes=path.stat().st_size,
                sha256=sha(path),
            )
        )
    db.commit()


def canonical_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
