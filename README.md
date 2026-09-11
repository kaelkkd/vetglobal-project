# VetGlobal

Small full-stack demonstration of a persisted, asynchronous pet-document summarization workflow. A React client creates a pet and uploads a document; the FastAPI backend stores the document, creates a durable job, accepts a simulated worker result, and exposes the result through document reads and long polling.

The project deliberately uses canned worker results. It demonstrates workflow, concurrency, retry, and failure behavior rather than real clinical summarization.

## Prerequisites

- Python 3.12 (verified with 3.12.5)
- Node.js 22 (verified with 22.20.0 and npm 10.9.3)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (verified with 0.9.26)
- Docker with Compose
- PostgreSQL 17 through Compose (verified with 17.11)

## Configuration

Create the local environment file before starting the API:

```powershell
Copy-Item .env.example .env
```

Replace `INTERNAL_SERVICE_TOKEN` with a random value of at least 16 characters. The browser never receives this token. The other defaults use the Compose PostgreSQL service and allow the frontend at `http://localhost:5173`.

## Run locally

Install the locked backend dependencies, start PostgreSQL, apply the schema, and run FastAPI:

```powershell
uv sync --locked
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn vetglobal.main:app --reload
```

The API is available at `http://localhost:8000`. Temporary interactive Swagger documentation is available at `http://localhost:8000/docs`.

In a second terminal, start the frontend:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The frontend creates the pet and document job, then long-polls until the simulator supplies a success or failure.

### Run the backend with Compose

After creating `.env`, the complete backend stack can be built and started with:

```powershell
docker compose up --build
```

Compose waits for PostgreSQL, runs migrations once, and then starts the API. The frontend remains a separate Vite development process. Stop services without deleting database data with `docker compose down`.

## API workflow

| Method and path | Purpose | Successful response |
| --- | --- | --- |
| `POST /pets` | Create a pet | `201` |
| `POST /pets/{pet_id}/documents` | Validate a TXT/PDF and enqueue its job | `202` |
| `POST /internal/jobs/{job_id}/complete` | Deliver a simulated worker result | `200` |
| `GET /documents/{document_id}` | Read current document/job metadata | `200` |
| `GET /documents/{document_id}/poll?after_job_id=0` | Wait up to 25 seconds for a terminal result | `200` or empty `204` |
| `GET /health/live` | Process liveness | `200` |
| `GET /health/ready` | PostgreSQL readiness | `200` or `503` |

Create a pet:

```powershell
curl.exe -X POST http://localhost:8000/pets `
  -H "Content-Type: application/json" `
  -d '{"name":"Hank","owner_name":"John Bergeson"}'
```

Upload a nonempty UTF-8 TXT or basic-signature-valid PDF of at most 5 MiB:

```powershell
curl.exe -X POST http://localhost:8000/pets/1/documents `
  -H "Idempotency-Key: demo-upload-1" `
  -F "file=@record.txt"
```

The optional idempotency key makes an uncertain upload retry safe. A matching retry returns the original document/job IDs, while reusing the key for different input returns `409`. Requests without a key create a new document and job each time.

Complete the returned job through the simulator, which reads `.env`:

```powershell
uv run python -m vetglobal.worker_simulator 1 --summary "Patient is stable."
# Or deliver a failure:
uv run python -m vetglobal.worker_simulator 1 --error "Could not parse document"
```

An identical callback may be replayed safely and preserves the completion timestamp. A different result for an already completed job returns `409`.

Read or poll the document:

```powershell
curl.exe http://localhost:8000/documents/1
curl.exe -i "http://localhost:8000/documents/1/poll?after_job_id=0"
```

Polling returns the document with `200` for both `DONE` and `FAILED`. It returns an empty `204` if no new terminal result arrives within 25 seconds. `after_job_id` is the last terminal job result consumed; use `0` immediately after upload. Clients must not parse JSON from a `204`.

Predictable validation, authentication, absence, size, and state-conflict failures use deliberate 4xx responses. Error bodies use a stable `code` and safe `message`; Pydantic validation may additionally return field details.

## Tests and quality checks

Tests use PostgreSQL rather than SQLite so transaction, uniqueness, locking, and cross-instance behavior match the application. The fixture refuses to use a database whose name does not contain `test`.

```powershell
docker compose --profile test up -d test-db
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src

Set-Location frontend
npm ci
npm test
npm run build
```

Override `TEST_DATABASE_URL` if port 5433 is unavailable. The test session migrates the test database, isolates test data, and downgrades it after the session. GitHub Actions runs the same backend and frontend gates on every push and pull request.

## Key design decisions

- **Modular monolith:** thin FastAPI routers call focused services backed by Pydantic schemas and SQLAlchemy models. This keeps the small project understandable without speculative repository or dependency-injection layers.
- **PostgreSQL as source of truth:** document bytes and job state are shared across API instances. Document and job creation therefore commit atomically, and no local process memory is authoritative.
- **Persisted queue simulation:** an `ENQUEUED` row represents accepted work. The CLI explicitly delivers success or failure; it is not an automatic queue consumer.
- **Concurrency-safe completion:** a short transaction locks the job row. Identical delivery is idempotent; a contradictory terminal delivery conflicts.
- **Concurrency-safe upload retries:** PostgreSQL uniqueness scopes an idempotency key to a pet. A fingerprint of filename, media type, and content hash rejects conflicting reuse, including concurrent requests.
- **Database-backed long polling:** requests perform fresh reads and release the connection between checks. This remains correct across processes and cancellation without Redis or an in-memory event registry.
- **Environment-backed configuration:** the internal callback token is securely compared and excluded from browser code, public responses, and logs.
- **Reproducible tooling:** uv and npm lock dependencies; Ruff, mypy, pytest, Vitest, and CI enforce the validated baseline.

## Tradeoffs and deliberate omissions

Document bytes are stored in PostgreSQL because the 5 MiB limit keeps the assessment small and permits one atomic document/job transaction. A production design would normally store PDFs and other large objects in bucket storage and retain only metadata, hashes, and object keys in PostgreSQL, with explicit cleanup/reconciliation behavior.

Periodic database polling is simple and reliable at this scale but creates roughly one query per active poller per polling interval. Higher scale could use a queue for work delivery and PostgreSQL `LISTEN/NOTIFY`, Redis, WebSockets, or server-sent events as wake-up hints while preserving a durable database fallback.

Public routes are an unauthenticated, single-tenant demo. `owner_name` is metadata, not authorization. Production tenant isolation would require authenticated tenant identity, tenant-scoped foreign keys and queries, authorization tests, encrypted object storage, retention rules, and audit controls.

Intentionally omitted: real summarization, automatic workers, OCR, malware scanning, full PDF parsing, document download/deletion/listing, worker leases/retries/dead-letter queues, authentication, production object storage, load/soak testing, elaborate monitoring, and deployment.

## Project status

The required API, reliability gate, React demonstration, clean-start verification, automated checks, and browser success/failure smoke flows are complete. Executed evidence is recorded in [`docs/VERIFICATION.md`](docs/VERIFICATION.md).

LLM assistance accelerated scaffolding and review. Generated code was reviewed incrementally, corrected where verification exposed issues, and accepted only after executable checks.
