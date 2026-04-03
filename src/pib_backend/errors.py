from __future__ import annotations


class TelemetryError(Exception):
    pass


class PermanentTelemetryError(TelemetryError):
    pass


class TransientTelemetryError(TelemetryError):
    def __init__(self, message: str, retry_after_ms: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_ms = retry_after_ms
