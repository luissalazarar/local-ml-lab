import threading
import time
from uuid import uuid4

from redis import Redis
from rq import Queue, SimpleWorker
from rq.serializers import JSONSerializer

from local_ml_lab.db.migrate import migrate
from local_ml_lab.jobs import reconcile_queued_jobs, recover_pending_jobs
from local_ml_lab.settings import settings


def outbox_loop():
    while True:
        try:
            reconcile_queued_jobs()
        except Exception:
            pass
        time.sleep(2)


def main():
    migrate()
    connection = Redis.from_url(settings.queue_url)
    for attempt in range(30):
        try:
            connection.ping()
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
    recover_pending_jobs()
    threading.Thread(target=outbox_loop, name="sqlite-outbox", daemon=True).start()
    worker = SimpleWorker(
        [Queue("analysis", connection=connection, serializer=JSONSerializer)],
        connection=connection,
        name=f"local-ml-worker-{uuid4().hex[:8]}",
        serializer=JSONSerializer,
    )
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
