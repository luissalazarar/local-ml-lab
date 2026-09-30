import multiprocessing
import subprocess
import sys
import time

import psutil

from local_ml_lab.jobs import terminate_process_tree


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
