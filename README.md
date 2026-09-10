# VetGlobal

Small FastAPI backend for a persisted, asynchronous pet-document summarization workflow. The backend now supports pet creation, validated document upload, durable jobs, worker completion callbacks, document reads, and database-backed long polling.

## Prerequisites

- Python 3.12
- Node.js 22
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker with Compose (for PostgreSQL)

## Local setup

```powershell
Copy-Item .env.example .env
# Replace INTERNAL_SERVICE_TOKEN in .env with a random value of at least 16 characters.
uv sync --locked
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn vetglobal.main:app --reload
```

The API is at `http://localhost:8000`; temporary interactive documentation is at `/docs`.

In a second terminal, start the React client:

```powershell
Set-Location frontend
npm ci
npm run dev
```

The frontend is at `http://localhost:5173`. It creates the pet and document job, then long-polls until the manual simulator supplies a result.

## Compose setup

After creating `.env` as above:

```powershell
docker compose up --build
```

Compose waits for PostgreSQL, runs migrations once, and then starts the API. Stop services without deleting database data with `docker compose down`.

## Current API

Create a pet:

```powershell
curl.exe -X POST http://localhost:8000/pets `
  -H "Content-Type: application/json" `
  -d '{"name":"Hank","owner_name":"John Bergeson"}'
```

Upload a text or PDF document (maximum 5 MiB):

```powershell
curl.exe -X POST http://localhost:8000/pets/1/documents `
  -H "Idempotency-Key: demo-upload-1" `
  -F "file=@record.txt"
```

The optional key makes retrying the same upload safe. A matching retry returns the original IDs, while reusing the key for different input returns `409`; requests without a key always create a new document and job.

The `202` response contains `document_id` and `job_id`. Complete that job with the manual simulator, which reads the same `INTERNAL_SERVICE_TOKEN` and `.env` configuration as the API:

```powershell
uv run python -m vetglobal.worker_simulator 1 --summary "Patient is stable."
# Or simulate failure:
uv run python -m vetglobal.worker_simulator 1 --error "Could not parse document"
```

Read or poll the document:

```powershell
curl.exe http://localhost:8000/documents/1
curl.exe -i "http://localhost:8000/documents/1/poll?after_job_id=0"
```

Polling waits up to 25 seconds. It returns the document with `200` when the job is `DONE` or `FAILED`, and an empty `204` on timeout. `after_job_id` is the last terminal result the client consumed; a newly accepted job should initially be polled with cursor `0`.

Health checks are available at `GET /health/live` and `GET /health/ready`. Readiness returns 503 when PostgreSQL is unavailable.

## Tests and quality checks

Tests deliberately use PostgreSQL rather than SQLite. The fixture refuses to operate on a database whose name does not contain `test`.

```powershell
docker compose --profile test up -d test-db
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
Set-Location frontend
npm ci
npm test
npm run build
```

Override `TEST_DATABASE_URL` if port 5433 is unavailable. The test session migrates the test database, isolates test data, and downgrades it when finished.

## Foundation decisions

- Files and durable job state will live in PostgreSQL so multiple API instances share authoritative state.
- An `ENQUEUED` database row is the durable queue simulation. The worker simulator explicitly delivers a success or failure callback; there is no automatic consumer.
- The application uses async SQLAlchemy sessions with psycopg 3; migrations run as a separate one-shot service rather than in each API process.
- Completion locks the job row. An identical callback is safe to replay, while a different terminal result returns `409`.
- Upload idempotency is enforced by PostgreSQL uniqueness scoped to a pet. A fingerprint of the normalized filename, media type, and content hash rejects conflicting key reuse, including races across API instances.
- Long polling performs short, fresh database reads and releases the connection between checks. PostgreSQL remains authoritative across API instances.
- Configuration is environment-backed. The internal completion endpoint requires a securely compared service token that is never exposed to the browser.
- Public routes are an unauthenticated, single-tenant demo; `owner_name` is metadata, not authorization.
- uv manages Python versions and dependencies reproducibly, while Ruff provides fast linting and formatting.

The full contract, polling design, tradeoffs, and deliberate omissions are in [`docs/`](docs/). The included concurrency tests target important races but are not load or soak tests. No real clinical summarization, automatic queue consumer, OCR, malware scanning, authentication, object storage, or production deployment is planned for this assessment.

LLM assistance was used to accelerate scaffolding. The implementation is reviewed and validated incrementally; executed evidence is recorded in `docs/VERIFICATION.md` rather than inferred from generated code.
