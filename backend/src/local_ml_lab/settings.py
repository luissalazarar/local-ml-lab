from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    app_display_name: str = "Laboratorio ML"
    app_env: str = "production"
    app_default_locale: str = "es-PE"
    data_root: Path = Path("/data")
    database_url: str = "sqlite:////data/db/app.sqlite3"
    queue_url: str = "redis://queue:6379/0"
    ml_threads: int = Field(default=2, ge=1, le=8)
    worker_concurrency: int = 1
    max_upload_mib: int = Field(default=100, ge=1)
    max_rows: int = 200_000
    max_columns: int = 300
    max_cells: int = 2_000_000
    max_profile_sample_rows: int = 10_000
    max_class_labels: int = 50
    shap_enabled: bool = False
    openai_default_model: str = "gpt-4.1-mini-2025-04-14"
    openai_timeout_seconds: int = 45
    openai_max_output_tokens: int = 2000
    openai_max_payload_kib: int = 48

    @model_validator(mode="after")
    def validate_v1(self):
        if self.worker_concurrency != 1:
            raise ValueError("WORKER_CONCURRENCY debe ser 1 en V1")
        return self

    def prepare(self) -> None:
        for name in ("db", "uploads", "datasets", "preflights", "runs", "logs", "tmp"):
            (self.data_root / name).mkdir(parents=True, exist_ok=True)


settings = Settings()
