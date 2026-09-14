"""Typed request and response contracts for the public educational API."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[
    Decimal,
    Field(
        ge=0,
        le=Decimal("99999999999999.99"),
        max_digits=16,
        decimal_places=2,
    ),
]
Multiplier = Annotated[
    Decimal, Field(ge=0, le=10, max_digits=8, decimal_places=6)
]


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


class AnalysisSection(APIModel):
    analysis: Literal[
        "landing_page", "device", "product_revenue", "high_value_journey"
    ]
    decision: str
    rows: list[dict[str, str | int | float | None]]
    evidence: Evidence


class KpisResponse(Pagination):
    items: list[KpiItem]
    analyses: list[AnalysisSection] = Field(default_factory=list)
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


class FunnelStageSummary(APIModel):
    views: int = Field(ge=0)
    engaged_sessions: int = Field(ge=0)
    add_to_carts: int = Field(ge=0)
    checkouts: int = Field(ge=0)
    purchases: int = Field(ge=0)


class ChannelQualitySummary(APIModel):
    channel: str
    views: int = Field(ge=0)
    engaged_sessions: int = Field(ge=0)
    purchases: int = Field(ge=0)


class FunnelDecisionSummary(APIModel):
    coverage: Literal["full_filtered_window"]
    stages: FunnelStageSummary
    channels: list[ChannelQualitySummary]


class FunnelResponse(Pagination):
    items: list[FunnelItem]
    decision_summary: FunnelDecisionSummary
    evidence: Evidence


class CohortItem(APIModel):
    cohort_date: str
    activity_date: str
    days_since_acquisition: int = Field(ge=0)
    cohort_users: int = Field(ge=0)
    retained_users: int = Field(ge=0)
    measured_sessions: int = Field(ge=0)
    cohort_definition: str


class CohortRetentionSummaryItem(APIModel):
    cohort_date: str
    days_since_acquisition: Literal[7]
    cohort_users: int = Field(ge=0)
    retained_users: int = Field(ge=0)
    retention_rate: float | None = Field(default=None, ge=0, le=1)


class CohortDecisionSummary(APIModel):
    coverage: Literal["complete_day_7_cohorts"]
    items: list[CohortRetentionSummaryItem]


class CohortsResponse(Pagination):
    items: list[CohortItem]
    decision_summary: CohortDecisionSummary
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
    """Bounded exact-decimal scenario inputs.

    Money supports at most fourteen integer digits and exactly whole-cent precision.
    Expected-value multipliers are finite, non-negative, and capped at 10.
    """

    total_budget: Money
    minimums: dict[str, Money] = Field(min_length=1)
    capacities: dict[str, Money] = Field(min_length=1)
    expected_incremental_value: dict[str, Multiplier] = Field(min_length=1)


class BudgetSensitivityItem(APIModel):
    scenario: str
    varied_channel: str
    value_multiplier: float
    estimated_incremental_value: str
    ranking_changed_from_baseline: bool
    allocation_changed_from_baseline: bool
    decision_summary: str


class ExperimentScenario(APIModel):
    evidence_type: Literal["synthetic"]
    analysis_population: str
    baseline_rate: float = Field(ge=0, le=1)
    minimum_detectable_effect: float = Field(gt=0, lt=1)
    planned_sample_per_arm: int = Field(gt=0)
    observed_sample_per_arm: int = Field(ge=0)
    itt_effect: float
    confidence_interval: tuple[float, float]
    confidence_level: float = Field(gt=0, lt=1)
    conclusion: str


class BudgetScenarioResponse(APIModel):
    """Money is always a two-decimal string; never an ambiguous JSON float."""

    allocations: dict[str, str]
    total_budget: str
    estimated_incremental_value: str
    assumptions: list[str]
    sensitivity: list[BudgetSensitivityItem]
    robustness_summary: str
    experiment: ExperimentScenario
    evidence: Evidence
