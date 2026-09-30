import hashlib
import json
import multiprocessing
import os
import queue as queue_module
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import psutil
from redis import Redis
from rq import Queue
from rq.serializers import JSONSerializer
from sqlalchemy import select

from local_ml_lab import __version__
from local_ml_lab.data.preparation import (
    apply_recipe,
    export_prepared_excel,
    frame_hash,
    quality_comparison,
)
from local_ml_lab.data.preparation import (
    canonical_hash as preparation_hash,
)
from local_ml_lab.data.readers import inspect_file, normalize_columns, profile_frame, read_frame
from local_ml_lab.db.models import Artifact, Dataset, DatasetVersion, Event, Job, Preflight, Run
from local_ml_lab.db.session import SessionLocal
from local_ml_lab.ml.engine import analyze, resolve_primary_metric
from local_ml_lab.preflight import evaluate_preflight
from local_ml_lab.reports import create_excel, create_pdf, sha
from local_ml_lab.settings import settings


class JobCancelled(Exception):
    pass


class JobTimedOut(Exception):
    pass


def queue_connection():
    return Redis.from_url(settings.queue_url, socket_connect_timeout=2, socket_timeout=3)


def enqueue(job_id: str) -> bool:
    try:
        connection = queue_connection()
        connection.ping()
        queue = Queue(
            "analysis",
            connection=connection,
            default_timeout=settings.analysis_timeout_seconds + 60,
            serializer=JSONSerializer,
        )
        existing = queue.fetch_job(job_id)
        if existing:
            status = existing.get_status(refresh=True)
            if status in {"queued", "started", "scheduled", "deferred"}:
                return True
            existing.delete()
        queue.enqueue(
            process_job,
            job_id,
            job_id=job_id,
            result_ttl=3600,
            failure_ttl=86400,
        )
        return True
    except Exception:
        return False


def reconcile_queued_jobs() -> list[str]:
    """Reconcile the durable SQLite outbox without disturbing running jobs."""
    with SessionLocal() as db:
        pending = db.scalars(select(Job.id).where(Job.status == "queued")).all()
    return [job_id for job_id in pending if enqueue(job_id)]


def recover_pending_jobs() -> dict:
    """Recover SQLite outbox entries after a worker/queue restart."""
    recovered = []
    interrupted = []
    with SessionLocal() as db:
        active = db.scalars(
            select(Job).where(Job.status.in_(["queued", "running", "cancel_requested"]))
        ).all()
        for job in active:
            if job.cancel_requested_at:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                continue
            if job.status in {"running", "cancel_requested"}:
                job.status = "interrupted"
                job.error_code = "WORKER_RESTARTED"
                job.finished_at = datetime.now(UTC)
                interrupted.append(job.id)
                replacement = Job(
                    job_type=job.job_type,
                    run_id=job.run_id,
                    dataset_version_id=job.dataset_version_id,
                    payload=job.payload,
                    progress={"stage": "recovery", "message": "Recuperado tras reinicio"},
                )
                db.add(replacement)
                db.flush()
                if job.run_id:
                    run = db.get(Run, job.run_id)
                    if run:
                        run.latest_job_id = replacement.id
                        run.status = "queued"
                recovered.append(replacement.id)
            else:
                recovered.append(job.id)
        db.commit()
    enqueued = [job_id for job_id in recovered if enqueue(job_id)]
    return {"interrupted": interrupted, "recovered": enqueued}


def emit(db, job, event_type, stage, message, completed=0, total=None, payload=None):
    if job.job_type == "analyze" and event_type == "completed":
        # The generic job completion must not erase the analytical unit counters.
        completed = job.progress.get("completed_units", completed)
        total = job.progress.get("total_units", total)
    event_payload = {
        "event_version": "1.0",
        "event_type": event_type,
        "run_id": job.run_id,
        "job_id": job.id,
        "attempt_id": job.id,
        "stage": stage,
        "completed_units": completed,
        "total_units": total,
        "message_code": message,
        **(payload or {}),
    }
    live_state = _reduce_live_state(job.progress.get("live_state", {}), event_payload)
    job.progress = {
        "stage": stage,
        "completed_units": completed,
        "total_units": total,
        "message": message,
        "live_state": live_state,
    }
    job.heartbeat_at = datetime.now(UTC)
    db.add(
        Event(
            job_id=job.id,
            run_id=job.run_id,
            event_type=event_type,
            stage=stage,
            message_code=message,
            payload=event_payload,
        )
    )
    db.commit()


