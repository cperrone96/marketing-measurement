"""Typed request and response contracts for the public educational API."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Forbid undeclared fields so published contracts stay intentional."""

    model_config = ConfigDict(extra="forbid")


class Provenance(APIModel):
    artifact: str
    sha256: str


class Evidence(APIModel):
    evidence_type: Literal["public_observed", "synthetic"]
    source_date_or_window: str
    provenance: Provenance
    limitations: list[str] = Field(min_length=1)


class ErrorResponse(APIModel):
    code: str
    message: str
    details: object


class HealthResponse(APIModel):
    status: Literal["ok"]
    version: Literal["v1"]
    database: str


class Pagination(APIModel):
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class SourceItem(APIModel):
    name: str
    description: str
    evidence: Evidence


class SourcesResponse(Pagination):
    boundary: str
    items: list[SourceItem]


class KpiItem(APIModel):
    name: str
    values: dict[str, int | float | str]


class KpisResponse(Pagination):
    items: list[KpiItem]
    evidence: Evidence


class FunnelItem(APIModel):
    date: str
    channel_source: str
    channel_medium: str
    measured_sessions: int = Field(ge=0)
    views: int = Field(ge=0)
    engaged_sessions: int = Field(ge=0)
    add_to_carts: int = Field(ge=0)
    checkouts: int = Field(ge=0)
    purchases: int = Field(ge=0)


class FunnelResponse(Pagination):
    items: list[FunnelItem]
    evidence: Evidence


class CohortItem(APIModel):
    cohort_date: str
    activity_date: str
    days_since_acquisition: int = Field(ge=0)
    cohort_users: int = Field(ge=0)
    retained_users: int = Field(ge=0)
    measured_sessions: int = Field(ge=0)
    cohort_definition: str


class CohortsResponse(Pagination):
    items: list[CohortItem]
    evidence: Evidence


class AttributionItem(APIModel):
    model: Literal["first_touch", "last_touch", "linear", "time_decay"]
    conversion_credit_total: float
    top_channel_credits: dict[str, float]
    interpretation: str


class AttributionResponse(Pagination):
    items: list[AttributionItem]
    evidence: Evidence


class AudienceQualityItem(APIModel):
    metric: str
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)


class AudienceQualityResponse(Pagination):
    items: list[AudienceQualityItem]
    evidence: Evidence


class IntegrationHealthItem(APIModel):
    metric: str
    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)


class IntegrationHealthResponse(Pagination):
    items: list[IntegrationHealthItem]
    evidence: Evidence


class ConversionModelResponse(APIModel):
    selected_model: Literal["logistic_regression"]
    evaluation_population: str
    metrics: dict[str, dict[str, float]]
    selected_threshold: float = Field(ge=0, le=1)
    threshold_label: str
    evidence: Evidence


class BudgetScenarioRequest(APIModel):
    total_budget: Decimal
    minimums: dict[str, Decimal] = Field(min_length=1)
    capacities: dict[str, Decimal] = Field(min_length=1)
    expected_incremental_value: dict[str, Decimal] = Field(min_length=1)


class BudgetScenarioResponse(APIModel):
    allocations: dict[str, float]
    total_budget: float
    estimated_incremental_value: float
    assumptions: list[str]
    sensitivity: list[dict[str, bool | float | str]]
    robustness_summary: str
    evidence: Evidence
