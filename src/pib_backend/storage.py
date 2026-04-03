from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import sqlite3
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from pib_backend.config import Settings
from pib_backend.errors import PermanentTelemetryError, TransientTelemetryError
from pib_backend.models import TelemetryUploadRequest


@dataclass(frozen=True, slots=True)
class IngestResult:
    ack_id: str
    batch_id: str
    inserted: bool
    event_count: int
    received_at_ms: int


class TelemetryRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def database_path(self) -> Path:
        return self._settings.sqlite_path

    def initialize(self) -> None:
        self._settings.ensure_storage_ready()
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS telemetry_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL UNIQUE,
                    ack_id TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    sent_at_ms INTEGER NOT NULL,
                    received_at_ms INTEGER NOT NULL,
                    client_json TEXT NOT NULL,
                    raw_request_json TEXT NOT NULL,
                    event_count INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS telemetry_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id TEXT NOT NULL,
                    event_index INTEGER NOT NULL,
                    event_id INTEGER NOT NULL,
                    timestamp_ms INTEGER NOT NULL,
                    package_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    success INTEGER,
                    error_code INTEGER,
                    retriable INTEGER,
                    source TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL,
                    raw_event_json TEXT NOT NULL,
                    FOREIGN KEY(batch_id) REFERENCES telemetry_batches(batch_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_telemetry_events_batch_id ON telemetry_events(batch_id);
                CREATE INDEX IF NOT EXISTS idx_telemetry_events_timestamp_ms ON telemetry_events(timestamp_ms);
                CREATE INDEX IF NOT EXISTS idx_telemetry_batches_sent_at_ms ON telemetry_batches(sent_at_ms);
                """
            )

    def ingest_batch(
        self,
        payload: TelemetryUploadRequest,
        raw_request_json: str,
        received_at_ms: int,
    ) -> IngestResult:
        ack_id = f"ack-{uuid4().hex}"
        client_json = payload.client.model_dump_json()
        event_count = len(payload.events)

        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO telemetry_batches (
                        batch_id,
                        ack_id,
                        schema_version,
                        sent_at_ms,
                        received_at_ms,
                        client_json,
                        raw_request_json,
                        event_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.batchId,
                        ack_id,
                        payload.schemaVersion,
                        payload.sentAtMs,
                        received_at_ms,
                        client_json,
                        raw_request_json,
                        event_count,
                    ),
                )

                for event_index, event in enumerate(payload.events):
                    connection.execute(
                        """
                        INSERT INTO telemetry_events (
                            batch_id,
                            event_index,
                            event_id,
                            timestamp_ms,
                            package_name,
                            event_type,
                            success,
                            error_code,
                            retriable,
                            source,
                            attempt_count,
                            raw_event_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload.batchId,
                            event_index,
                            event.id,
                            event.timestampMs,
                            event.packageName,
                            event.eventType,
                            _bool_to_int(event.success),
                            event.errorCode,
                            _bool_to_int(event.retriable),
                            event.source,
                            event.attemptCount,
                            event.model_dump_json(),
                        ),
                    )

                connection.commit()
                return IngestResult(
                    ack_id=ack_id,
                    batch_id=payload.batchId,
                    inserted=True,
                    event_count=event_count,
                    received_at_ms=received_at_ms,
                )
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                existing = connection.execute(
                    "SELECT ack_id, event_count, received_at_ms FROM telemetry_batches WHERE batch_id = ?",
                    (payload.batchId,),
                ).fetchone()
                if existing is not None:
                    return IngestResult(
                        ack_id=str(existing["ack_id"]),
                        batch_id=payload.batchId,
                        inserted=False,
                        event_count=int(existing["event_count"]),
                        received_at_ms=int(existing["received_at_ms"]),
                    )
                raise PermanentTelemetryError("telemetry batch violates a storage constraint") from exc
            except sqlite3.OperationalError as exc:
                connection.rollback()
                message = str(exc).lower()
                if "locked" in message or "busy" in message:
                    raise TransientTelemetryError("telemetry database is busy", retry_after_ms=1000) from exc
                raise TransientTelemetryError("telemetry database is unavailable", retry_after_ms=1000) from exc

    def count_batches(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM telemetry_batches").fetchone()
            return int(row["total"] if row is not None else 0)

    def count_events(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM telemetry_events").fetchone()
            return int(row["total"] if row is not None else 0)

    def fetch_batch(self, batch_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT batch_id, ack_id, schema_version, sent_at_ms, received_at_ms, client_json, raw_request_json, event_count
                FROM telemetry_batches
                WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchone()
            if row is None:
                return None

            events = connection.execute(
                """
                SELECT event_index, event_id, timestamp_ms, package_name, event_type, success, error_code, retriable, source, attempt_count, raw_event_json
                FROM telemetry_events
                WHERE batch_id = ?
                ORDER BY event_index ASC
                """,
                (batch_id,),
            ).fetchall()

            return {
                "batch_id": row["batch_id"],
                "ack_id": row["ack_id"],
                "schema_version": row["schema_version"],
                "sent_at_ms": row["sent_at_ms"],
                "received_at_ms": row["received_at_ms"],
                "client": json.loads(row["client_json"]),
                "raw_request": json.loads(row["raw_request_json"]),
                "event_count": row["event_count"],
                "events": [dict(event) for event in events],
            }

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._settings.ensure_storage_ready()
        connection = sqlite3.connect(
            self._settings.sqlite_path,
            timeout=5,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0
