# Architecture and decisions

Status: active implementation baseline. See [PLAN.md](../PLAN.md) for priorities and deadline.

## Structure

Use a modular monolith: thin FastAPI routers, Pydantic request/response schemas, SQLAlchemy models, and small services for transactions and state changes. Use asynchronous SQLAlchemy sessions with psycopg 3. Keep dependencies explicit. Avoid generic repositories, dependency-injection frameworks, microservices, and speculative abstractions.

Proposed layout:

```text
src/vetglobal/
  main.py
  config.py
  db.py
  models.py
  schemas.py
  api/
    pets.py
    documents.py
    jobs.py
  services/
    documents.py
    jobs.py
    polling.py
  worker_simulator.py
migrations/
tests/
  conftest.py
  unit/
  integration/
frontend/                 # created only after backend gate
docs/
pyproject.toml
uv.lock
compose.yaml
Dockerfile
.env.example
README.md
```

Split modules further only when real complexity warrants it.

## Persistence

| Entity | Fields and constraints |
| --- | --- |
| Pet | Generated positive integer ID, nonempty name and owner_name, UTC created_at |
| Document | Generated ID, pet foreign key, original filename, normalized media type, byte size, SHA-256, content bytes, UTC created_at |
| Job | Generated ID, unique document foreign key, ENQUEUED/DONE/FAILED status, nullable summary/error, UTC created_at and completed_at |
| Upload idempotency | Nullable key and request fingerprint on Document; unique (pet_id, idempotency_key) for supplied keys |

One document has one job in this version. Index foreign keys used by lookups. Enforce valid status/result combinations with database checks as well as Pydantic validation. ENQUEUED has no terminal timestamp or result; DONE has summary only; FAILED has error only. Use timezone-aware timestamps. Do not return binary content in metadata queries.

Store files in PostgreSQL with a 5 MiB per-file limit. This makes document and job persistence a single transaction and works across API instances without a shared local directory. Cost: database size, backup volume, and bandwidth. Production evolution: object storage with lifecycle management and a strategy for reconciling storage/database failures.

## Upload transaction and validation

1. Validate the pet, multipart file, supported extension, nonempty contents, and size.
2. Read in bounded chunks; stop as soon as the limit is exceeded. Do not trust Content-Length. Bound multipart/request intake as well so oversized bodies do not consume unlimited temporary storage before handler validation; allow modest multipart overhead beyond the file limit.
3. Require valid UTF-8 for text and a basic PDF signature for PDF. Treat MIME type as advisory because clients vary; never rely on filename or MIME alone. Full PDF parsing is outside this simulation.
4. Normalize stored filename to a basename used only as metadata, compute hash, and atomically insert Document and Job.
5. Return 202 only after commit. Roll back both records on failure.

Without an idempotency key, duplicate content creates another document. With a key, use a fingerprint of normalized filename, media type, and content hash. Enforce uniqueness in PostgreSQL, handle a concurrent insert conflict by rolling back and loading the winner, then compare fingerprints. Same fingerprint replays the original acceptance response; different fingerprint returns 409. Keys are scoped to a pet and retained for the lifetime of the document in this demo. Do not cache idempotency in memory.

## Jobs and worker simulation

```text
ENQUEUED --> DONE
ENQUEUED --> FAILED
```

The persisted ENQUEUED record is the durable representation of pending work. A CLI simulator takes a job ID and calls the internal completion endpoint with an explicit canned success or failure. It is manual dispatch, not an automatic queue consumer; explain this limitation in the README. There is no real LLM call, extraction, OCR, or job execution guarantee.

Use a row lock in a short callback transaction. First completion stores the result and completion timestamp. An identical callback succeeds without changing state or timestamps. A conflicting callback returns 409. Normalize payloads before comparison. Terminal states are immutable. Concurrent success/failure callbacks must yield one winner and one conflict.

