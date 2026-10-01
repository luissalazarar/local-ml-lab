import multiprocessing
import subprocess
import sys
import time

import psutil

from local_ml_lab.jobs import _reduce_live_state, terminate_process_tree


def process_with_descendant():
    subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    time.sleep(60)


def test_termination_stops_active_process_and_descendants():
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=process_with_descendant)
    process.start()
    deadline = time.time() + 5
    descendants = []
    while time.time() < deadline:
        descendants = psutil.Process(process.pid).children(recursive=True)
        if descendants:
            break
        time.sleep(0.05)
    assert descendants
    descendant_pids = [child.pid for child in descendants]
    started = time.monotonic()
    terminate_process_tree(process.pid)
    process.join(timeout=5)
    assert time.monotonic() - started < 6
    assert not process.is_alive()
    deadline = time.time() + 2
    while time.time() < deadline:
        active = []
        for pid in descendant_pids:
            try:
                child = psutil.Process(pid)
                if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                    active.append(pid)
            except psutil.NoSuchProcess:
                pass
        if not active:
            break
        time.sleep(0.05)
    assert not active


def test_live_projection_is_bounded_and_replayed_events_do_not_increment_counts():
    state = _reduce_live_state(
        {},
        {
            "event_type": "plan_ready",
            "plan_summary": {
                "eligible_candidate_count": 2,
                "evaluation_unit_count": 5,
                "metric_direction": "min",
            },
        },
    )
    started = {
        "event_type": "candidate_started",
        "candidate_id": "ridge",
        "display_name": "Ridge",
    }
    state = _reduce_live_state(state, started)
    completed = {
        "event_type": "unit_completed",
        "candidate_id": "ridge",
        "unit_id": "selection-01",
        "evaluation_role": "selection",
        "preview_ref": "live/ridge/selection-01.json",
        "preview_sha256": "a" * 64,
        "preview_count": 300,
        "complete_prediction_count": 1000,
        "partial_metrics": [],
        "unit_metrics": [],
    }
    first = _reduce_live_state(state, completed)
    replayed = _reduce_live_state(first, completed)
    assert "predictions" not in replayed["active_preview"]
    assert replayed["active_preview"]["preview_ref"] == "live/ridge/selection-01.json"
    assert replayed["active_unit_id"] == "selection-01"
    assert replayed["candidates"]["ridge"]["status"] == "running"
    assert replayed["candidates"]["ridge"]["completed_unit_count"] == 1
