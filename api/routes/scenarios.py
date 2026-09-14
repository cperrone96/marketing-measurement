"""Route for deterministic, explicitly synthetic budget scenarios."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import (
    BudgetScenarioRequest,
    BudgetScenarioResponse,
    ErrorResponse,
)
from api.services import MarketingMeasurementService

router = APIRouter(prefix="/api/v1", tags=["synthetic scenarios"])
_service = MarketingMeasurementService()


@router.post(
    "/scenarios/budget",
    response_model=BudgetScenarioResponse,
    responses={422: {"model": ErrorResponse}},
)
def budget_scenario(request: BudgetScenarioRequest) -> dict[str, object]:
    return {
        **_service.budget_scenario(
            request.total_budget,
            request.minimums,
            request.capacities,
            request.expected_incremental_value,
        ),
        "evidence": _service.synthetic_evidence("synthetic budget allocation scenario v1"),
    }
