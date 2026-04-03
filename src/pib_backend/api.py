from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pib_backend.config import Settings
from pib_backend.errors import PermanentTelemetryError, TransientTelemetryError
from pib_backend.logging_config import setup_logging
from pib_backend.models import ErrorResponse, HealthResponse, TelemetryUploadRequest, TelemetryUploadResponse
from pib_backend.service import TelemetryIngestionService
from pib_backend.storage import TelemetryRepository


@dataclass(frozen=True, slots=True)
class AppServices:
    settings: Settings
    repository: TelemetryRepository
    ingestion_service: TelemetryIngestionService


class MaxRequestSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, max_bytes: int) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        body = await request.body()
        if len(body) > self._max_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content=ErrorResponse(error="request body exceeds configured size limit").model_dump(),
            )
        return await call_next(request)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    setup_logging(settings.log_level)

    repository = TelemetryRepository(settings)
    repository.initialize()
    services = AppServices(
        settings=settings,
        repository=repository,
        ingestion_service=TelemetryIngestionService(repository, settings),
    )

    app = FastAPI(title="PIB Telemetry Backend", version="0.1.0")
    app.state.services = services
    app.add_middleware(MaxRequestSizeMiddleware, max_bytes=settings.max_request_bytes)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = exc.errors()[0]["msg"] if exc.errors() else "invalid request payload"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(error=detail).model_dump(),
        )

    @app.exception_handler(PermanentTelemetryError)
    async def handle_permanent_error(_: Request, exc: PermanentTelemetryError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(error=str(exc)).model_dump(),
        )

    @app.exception_handler(TransientTelemetryError)
    async def handle_transient_error(_: Request, exc: TransientTelemetryError) -> JSONResponse:
        retry_after_ms = exc.retry_after_ms if exc.retry_after_ms and exc.retry_after_ms > 0 else settings.default_retry_after_seconds * 1000
        headers = {"Retry-After": str(max(1, retry_after_ms // 1000))}
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers=headers,
            content=TelemetryUploadResponse(
                accepted=False,
                retryable=True,
                retryAfterMs=retry_after_ms,
                error=str(exc),
            ).model_dump(),
        )

    router = APIRouter()

    @router.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            databaseReady=True,
            databasePath=str(repository.database_path),
        )

    @router.post("/telemetry", response_model=TelemetryUploadResponse)
    async def ingest_telemetry(payload: TelemetryUploadRequest, request: Request) -> TelemetryUploadResponse:
        raw_body = (await request.body()).decode("utf-8", errors="replace")
        return services.ingestion_service.ingest(payload, raw_body)

    app.include_router(router)
    return app


app = create_app()
