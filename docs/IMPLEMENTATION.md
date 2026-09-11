# Ordered implementation checklist

Status: September 8–11 delivery work complete. Follow [PLAN.md](../PLAN.md), [architecture](ARCHITECTURE.md), and [API contract](API.md). Publishing and submission remain separate user-controlled actions.

## 1. Foundation — Tuesday

- [x] Initialize uv project with Python 3.12 and src layout.
- [x] Add FastAPI, SQLAlchemy, psycopg, Pydantic settings, multipart support, Alembic, and server dependencies.
- [x] Add pytest/async support, HTTP test client, Ruff, and type checker as development dependencies.
- [x] Add lockfile, Python version, ignore rules, and safe example environment. Commit intentionally deferred per user instruction.
- [x] Create application factory/lifespan, validated settings, session dependency, liveness/readiness.
- [x] Add Dockerfile and Compose PostgreSQL/API/migration workflow with readiness handling.
- [x] Create models, constraints, and initial Alembic migration.
- [x] Create PostgreSQL test fixtures with isolated test data and migration setup.
- [x] Implement POST /pets and its validation tests.
- [x] Start README with actual verified setup commands.

## 2. Core workflow — Wednesday

- [x] Implement bounded multipart intake and content validation.
- [x] Atomically create document and ENQUEUED job; test rollback.
- [x] Implement GET document without fetching binary contents unnecessarily.
- [x] Add protected callback endpoint and terminal payload validation.
- [x] Add row-lock-based completion idempotency and conflict handling.
- [x] Add manual worker simulator for explicit success/failure through HTTP.
- [x] Implement database-backed long polling with monotonic deadline and cancellation cleanup.
- [x] Add missing-resource, validation, failure, immediate-result, and timeout tests.
- [x] Add structured request/job logs with safe metadata and duration.

## 3. Reliability and backend gate — Thursday first

- [x] Test callback races and repeated delivery.
- [x] Test cross-instance upload/completion/polling against shared PostgreSQL.
- [x] Test polling completion near the deadline and session release between checks.
- [x] Add upload Idempotency-Key fingerprint and database uniqueness, if schedule permits.
- [x] Test identical, conflicting, and concurrent upload replays if included.
- [x] Add CI running migrations, tests, lint/format checks, and type checks.
- [x] Verify clean-start API instructions and worker simulator examples.
- [x] Review transaction boundaries, exception handling, resource cleanup, and generated code.
- [x] Record actual checks/results in VERIFICATION.md and current behavior in README.

### Mandatory backend gate before frontend

- [x] All five required routes pass contract tests, including failed jobs.
- [x] Multi-instance behavior works without authoritative in-memory state.
- [x] Completion idempotency is concurrency-safe.
- [x] Polling returns 204 by its configured deadline and cleans up on cancellation.
- [x] Clean database migrations and documented local startup work.
- [x] pytest, Ruff checks, and configured type checks pass.
- [x] No known core correctness defect remains; any deferred bonus is documented.

Do not create the React app before every gate item passes.

## 4. Minimal frontend — Thursday after gate

- [x] Scaffold React + TypeScript + Vite with a package lockfile.
- [x] Implement pet creation, current pet display, and file upload.
- [x] Display pending state immediately after acceptance.
- [x] Implement cursor=0 polling, empty-204 handling, cancellation, and transient-error backoff.
- [x] Display summary and processing failure clearly; distinguish connection failures.
- [x] Keep the internal token and worker callback controls out of the browser.
- [x] Add simple accessible labels, disabled submitting states, and readable layout.
- [x] Verify a production frontend build and key polling behavior tests.

## 5. Final delivery — Friday

- [x] Run the verification matrix and browser smoke flow.
- [x] Finish README setup, API examples, test commands, tradeoffs, and omissions.
- [x] Verify clean checkout instructions using only documented prerequisites.
- [x] Prepare demonstration and discussion outline.
- [x] Review repository for secrets, generated clutter, and misleading claims.
- [x] Prepare repository link and meeting-request text; do not send automatically.

## Deliberately deferred stretch: notifications

Start only after the delivery target works, including React and documentation, with time remaining for verification.

- [ ] Add dedicated per-process LISTEN connection and transactional NOTIFY.
- [ ] Preserve periodic database fallback and cancellation cleanup.
- [ ] Test registration race, missed notifications, listener reconnect, and cross-instance delivery.
- [ ] Compare complexity/query cost in the design notes; omit if incomplete.
