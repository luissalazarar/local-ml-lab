from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisConfig(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_version_id: str
    goal: Literal["estimate_value", "classify", "forecast", "drivers", "explore"]
    problem_type: Literal["regression", "classification", "forecasting", "exploration"]
    target_column_id: str | None = None
    date_column_id: str | None = None
    # None means "use the eligible defaults"; [] is an explicit featureless selection.
    included_column_ids: list[str] | None = None
    excluded_column_ids: list[str] = Field(default_factory=list)
    depth: Literal["quick", "recommended"] = "quick"
    primary_metric: str | None = None
    validation_context: Literal["independent_records"] = "independent_records"
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


ColumnId = Annotated[str, StringConstraints(pattern=r"^c\d{4}$")]


class ColumnPreparation(StrictModel):
    type: Literal["auto", "numeric", "date", "categorical", "text"] = "auto"
    role: Literal["variable", "identifier", "ignore"] = "variable"
    trim: bool = False
    empty_to_missing: bool = False
    date_format: Literal["DMY", "MDY", "YMD", "UNAMBIGUOUS"] | None = None
    excel_date_serials: bool = False
    decimal_separator: Literal[".", ","] | None = None
    thousands_separator: Literal[".", ",", " "] | None = None
    percent: bool = False
    currency: Literal["PEN", "USD", "EUR"] | None = None
    invalid: Literal["block", "segregate"] = "block"
    category_merges: dict[str, str] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def coherent_options(self):
        if self.type != "date" and (self.date_format or self.excel_date_serials):
            raise ValueError("Las opciones de fecha requieren type=date")
        if self.type != "numeric" and (
            self.decimal_separator or self.thousands_separator or self.percent or self.currency
        ):
            raise ValueError("Las opciones numéricas requieren type=numeric")
        if (
            self.decimal_separator
            and self.thousands_separator
            and self.decimal_separator == self.thousands_separator
        ):
            raise ValueError("Los separadores decimal y de miles deben ser distintos")
        if self.type not in {"categorical", "text", "auto"} and self.category_merges:
            raise ValueError("La unificación explícita solo aplica a texto o categorías")
        return self


class DateRangeFilter(StrictModel):
    kind: Literal["date_range"]
    column_id: ColumnId
    start: str | None = None
    end: str | None = None

    @model_validator(mode="after")
    def has_bound(self):
        if not self.start and not self.end:
            raise ValueError("El filtro de periodo necesita al menos un límite")
        return self


class CategoryFilter(StrictModel):
    kind: Literal["category"]
    column_id: ColumnId
    mode: Literal["include", "exclude"]
    values: list[str] = Field(min_length=1, max_length=100)


class NumericNotNullFilter(StrictModel):
    kind: Literal["numeric_not_null"]
    column_id: ColumnId


RowFilter = Annotated[
    DateRangeFilter | CategoryFilter | NumericNotNullFilter, Field(discriminator="kind")
]


class MonthlyAggregation(StrictModel):
    date_column_id: ColumnId
    value_column_id: ColumnId
    operation: Literal["sum", "mean"]


class PreparationRecipe(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    columns: dict[ColumnId, ColumnPreparation] = Field(default_factory=dict, max_length=500)
    expected_columns: dict[ColumnId, str] = Field(default_factory=dict, max_length=500)
    exact_duplicates: Literal["keep", "exclude"] = "keep"
    filters: list[RowFilter] = Field(default_factory=list, max_length=20)
    monthly_aggregation: MonthlyAggregation | None = None

    @field_validator("columns")
    @classmethod
    def reject_dangerous_column_payloads(cls, value):
        forbidden = {"path", "command", "sql", "python", "callable", "formula"}
        for config in value.values():
            keys = {key.lower() for key in config.category_merges}
            if keys & forbidden:
                raise ValueError("La receta contiene contenido no permitido")
        return value


class PreparationRequest(StrictModel):
    recipe: PreparationRecipe
