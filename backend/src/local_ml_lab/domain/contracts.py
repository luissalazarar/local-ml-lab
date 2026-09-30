from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisConfig(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_version_id: str
    goal: Literal["estimate_value", "classify", "forecast", "drivers", "explore"]
    problem_type: Literal["regression", "classification", "forecasting", "exploration"]
    target_column_id: str | None = None
    date_column_id: str | None = None
    included_column_ids: list[str] = Field(default_factory=list)
    excluded_column_ids: list[str] = Field(default_factory=list)
    depth: Literal["quick", "recommended", "exhaustive"] = "quick"
    primary_metric: str | None = None
    seed: int = 42
    forecast_options: dict | None = None


class PreflightRequest(StrictModel):
    config: AnalysisConfig


class RunRequest(StrictModel):
    preflight_id: str
    config_sha256: str


class ExportRequest(StrictModel):
    formats: list[Literal["xlsx", "pdf"]]


class ContextRequest(StrictModel):
    privacy_level: Literal[1, 2, 3] = 1
    detail: Literal["summary", "complete"] = "summary"
    format: Literal["txt", "md", "json"] = "md"