def process_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job or job.status != "queued":
            return
        if job.cancel_requested_at:
            _finish_cancelled(db, job)
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.heartbeat_at = datetime.now(UTC)
        db.commit()
        try:
            if job.job_type == "inspect_dataset":
                inspect_dataset(db, job)
            elif job.job_type == "prepare_dataset":
                prepare_dataset(db, job)
            elif job.job_type == "apply_preparation":
                apply_preparation(db, job)
            elif job.job_type == "preflight":
                preflight(db, job)
            elif job.job_type == "analyze":
                run_analysis(db, job)
            elif job.job_type == "render_export":
                render_export(db, job)
            else:
                raise ValueError("UNKNOWN_JOB_TYPE")
            db.refresh(job)
            if job.cancel_requested_at:
                raise JobCancelled()
            job.status = "succeeded"
            job.finished_at = datetime.now(UTC)
            emit(db, job, "completed", "finished", "Trabajo completado", 1, 1)
        except JobCancelled:
            _finish_cancelled(db, job)
        except Exception as exc:
            _finish_failed(db, job, exc)
            raise


def _finish_cancelled(db, job):
    job.status = "cancelled"
    job.error_code = None
    job.finished_at = datetime.now(UTC)
    if job.run_id and job.job_type == "analyze":
        run = db.get(Run, job.run_id)
        if run and not run.result_available:
            run.status = "cancelled"
    db.add(
        Event(
            job_id=job.id,
            run_id=job.run_id,
            event_type="cancelled",
            stage=job.progress.get("stage", "unknown"),
            message_code="CANCELLED_BY_USER",
            payload={},
        )
    )
    db.commit()


def _finish_failed(db, job, exc):
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
            payload={"detail": str(exc)[:300]},
        )
    )
    if job.run_id and job.job_type == "analyze":
        run = db.get(Run, job.run_id)
        if run and not run.result_available:
            run.status = "failed"
    db.commit()


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
    _raise_if_cancelled(db, job)
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
    version.version_kind = "original"
    version.input_row_count = len(frame)
    version.input_sha256 = frame_hash(frame)
    version.output_sha256 = version.input_sha256
    db.commit()


