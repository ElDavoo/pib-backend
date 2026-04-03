from __future__ import annotations

from fastapi.testclient import TestClient

from pib_backend.api import create_app
from pib_backend.config import Settings
from pib_backend.storage import TelemetryRepository


def build_payload(batch_id: str = "batch-123") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "batchId": batch_id,
        "sentAtMs": 1710000000000,
        "client": {
            "appVersionName": "1.0.0",
            "appVersionCode": 7,
            "sdkInt": 34,
            "device": "pixel",
            "model": "pixel 8",
        },
        "events": [
            {
                "id": 1,
                "timestampMs": 1710000000100,
                "packageName": "icu.nullptr.playintegritybreak",
                "eventType": "request",
                "source": "client",
                "attemptCount": 0,
            },
            {
                "id": 2,
                "timestampMs": 1710000000200,
                "packageName": "icu.nullptr.playintegritybreak",
                "eventType": "response",
                "success": True,
                "source": "client",
                "attemptCount": 0,
            },
        ],
    }


def test_post_telemetry_persists_batch_and_returns_ack(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.post("/telemetry", json=build_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert body["retryable"] is False
    assert body["ackId"]
    assert body["error"] is None

    repository = TelemetryRepository(settings)
    assert repository.count_batches() == 1
    assert repository.count_events() == 2

    stored = repository.fetch_batch("batch-123")
    assert stored is not None
    assert stored["ack_id"] == body["ackId"]
    assert stored["event_count"] == 2
    assert stored["raw_request"]["batchId"] == "batch-123"
    assert stored["events"][0]["event_type"] == "request"


def test_schema_version_must_be_one(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    app = create_app(settings)

    payload = build_payload()
    payload["schemaVersion"] = 2

    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)

    assert response.status_code == 400
    assert response.json()["retryable"] is False
    assert "schemaVersion" in response.json()["error"]


def test_invalid_event_type_is_rejected(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    app = create_app(settings)

    payload = build_payload()
    payload["events"][0]["eventType"] = "other"

    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)

    assert response.status_code == 400
    assert response.json()["retryable"] is False


def test_empty_events_are_rejected(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    app = create_app(settings)

    payload = build_payload()
    payload["events"] = []

    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)

    assert response.status_code == 400
    assert response.json()["retryable"] is False


def test_duplicate_batch_id_returns_stable_ack_and_no_duplicate_rows(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    app = create_app(settings)
    payload = build_payload()

    with TestClient(app) as client:
        first = client.post("/telemetry", json=payload)
        second = client.post("/telemetry", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["ackId"] == second.json()["ackId"]

    repository = TelemetryRepository(settings)
    assert repository.count_batches() == 1
    assert repository.count_events() == 2


def test_oversized_payload_returns_413(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3", max_request_bytes=128)
    app = create_app(settings)
    payload = build_payload()
    payload["events"].append(
        {
            "id": 3,
            "timestampMs": 1710000000300,
            "packageName": "icu.nullptr.playintegritybreak",
            "eventType": "request",
            "source": "client",
        }
    )

    with TestClient(app) as client:
        response = client.post("/telemetry", json=payload)

    assert response.status_code == 413


def test_transient_storage_error_maps_to_retryable_response(tmp_path, monkeypatch) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    app = create_app(settings)

    def raise_transient(*args, **kwargs):
        from pib_backend.errors import TransientTelemetryError

        raise TransientTelemetryError("database busy", retry_after_ms=7000)

    monkeypatch.setattr(app.state.services.repository, "ingest_batch", raise_transient)

    with TestClient(app) as client:
        response = client.post("/telemetry", json=build_payload("batch-transient"))

    assert response.status_code == 503
    assert response.headers["retry-after"] == "7"
    body = response.json()
    assert body["accepted"] is False
    assert body["retryable"] is True
    assert body["retryAfterMs"] == 7000
