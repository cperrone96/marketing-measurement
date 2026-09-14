"""Public, unauthenticated FastAPI application for educational analytics contracts."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routes import integrations, kpis, models, scenarios
from api.schemas import ErrorResponse, HealthResponse
from api.services import APIValidationError

app = FastAPI(
    title="Marketing Measurement API",
    version="v1",
    description="Public educational API backed by reviewed observed and synthetic artifacts.",
)
app.include_router(kpis.router)
app.include_router(integrations.router)
app.include_router(models.router)
app.include_router(scenarios.router)


def _validation_details(error: RequestValidationError) -> list[dict[str, object]]:
    """Expose fields and safe messages, never raw submitted values or tracebacks."""
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    body = ErrorResponse(
        code="validation_error",
        message="Request validation failed",
        details=_validation_details(error),
    )
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(APIValidationError)
async def api_validation_error(
    _request: Request, error: APIValidationError
) -> JSONResponse:
    body = ErrorResponse(code=error.code, message=error.message, details=error.details)
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(StarletteHTTPException)
async def http_error(
    _request: Request, error: StarletteHTTPException
) -> JSONResponse:
    """Return a safe stable shape for routing failures without echoing internals."""
    code, message = {
        404: ("not_found", "Requested resource was not found"),
        405: ("method_not_allowed", "Requested method is not allowed"),
    }.get(error.status_code, ("http_error", "HTTP request failed"))
    body = ErrorResponse(code=code, message=message, details={"status": error.status_code})
    return JSONResponse(status_code=error.status_code, content=body.model_dump())


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "v1", "database": "committed-artifact-repository"}
