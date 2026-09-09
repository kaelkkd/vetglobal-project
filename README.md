# VetGlobal

Small FastAPI backend for a persisted, asynchronous pet-document summarization workflow. The September 8 foundation currently provides PostgreSQL persistence, migrations, health checks, and pet creation. Document/job endpoints are scheduled next and are not implemented yet.

## Prerequisites

- Python 3.12
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

The API is at `http://localhost:8000`; interactive documentation is at `/docs`.

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

Health checks are available at `GET /health/live` and `GET /health/ready`. Readiness returns 503 when PostgreSQL is unavailable.

## Tests and quality checks

Tests deliberately use PostgreSQL rather than SQLite. The fixture refuses to operate on a database whose name does not contain `test`.

```powershell
docker compose --profile test up -d test-db
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Override `TEST_DATABASE_URL` if port 5433 is unavailable. The test session migrates the test database, isolates test data, and downgrades it when finished.

## Foundation decisions

- Files and durable job state will live in PostgreSQL so multiple API instances share authoritative state.
- The application uses async SQLAlchemy sessions with psycopg 3; migrations run as a separate one-shot service rather than in each API process.
- Configuration is environment-backed. The internal callback token is required even though its endpoint belongs to the next implementation slice.
- Public routes are an unauthenticated, single-tenant demo; `owner_name` is metadata, not authorization.
- uv manages Python versions and dependencies reproducibly, while Ruff provides fast linting and formatting.

The full planned contract, polling design, tradeoffs, and deliberate omissions are in [`docs/`](docs/). Current limitations include all document/job behavior, worker simulation, long polling, idempotency, observability, CI, and the React UI. No real clinical summarization, OCR, or malware scanning is planned for this assessment.

LLM assistance was used to accelerate scaffolding. The implementation is reviewed and validated incrementally; executed evidence is recorded in `docs/VERIFICATION.md` rather than inferred from generated code.
