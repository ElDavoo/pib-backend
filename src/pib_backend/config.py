from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
DEFAULT_SQLITE_PATH = Path("data/pib-telemetry.sqlite3")
DEFAULT_MAX_REQUEST_BYTES = 1_000_000
DEFAULT_MAX_EVENTS_PER_BATCH = 100
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_RETRY_AFTER_SECONDS = 5


def _env_int(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default

    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    sqlite_path: Path = DEFAULT_SQLITE_PATH
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES
    max_events_per_batch: int = DEFAULT_MAX_EVENTS_PER_BATCH
    log_level: str = DEFAULT_LOG_LEVEL
    default_retry_after_seconds: int = DEFAULT_RETRY_AFTER_SECONDS

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("PIB_HOST", DEFAULT_HOST),
            port=_env_int("PIB_PORT", DEFAULT_PORT, minimum=1, maximum=65535),
            sqlite_path=Path(os.getenv("PIB_SQLITE_PATH", str(DEFAULT_SQLITE_PATH))),
            max_request_bytes=_env_int("PIB_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES, minimum=1),
            max_events_per_batch=_env_int("PIB_MAX_EVENTS_PER_BATCH", DEFAULT_MAX_EVENTS_PER_BATCH, minimum=1),
            log_level=os.getenv("PIB_LOG_LEVEL", DEFAULT_LOG_LEVEL).upper(),
            default_retry_after_seconds=_env_int(
                "PIB_DEFAULT_RETRY_AFTER_SECONDS",
                DEFAULT_RETRY_AFTER_SECONDS,
                minimum=1,
            ),
        )

    def ensure_storage_ready(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
