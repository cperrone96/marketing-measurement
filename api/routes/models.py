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
            "reviewed conversion model evaluation",
            _service.artifact_sha256(
                "data/derived/ga4_public_sample/conversion_model_evaluation.json"
            ),
        ),
    }