Retrying delivery of the same callback is supported. Reprocessing a failed document requires a new upload; no retry endpoint or automatic processing retries in this version.

## Stateless long polling

PostgreSQL is the source of truth. Each polling request checks for a qualifying terminal result, releases its database session, then awaits a short interval (initially 500 ms). Repeat until the monotonic 25-second deadline, rechecking state before timeout. Bound individual database waits by the remaining request budget. Detect cancellation/disconnection and clean up promptly. No transaction or database connection remains checked out during sleep.

Use fresh reads under READ COMMITTED so completion in another transaction becomes visible. A local timer is acceptable; authoritative state and correctness must not depend on a local event registry. Approximate query load is active pollers divided by the interval in seconds. This simple design is appropriate for a small assessment, with explicit scale limits.

### Optional LISTEN/NOTIFY enhancement

Only after the delivery target is complete:

- Use one dedicated listening connection per API process, outside the request pool.
- Commit LISTEN registration before reading current state, then wait and re-query.
- Issue NOTIFY in the completion transaction; publish IDs only, no clinical content.
- Treat notifications as hints, and keep periodic database checks as fallback.
- Handle listener reconnects, lost notifications, event cleanup, and completion racing with registration.
- Local wake-up bookkeeping may optimize latency but must never be required for correctness.

Reference: [PostgreSQL LISTEN ordering and race conditions](https://www.postgresql.org/docs/17/sql-listen.html).

## Configuration and access

Use environment-backed settings for database URL, internal service token, allowed frontend origins, and logging. Keep test overrides for polling timing and file limits. Do not commit secrets. Require a configured internal token at startup; compare the X-Internal-Token header securely. Never expose this token to React. The simulator reads it from its environment.

Public routes are an explicitly unauthenticated, single-tenant demo. owner_name does not establish ownership or authorization. Production tenant isolation would require authenticated tenant identity, tenant foreign keys, scoped queries/uniqueness, and cross-tenant authorization tests. Do not claim production security.

Configure explicit development CORS origins. Add liveness and database readiness endpoints. Emit structured logs with request/document/job IDs and elapsed times; avoid file contents, summaries, owner names, and secrets. Measure enqueue-to-completion duration, not invented worker CPU time. Map foreseeable input/domain errors deliberately; log unexpected server errors without exposing internals.

## Tooling

Use uv for initialization, dependency additions, locking, execution, and CI installation. Commit pyproject.toml, uv.lock, and .python-version. Use uv sync --locked in CI, Ruff for lint/format, and a modest type-checking configuration for application code. Pin dependencies through the lockfile and choose supported releases at implementation time.

Compose should support PostgreSQL plus the API and a one-shot migration step; also document running the API locally with uv against containerized PostgreSQL. Do not run migrations independently in every API instance. CI uses PostgreSQL rather than SQLite.

References: [uv project sync](https://docs.astral.sh/uv/concepts/projects/sync/), [FastAPI upload handling](https://fastapi.tiangolo.com/tutorial/request-files/).

## Deliberately omitted

Real summarization, full PDF validation, malware scanning, OCR, Redis/SQS, background consumers, leases/retries/dead-letter queues, multi-tenant authentication, production deployment, object storage, document deletion/download, document listing/pagination, and elaborate monitoring infrastructure.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-08 | Finish September 11; React after backend gate | User's updated schedule and sequencing |
| 2026-09-08 | PostgreSQL jobs and file bytes | Small, transactional, stateless across instances |
| 2026-09-08 | Database-checking long polling first; notifications stretch | Protect correctness and Friday deadline |
| 2026-09-08 | Manual callback simulator | Matches the assessment without building a queue platform |
| 2026-09-10 | Upload idempotency stored with the document | Database uniqueness resolves races across instances; a request fingerprint detects conflicting reuse |
| 2026-09-10 | Minimal single-screen React workflow | Keeps the bonus UI focused on the API contract and makes pending, terminal, and connection states explicit |
