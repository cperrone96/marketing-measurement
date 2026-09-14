"""Routes for intentionally synthetic integration demonstrations."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from api.schemas import (
    AudienceQualityResponse,
    ErrorResponse,
    IntegrationHealthResponse,
)
from api.services import MarketingMeasurementService, paginate

router = APIRouter(prefix="/api/v1", tags=["synthetic integrations"])
_service = MarketingMeasurementService()
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {422: {"model": ErrorResponse}}
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get(
    "/audiences/quality",
    response_model=AudienceQualityResponse,
    responses=_ERROR_RESPONSES,
)
def audience_quality(page: Page = 1, page_size: PageSize = 100) -> dict[str, object]:
    items, total = paginate(_service.audience_quality(), page, page_size)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.synthetic_evidence("integration"),
    }


@router.get(
    "/integrations/health",
    response_model=IntegrationHealthResponse,
    responses=_ERROR_RESPONSES,
)
def health(page: Page = 1, page_size: PageSize = 100) -> dict[str, object]:
    items, total = paginate(_service.integration_health(), page, page_size)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.synthetic_evidence("integration"),
    }
