# PIB Telemetry Backend

FastAPI + SQLite ingestion service for the Play Integrity Break telemetry client.

## Quick Start

On NixOS, the recommended path is:

```bash
nix develop
uvicorn pib_backend.main:app --host 127.0.0.1 --port 8080
```

The backend also supports direct execution through the module entrypoint:

```bash
python -m pib_backend.main
```

## Environment

The service reads these environment variables:

- `PIB_HOST`
- `PIB_PORT`
- `PIB_SQLITE_PATH`
- `PIB_MAX_REQUEST_BYTES`
- `PIB_MAX_EVENTS_PER_BATCH`
- `PIB_LOG_LEVEL`
- `PIB_DEFAULT_RETRY_AFTER_SECONDS`

## Endpoints

- `GET /health`
- `POST /telemetry`

## Testing

```bash
pytest
```