def apply_preparation(db, job):
    version = db.get(DatasetVersion, job.dataset_version_id)
    parent = db.get(DatasetVersion, version.parent_version_id)
    if not parent or parent.status != "ready":
        raise ValueError("PARENT_DATASET_VERSION_NOT_READY")
    dataset = db.get(Dataset, version.dataset_id)
    source = pd.read_parquet(settings.data_root / parent.canonical_ref)
    original_profile = json.loads(
        (settings.data_root / parent.profile_ref).read_text(encoding="utf-8")
    )
    mapping = [
        {
            "column_id": item["column_id"],
            "display_name": item["display_name"],
            "source_name": item["source_name"],
            "position": item["position"],
        }
        for item in original_profile["columns"]
    ]
    emit(db, job, "stage_started", "prepare", "Aplicando la preparación confirmada")
    result = apply_recipe(source, version.recipe_json, source_extension=dataset.safe_extension)
    out = settings.data_root / "datasets" / version.id
    out.mkdir(parents=True, exist_ok=True)
    result.frame.to_parquet(out / "canonical.parquet", index=False)
    prepared_profile = profile_frame(
        result.frame, mapping, type_overrides=result.type_overrides, roles=result.roles
    )
    quality = quality_comparison(original_profile, prepared_profile)
    recipe = version.recipe_json
    recipe_path = out / "recipe.json"
    recipe_path.write_text(
        json.dumps(recipe, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    quarantine_path = out / "quarantine.json"
    quarantine_path.write_text(
        json.dumps(result.quarantined, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    quality_path = out / "quality.json"
    quality_path.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")
    profile_path = out / "profile.json"
    profile_path.write_text(
        json.dumps(prepared_profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    excel_path = out / "datos-preparados.xlsx"
    export_prepared_excel(
        excel_path,
        result.frame,
        mapping,
        result.quarantined,
        result.transformations,
        quality,
        result.roles,
    )
    output_hash = frame_hash(result.frame)
    summary = {
        "rows_input": len(source),
        "rows_output": len(result.frame),
        "rows_quarantined": len({row["row_id"] for row in result.quarantined}),
        "transformations": result.transformations,
        "preview": result.preview,
        "quality": quality,
        "roles": result.roles,
        "type_overrides": result.type_overrides,
        "source_extension": dataset.safe_extension,
    }
    version.status = "ready"
    version.version_kind = "prepared"
    version.row_count = len(result.frame)
    version.column_count = len(result.frame.columns)
    version.profile_ref = f"datasets/{version.id}/profile.json"
    version.canonical_ref = f"datasets/{version.id}/canonical.parquet"
    version.recipe_ref = f"datasets/{version.id}/recipe.json"
    version.quarantine_ref = f"datasets/{version.id}/quarantine.json"
    version.quality_ref = f"datasets/{version.id}/quality.json"
    version.prepared_excel_ref = f"datasets/{version.id}/datos-preparados.xlsx"
    version.input_sha256 = frame_hash(source)
    version.recipe_sha256 = preparation_hash(recipe)
    version.output_sha256 = output_hash
    version.input_row_count = len(source)
    version.quarantined_row_count = summary["rows_quarantined"]
    version.transformation_count = len(result.transformations)
    version.preparation_summary = summary
    db.commit()


def preflight(db, job):
    pf = db.get(Preflight, job.payload["preflight_id"])
    config = pf.requested_config
    config["_application_version"] = __version__
    config["_policy_versions"] = {
        "analysis_plan": "analysis-plan-2.0",
        "selection": "selection-policy-2.0",
        "reliability": "reliability-policy-1.2",
    }
    emit(db, job, "stage_started", "preflight", "Diseñando una evaluación sin fugas")
    version = db.get(DatasetVersion, config["dataset_version_id"])
    if not version or version.status != "ready":
        raise ValueError("DATASET_VERSION_NOT_READY")
    profile = json.loads((settings.data_root / version.profile_ref).read_text(encoding="utf-8"))
    known = {column["column_id"] for column in profile["columns"]}
    referenced = set(config.get("included_column_ids") or []) | set(
        config.get("excluded_column_ids") or []
    )
    if referenced - known:
        raise ValueError("UNKNOWN_COLUMN_IDS")
    if (
        set(config.get("included_column_ids") or []) & set(config.get("excluded_column_ids") or [])
    ) - {config.get("target_column_id")}:
        raise ValueError("COLUMN_INCLUDED_AND_EXCLUDED")
    if config["problem_type"] != "exploration" and not config.get("target_column_id"):
        raise ValueError("TARGET_REQUIRED")
    if config["problem_type"] == "forecasting" and not config.get("date_column_id"):
        raise ValueError("FORECAST_COLUMNS_REQUIRED")
    if config["problem_type"] != "exploration":
        config["primary_metric"] = resolve_primary_metric(
            config["problem_type"], config.get("primary_metric")
        )
    frame = pd.read_parquet(settings.data_root / version.canonical_ref)
    if version.version_kind == "prepared":
        config["_preparation"] = {
            "dataset_version_id": version.id,
            "parent_version_id": version.parent_version_id,
            "transformations": version.preparation_summary.get("transformations", []),
            "rows_input": version.input_row_count,
            "rows_analyzed": version.row_count,
            "rows_quarantined": version.quarantined_row_count,
            "recipe_sha256": version.recipe_sha256,
            "output_sha256": version.output_sha256,
        }
    summary = evaluate_preflight(frame, profile, config)
    config["_preflight"] = summary
    pf.resolved_config = config
    pf.config_sha256 = canonical_hash(config)
    pf.can_run = summary["can_run"]
    pf.status = "ready"
    pf.warning_codes = [warning["code"] for warning in summary["warnings"]]
    db.commit()


def _analysis_child(frame_path, profile_path, config, result_path, updates):
    try:
        frame = pd.read_parquet(frame_path)
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))

        def progress(event):
            updates.put(("event", event))

        result = analyze(frame, profile, config, progress)
        Path(result_path).write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        updates.put(("done",))
    except BaseException as exc:
        updates.put(("error", type(exc).__name__, str(exc)[:500]))


def run_analysis(db, job):
    run = db.get(Run, job.run_id)
    pf = db.get(Preflight, run.preflight_id)
    version = db.get(DatasetVersion, run.dataset_version_id)
    run.status = "running"
    db.commit()
    emit(db, job, "stage_started", "prepare", "Preparando variables")
    out = settings.data_root / "runs" / run.id
    out.mkdir(parents=True, exist_ok=True)
    pending_path = out / f".analysis-{job.id}.json"
    context = multiprocessing.get_context("spawn")
    updates = context.Queue()
    process = context.Process(
        target=_analysis_child,
        args=(
            str(settings.data_root / version.canonical_ref),
            str(settings.data_root / version.profile_ref),
            pf.resolved_config,
            str(pending_path),
            updates,
        ),
        name=f"analysis-{job.id}",
    )
    process.start()
    deadline = time.monotonic() + settings.analysis_timeout_seconds
    last_heartbeat = 0.0
    child_error = None
    try:
        while process.is_alive():
            now = time.monotonic()
            db.refresh(job)
            if job.cancel_requested_at:
                terminate_process_tree(process.pid)
                process.join(timeout=5)
                raise JobCancelled()
            if now >= deadline:
                terminate_process_tree(process.pid)
                process.join(timeout=5)
                raise JobTimedOut("ANALYSIS_TIMEOUT")
            child_error = _drain_updates(db, job, updates, child_error)
            if now - last_heartbeat >= settings.heartbeat_interval_seconds:
                job.heartbeat_at = datetime.now(UTC)
                db.commit()
                last_heartbeat = now
            process.join(timeout=0.25)
        child_error = _drain_updates(db, job, updates, child_error)
        if child_error:
            raise RuntimeError(f"{child_error[0]}: {child_error[1]}")
        if process.exitcode != 0 or not pending_path.exists():
            raise RuntimeError("ANALYSIS_PROCESS_FAILED")
        _raise_if_cancelled(db, job)
        result = json.loads(pending_path.read_text(encoding="utf-8"))
        result["run_id"] = run.id
        raw = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode()
        final_path = out / "analysis_result.json"
        final_pending = out / f".publish-{job.id}.json"
        final_pending.write_bytes(raw)
        _raise_if_cancelled(db, job)
        os.replace(final_pending, final_path)
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
    finally:
        if process.is_alive():
            terminate_process_tree(process.pid)
            process.join(timeout=5)
        pending_path.unlink(missing_ok=True)


def _drain_updates(db, job, updates, child_error):
    while True:
        try:
            update = updates.get_nowait()
        except queue_module.Empty:
            return child_error
        if update[0] == "event":
            event = update[1]
            emit(
                db,
                job,
                event["event_type"],
                event["stage"],
                event["message_code"],
                event.get("completed_units", 0),
                event.get("total_units"),
                {
                    key: value
                    for key, value in event.items()
                    if key
                    not in {
                        "event_type",
                        "stage",
                        "message_code",
                        "completed_units",
                        "total_units",
                    }
                },
            )
        elif update[0] == "error":
            child_error = (update[1], update[2])


def _reduce_live_state(previous, event):
    """Project structured events into a bounded, restart-safe view."""
    state = {
        "revision": int(previous.get("revision", 0)) + 1,
        "plan_summary": previous.get("plan_summary"),
        "candidates": dict(previous.get("candidates", {})),
        "active_candidate_id": previous.get("active_candidate_id"),
        "active_unit_id": previous.get("active_unit_id"),
        "active_preview": previous.get("active_preview"),
        "ranking": list(previous.get("ranking", [])),
        "selection_decision": previous.get("selection_decision"),
        "final_test": previous.get("final_test"),
        "result_summary": previous.get("result_summary"),
    }
    event_type = event.get("event_type")
    candidate_id = event.get("candidate_id")
    if event_type == "plan_ready":
        state["plan_summary"] = event.get("plan_summary")
    if event_type == "candidate_started":
        state["active_candidate_id"] = candidate_id
        state["active_preview"] = None
        state["candidates"][candidate_id] = {
            "candidate_id": candidate_id,
            "display_name": event.get("display_name"),
            "status": "running",
        }
    if event_type == "unit_started":
        state["active_candidate_id"] = candidate_id
        state["active_unit_id"] = event.get("unit_id")
    if event_type == "unit_completed":
        state["active_candidate_id"] = candidate_id
        state["active_unit_id"] = event.get("unit_id")
        state["active_preview"] = {
            "candidate_id": candidate_id,
            "unit_id": event.get("unit_id"),
            "evaluation_role": event.get("evaluation_role"),
            "partial_metrics": event.get("partial_metrics", []),
            "unit_metrics": event.get("unit_metrics", []),
            "predictions": list(event.get("preview", []))[:200],
            "training_end": event.get("training_end"),
        }
    if event_type in {"candidate_completed", "candidate_failed", "candidate_skipped"}:
        summary = event.get("candidate") or {
            "candidate_id": candidate_id,
            "status": "ineligible" if event_type == "candidate_skipped" else "failed",
            "reason_code": event.get("message_code"),
        }
        state["candidates"][candidate_id] = summary
        complete = [
            value
            for value in state["candidates"].values()
            if value.get("status") == "completed" and value.get("primary_value") is not None
        ]
        direction = (state.get("plan_summary") or {}).get("metric_direction", "min")
        state["ranking"] = sorted(
            complete,
            key=lambda value: (
                -value["primary_value"] if direction == "max" else value["primary_value"],
                value.get("complexity_rank", 999),
            ),
        )
    if event_type == "selection_completed":
        state["selection_decision"] = event.get("selection_decision")
    if event_type == "final_test_completed":
        state["final_test"] = event.get("final_test")
    if event_type == "snapshot_frozen":
        state["result_summary"] = event.get("result_summary")
    # SQLite JSON mutation tracking requires a fresh object and candidates remain bounded by catalog.
    return state


def terminate_process_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    descendants = parent.children(recursive=True)
    for process in descendants:
        process.terminate()
    _, alive = psutil.wait_procs(descendants, timeout=2)
    for process in alive:
        process.kill()
    psutil.wait_procs(alive, timeout=1)
    try:
        parent.terminate()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if not parent.is_running() or parent.status() == psutil.STATUS_ZOMBIE:
                return
            time.sleep(0.05)
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def render_export(db, job):
    run = db.get(Run, job.run_id)
    result = json.loads((settings.data_root / run.result_ref).read_text(encoding="utf-8"))
    out = settings.data_root / "runs" / run.id / "artifacts"
    out.mkdir(parents=True, exist_ok=True)
    for kind in dict.fromkeys(job.payload["formats"]):
        _raise_if_cancelled(db, job)
        artifact_id = str(uuid4())
        path = out / f"reporte-{artifact_id}.{kind}"
        pending = out / f".{artifact_id}.{kind}.tmp"
        try:
            create_excel(result, pending) if kind == "xlsx" else create_pdf(result, pending)
            _raise_if_cancelled(db, job)
            os.replace(pending, path)
            db.add(
                Artifact(
                    id=artifact_id,
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
        finally:
            pending.unlink(missing_ok=True)


def _raise_if_cancelled(db, job):
    db.refresh(job)
    if job.cancel_requested_at:
        raise JobCancelled()


def canonical_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
