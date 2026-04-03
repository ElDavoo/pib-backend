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

## Docker

Build the hardened image:

```bash
docker build -t pib-backend:latest .
```

Run the locked-down compose service:

```bash
docker compose up --build
```

The container listens on `127.0.0.1:8080` and stores SQLite data in the named volume defined in `docker-compose.yml`.

GitHub Actions publishes multi-arch images to `ghcr.io/<owner>/<repo>` when you create a `v*` tag or publish a GitHub Release.

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
