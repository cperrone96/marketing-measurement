"""Routes that publish reviewed public-observed aggregate findings."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from api.schemas import (
    AttributionResponse,
    CohortsResponse,
    ErrorResponse,
    FunnelResponse,
    KpisResponse,
    SourcesResponse,
)
from api.services import MarketingMeasurementService, paginate

router = APIRouter(prefix="/api/v1", tags=["observed analytics"])
_service = MarketingMeasurementService()
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {422: {"model": ErrorResponse}}
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/sources", response_model=SourcesResponse, responses=_ERROR_RESPONSES)
def sources(page: Page = 1, page_size: PageSize = 100) -> dict[str, object]:
    boundary, items = _service.sources()
    page_items, total = paginate(items, page, page_size)
    return {
        "boundary": boundary,
        "items": page_items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/kpis", response_model=KpisResponse, responses=_ERROR_RESPONSES)
def kpis(page: Page = 1, page_size: PageSize = 100) -> dict[str, object]:
    items, total = paginate(_service.kpis(), page, page_size)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed findings summary",
            "447c329ffca58e2c83972e7eebc1d7aa98ed8a2a744a2c3587de63c7bdeb55c1",
        ),
    }


@router.get("/funnel", response_model=FunnelResponse, responses=_ERROR_RESPONSES)
def funnel(
    start_date: date | None = None,
    end_date: date | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, object]:
    items, total = paginate(_service.funnel(start_date, end_date), page, page_size)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed daily funnel aggregate",
            "447c329ffca58e2c83972e7eebc1d7aa98ed8a2a744a2c3587de63c7bdeb55c1",
        ),
    }


@router.get("/cohorts", response_model=CohortsResponse, responses=_ERROR_RESPONSES)
def cohorts(
    start_date: date | None = None,
    end_date: date | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, object]:
    items, total = paginate(_service.cohorts(start_date, end_date), page, page_size)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed cohort retention aggregate",
            "42cbe7d216b59b899901ff3017493715338910706edd048a50bfd6c0f355e2b7",
        ),
    }


@router.get(
    "/attribution", response_model=AttributionResponse, responses=_ERROR_RESPONSES
)
def attribution(page: Page = 1, page_size: PageSize = 100) -> dict[str, object]:
    items, total = paginate(_service.attribution(), page, page_size)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed conversion-path aggregate",
            "f3fc57a1ba15181f0a116ef1e549ec97d9c778985a970ad0aabfe85628b69d8f",
        ),
    }
