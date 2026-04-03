from __future__ import annotations

from pib_backend.config import Settings
from pib_backend.storage import TelemetryRepository


def test_repository_initialization_creates_tables(tmp_path) -> None:
    settings = Settings(sqlite_path=tmp_path / "telemetry.sqlite3")
    repository = TelemetryRepository(settings)

    repository.initialize()

    assert repository.database_path.exists()
