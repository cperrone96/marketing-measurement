"""Route publishing a reviewed conversion-model card, never a fitted model object."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas import ConversionModelResponse
from api.services import MarketingMeasurementService

router = APIRouter(prefix="/api/v1", tags=["reviewed models"])
_service = MarketingMeasurementService()


@router.get("/models/conversion", response_model=ConversionModelResponse)
def conversion_model() -> dict[str, object]:
    return {
        **_service.conversion_model(),
        "evidence": _service.public_evidence(
            "identifier-free conversion model session output",
            "cf828e20761a596a0ca1a7f2568dd808792367137ba7bd0a6a3bfc946dfccf9c",
        ),
    }
