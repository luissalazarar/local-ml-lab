import sys

from redis import Redis
from rq import Worker

from local_ml_lab.settings import settings

try:
    workers = Worker.all(connection=Redis.from_url(settings.queue_url))
    sys.exit(0 if any(w.name == "local-ml-worker" for w in workers) else 1)
except Exception:
    sys.exit(1)
