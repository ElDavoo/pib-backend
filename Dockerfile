FROM python:3.14-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip wheel --wheel-dir /wheelhouse .


FROM python:3.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIB_HOST=0.0.0.0 \
    PIB_PORT=8080 \
    PIB_SQLITE_PATH=/data/pib-telemetry.sqlite3 \
    PIB_MAX_REQUEST_BYTES=1000000 \
    PIB_MAX_EVENTS_PER_BATCH=100 \
    PIB_LOG_LEVEL=INFO \
    PIB_DEFAULT_RETRY_AFTER_SECONDS=5

WORKDIR /app

RUN useradd --system --uid 10001 --create-home --home-dir /home/pib --shell /usr/sbin/nologin pib \
    && mkdir -p /data /app \
    && chown -R pib:pib /data /app /home/pib

COPY --from=builder /wheelhouse /wheelhouse

RUN python -m pip install --no-cache-dir /wheelhouse/*.whl \
    && rm -rf /wheelhouse

COPY --chown=pib:pib src /app/src

USER 10001:10001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).read()"

CMD ["python", "-m", "pib_backend.main"]
