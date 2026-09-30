from filelock import FileLock
from sqlalchemy import inspect, text

from local_ml_lab.settings import settings

from .base import Base
from .session import engine


def migrate() -> None:
    settings.prepare()
    with FileLock(str(settings.data_root / "db" / ".migrate.lock"), timeout=30):
        from . import models  # noqa: F401

        Base.metadata.create_all(engine)
        _add_dataset_version_columns()


def _add_dataset_version_columns() -> None:
    """Forward-only compatibility for SQLite databases created before v0.4."""
    existing = {column["name"] for column in inspect(engine).get_columns("dataset_versions")}
    additions = {
        "version_kind": "VARCHAR NOT NULL DEFAULT 'original'",
        "parent_version_id": "VARCHAR",
        "recipe_json": "JSON NOT NULL DEFAULT '{}'",
        "recipe_ref": "VARCHAR",
        "quarantine_ref": "VARCHAR",
        "quality_ref": "VARCHAR",
        "prepared_excel_ref": "VARCHAR",
        "input_sha256": "VARCHAR",
        "recipe_sha256": "VARCHAR",
        "output_sha256": "VARCHAR",
        "input_row_count": "INTEGER NOT NULL DEFAULT 0",
        "quarantined_row_count": "INTEGER NOT NULL DEFAULT 0",
        "transformation_count": "INTEGER NOT NULL DEFAULT 0",
        "preparation_summary": "JSON NOT NULL DEFAULT '{}'",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in existing:
                connection.execute(
                    text(f"ALTER TABLE dataset_versions ADD COLUMN {name} {definition}")
                )
