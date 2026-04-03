from __future__ import annotations

from time import perf_counter, time_ns
import logging

from pib_backend.config import Settings
from pib_backend.errors import PermanentTelemetryError
from pib_backend.models import TelemetryUploadRequest, TelemetryUploadResponse
from pib_backend.storage import TelemetryRepository


class TelemetryIngestionService:
    def __init__(self, repository: TelemetryRepository, settings: Settings, logger: logging.Logger | None = None) -> None:
        self._repository = repository
        self._settings = settings
        self._logger = logger or logging.getLogger("pib_backend.telemetry")

    def ingest(self, payload: TelemetryUploadRequest, raw_request_json: str) -> TelemetryUploadResponse:
        started = perf_counter()
        received_at_ms = time_ns() // 1_000_000

        self._validate(payload)

        result = self._repository.ingest_batch(payload, raw_request_json, received_at_ms)
        ingest_latency_ms = int((perf_counter() - started) * 1000)
        status = "accepted" if result.inserted else "duplicate"

        self._logger.info(
            "telemetry_ingest",
            extra={
                "batch_id": result.batch_id,
                "event_count": result.event_count,
                "ack_id": result.ack_id,
                "status": status,
                "ingest_latency_ms": ingest_latency_ms,
            },
        )

        return TelemetryUploadResponse(
            accepted=True,
            ackId=result.ack_id,
            retryable=False,
            error=None,
        )

    def _validate(self, payload: TelemetryUploadRequest) -> None:
        if payload.schemaVersion != 1:
            raise PermanentTelemetryError("schemaVersion must be 1")

        if payload.batchId.strip() == "":
            raise PermanentTelemetryError("batchId must be non-empty")

        if not payload.events:
            raise PermanentTelemetryError("events must not be empty")

        if len(payload.events) > self._settings.max_events_per_batch:
            raise PermanentTelemetryError(
                f"events must not exceed {self._settings.max_events_per_batch} items"
            )
