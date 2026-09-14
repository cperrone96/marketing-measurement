"""Typed HTTP client for the dashboard's published API boundary."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import TypeVar

import httpx
from pydantic import BaseModel

from api.schemas import (
    AttributionResponse,
    AudienceQualityResponse,
    BudgetScenarioRequest,
    BudgetScenarioResponse,
    CohortsResponse,
    FunnelResponse,
    IntegrationHealthResponse,
    KpisResponse,
    SourcesResponse,
)

ResponseT = TypeVar("ResponseT", bound=BaseModel)


class DashboardAPIError(RuntimeError):
    """A safe, user-presentable dashboard API failure."""


class DashboardAPIClient:
    """Fetch and validate only public API response contracts."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved_base_url = (
            base_url
            if base_url is not None
            else os.getenv("MARKETING_API_URL", "http://127.0.0.1:8000")
        )
        self.base_url = resolved_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._transport = transport

    def _get(self, path: str, model: type[ResponseT]) -> ResponseT:
        return self._request("GET", path, model)

    def _request(
        self,
        method: str,
        path: str,
        model: type[ResponseT],
        *,
        payload: dict[str, object] | None = None,
    ) -> ResponseT:
        try:
            with httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.request(method, path, json=payload)
            response.raise_for_status()
            return model.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as error:
            raise DashboardAPIError(
                "The analytics API could not be reached or returned an invalid contract."
            ) from error

    def sources(self) -> SourcesResponse:
        return self._get("/api/v1/sources", SourcesResponse)

    def kpis(self) -> KpisResponse:
        return self._get("/api/v1/kpis", KpisResponse)

    def funnel(self) -> FunnelResponse:
        return self._get("/api/v1/funnel?page_size=1", FunnelResponse)

    def cohorts(self) -> CohortsResponse:
        return self._get("/api/v1/cohorts?page_size=1", CohortsResponse)

    def attribution(self) -> AttributionResponse:
        return self._get("/api/v1/attribution", AttributionResponse)

    def audience_quality(self) -> AudienceQualityResponse:
        return self._get("/api/v1/audiences/quality", AudienceQualityResponse)

    def integration_health(self) -> IntegrationHealthResponse:
        return self._get("/api/v1/integrations/health", IntegrationHealthResponse)

    def budget_scenario(self, total_budget: Decimal) -> BudgetScenarioResponse:
        request = BudgetScenarioRequest(
            total_budget=total_budget,
            minimums={
                "channel_aurora": Decimal("0.00"),
                "channel_birch": Decimal("0.00"),
            },
            capacities={"channel_aurora": total_budget, "channel_birch": total_budget},
            expected_incremental_value={
                "channel_aurora": Decimal("1.20"),
                "channel_birch": Decimal("1.00"),
            },
        )
        payload = request.model_dump(mode="json")
        return self._request(
            "POST", "/api/v1/scenarios/budget", BudgetScenarioResponse, payload=payload
        )
