## Plan: Python Telemetry Ingestion Backend

Build a FastAPI + SQLite ingestion service that matches the Android telemetry contract exactly (POST /telemetry, schemaVersion=1, optional Retry-After behavior), so the existing app can upload batches without client-side changes. Start with ingestion-only scope, but design storage and service boundaries so query APIs can be added later without refactoring core write-paths.

**Steps**
1. Phase 1 - Contract Lock and Backend Skeleton
2. Confirm the exact request/response contract from existing client code and freeze it as backend-facing API rules: accepted request fields, nullable fields, schemaVersion handling, and default success response behavior.
3. Create backend project skeleton with FastAPI app factory, routing module for /telemetry, pydantic request/response models, config module, structured logging, and health endpoint. This phase is independent and can be started immediately.
4. Phase 2 - Validation and Ingestion Pipeline
5. Implement strict request validation: schemaVersion required and must be 1, non-empty batchId, sentAtMs as epoch-ms, events array size guard (align with configured max expected from client), and eventType whitelist (request/response).
6. Implement ingestion write-path to SQLite with two logical tables: raw batch envelope table and flattened event table; wrap writes in one transaction per batch to preserve atomicity. Depends on step 3.
7. Implement idempotency guard for duplicate batchId handling (recommended: unique index on batchId, treat duplicate as accepted with stable ack semantics to prevent duplicate event inflation). Depends on step 6.
8. Phase 3 - Response Semantics and Operational Safety
9. Implement response behavior compatible with TelemetryApiClient expectations: on successful ingest return accepted=true with ackId; on transient failures return retryable=true and optional retryAfterMs; on permanent validation failures return retryable=false with error message. Depends on steps 5-7.
10. Map HTTP status strategy to client retry behavior: 2xx for accepted/handled requests; 429 or 5xx for overload/transient server failures (with optional Retry-After header); 4xx for permanent client errors. Depends on step 9.
11. Add request correlation and batch-level structured logs (batchId, event count, ingest latency, status) to support troubleshooting and later analytics. Parallel with step 9.
12. Phase 4 - Runtime, Tooling, and Local Integration
13. Add environment-driven config (host, port, sqlite path, max payload size, log level) and startup checks (DB migrations/bootstrap). Depends on steps 6-10.
14. Add container/dev runner support and reproducible launch commands so Android app can target localhost collector quickly. Parallel with step 13.
15. Add minimal contract tests and one end-to-end integration test that posts a representative payload and validates DB persistence and response fields. Depends on steps 6-10.
16. Run manual integration against the Android app with telemetry enabled; verify batches move from in_flight to acked in app-side store and retries occur only on intended status codes. Depends on steps 9-15.

**Relevant files**
- /home/dave/git/PlayIntegrityBreak/app/src/main/java/icu/nullptr/playintegritybreak/telemetry/TelemetryApiClient.kt - Source of exact wire contract, status handling, retryable semantics, and endpoint path.
- /home/dave/git/PlayIntegrityBreak/app/src/main/java/icu/nullptr/playintegritybreak/telemetry/TelemetryUploadWorker.kt - Defines retry decision logic and how accepted/retryable/retryAfterMs influence queue transitions.
- /home/dave/git/PlayIntegrityBreak/common/src/main/java/icu/nullptr/playintegritybreak/common/TelemetryModels.kt - Canonical telemetry event/batch/stats model shapes and nullable fields.
- /home/dave/git/PlayIntegrityBreak/common/src/main/java/icu/nullptr/playintegritybreak/common/JsonConfig.kt - Config ranges and defaults (batch size, retry attempts, interval) that constrain expected backend load patterns.
- /home/dave/git/PlayIntegrityBreak/app/src/main/java/icu/nullptr/playintegritybreak/telemetry/AppIntegrityEventStore.kt - Batch leasing and ack/nack transitions to validate end-to-end behavior during manual tests.
- New backend package under repository root (to be created) - FastAPI app, models, storage, and test suite for ingestion service.

**Verification**
1. Contract tests: validate accepted payload, malformed schemaVersion, invalid eventType, empty events, duplicate batchId, and oversized payload cases.
2. Retry behavior tests: simulate transient server failures and confirm responses/statuses are aligned with Android client retriable rules.
3. DB integrity checks: verify one transaction per batch, no partial writes, and unique batchId behavior.
4. Manual app integration: run backend on localhost:8080, enable telemetry in app config, trigger integrity traffic, confirm backend receives POST /telemetry and stores events.
5. Queue-state validation in app: confirm successful uploads become acked and transient failures schedule retry with delay.

**Decisions**
- Included scope: ingestion-only backend in Python with FastAPI + SQLite.
- Excluded scope: query APIs/stats endpoints, auth, dashboard, long-term production hardening.
- Compatibility target: no Android client changes required for first iteration.
- Recommended idempotency behavior: duplicate batchId should be safely accepted to avoid double counting under client retries.

**Further Considerations**
1. Deployment topology recommendation: keep localhost-first for parity with current client, then optionally add configurable endpoint in Android app for remote staging.
2. Data retention recommendation: add a simple time-based cleanup job early (for example, keep 7-30 days) to prevent unbounded SQLite growth.
3. Privacy recommendation: avoid storing unnecessary device metadata beyond what the client already sends; document retention and purpose in backend README.
