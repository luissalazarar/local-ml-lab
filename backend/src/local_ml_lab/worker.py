from redis import Redis
from rq import Queue, SimpleWorker
from rq.serializers import JSONSerializer

from local_ml_lab.db.migrate import migrate
from local_ml_lab.settings import settings


def main():
    migrate()
    connection = Redis.from_url(settings.queue_url)
    worker = SimpleWorker(
        [Queue("analysis", connection=connection, serializer=JSONSerializer)],
        connection=connection,
        name="local-ml-worker",
        serializer=JSONSerializer,
    )
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
