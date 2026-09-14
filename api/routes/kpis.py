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
        "analyses": _service.portfolio_analyses(),
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed findings summary",
            _service.artifact_sha256(
                "data/derived/ga4_public_sample/findings_summary.json"
            ),
        ),
    }


@router.get("/funnel", response_model=FunnelResponse, responses=_ERROR_RESPONSES)
def funnel(
    start_date: date | None = None,
    end_date: date | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, object]:
    full_window_items = _service.funnel(start_date, end_date)
    items, total = paginate(full_window_items, page, page_size)
    return {
        "items": items,
        "decision_summary": _service.funnel_decision_summary(full_window_items),
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed daily funnel aggregate",
            _service.artifact_sha256(
                "data/observed/ga4_public_sample/funnel_daily_by_channel.json"
            ),
        ),
    }


@router.get("/cohorts", response_model=CohortsResponse, responses=_ERROR_RESPONSES)
def cohorts(
    start_date: date | None = None,
    end_date: date | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, object]:
    full_window_items = _service.cohorts(start_date, end_date)
    items, total = paginate(full_window_items, page, page_size)
    return {
        "items": items,
        "decision_summary": _service.cohort_decision_summary(full_window_items),
        "page": page,
        "page_size": page_size,
        "total": total,
        "evidence": _service.public_evidence(
            "reviewed cohort retention aggregate",
            _service.artifact_sha256(
                "data/observed/ga4_public_sample/cohort_retention.json"
            ),
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
            _service.artifact_sha256(
                "data/observed/ga4_public_sample/conversion_channel_paths.json"
            ),
        ),
    }
