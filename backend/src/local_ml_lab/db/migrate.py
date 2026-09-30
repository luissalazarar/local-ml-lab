from filelock import FileLock

from local_ml_lab.settings import settings

from .base import Base
from .session import engine


def migrate() -> None:
    settings.prepare()
    with FileLock(str(settings.data_root / "db" / ".migrate.lock"), timeout=30):
        from . import models  # noqa: F401

        Base.metadata.create_all(engine)
