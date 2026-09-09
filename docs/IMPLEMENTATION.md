# Ordered implementation checklist

Status: in progress; the September 8 foundation is complete. Follow [PLAN.md](../PLAN.md), [architecture](ARCHITECTURE.md), and [API contract](API.md). Work in small reviewable changes and verify each behavior before marking it complete.

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

- [ ] Implement bounded multipart intake and content validation.
- [ ] Atomically create document and ENQUEUED job; test rollback.
- [ ] Implement GET document without fetching binary contents unnecessarily.
- [ ] Add protected callback endpoint and terminal payload validation.
- [ ] Add row-lock-based completion idempotency and conflict handling.
- [ ] Add manual worker simulator for explicit success/failure through HTTP.
- [ ] Implement database-backed long polling with monotonic deadline and cancellation cleanup.
- [ ] Add missing-resource, validation, failure, immediate-result, and timeout tests.
- [ ] Add structured request/job logs with safe metadata and duration.

## 3. Reliability and backend gate — Thursday first

- [ ] Test callback races and repeated delivery.
- [ ] Test cross-instance upload/completion/polling against shared PostgreSQL.
- [ ] Test polling completion near the deadline and session release between checks.
- [ ] Add upload Idempotency-Key fingerprint and database uniqueness, if schedule permits.
- [ ] Test identical, conflicting, and concurrent upload replays if included.
- [ ] Add CI running migrations, tests, lint/format checks, and type checks.
- [ ] Verify clean-start API instructions and worker simulator examples.
- [ ] Review transaction boundaries, exception handling, resource cleanup, and generated code.
- [ ] Record actual checks/results in VERIFICATION.md and current behavior in README.

### Mandatory backend gate before frontend

- [ ] All five required routes pass contract tests, including failed jobs.
- [ ] Multi-instance behavior works without authoritative in-memory state.
- [ ] Completion idempotency is concurrency-safe.
- [ ] Polling returns 204 by its configured deadline and cleans up on cancellation.
- [ ] Clean database migrations and documented local startup work.
- [ ] pytest, Ruff checks, and configured type checks pass.
- [ ] No known core correctness defect remains; any deferred bonus is documented.

Do not create the React app before every gate item passes.

## 4. Minimal frontend — Thursday after gate

- [ ] Scaffold React + TypeScript + Vite with a committed package lockfile.
- [ ] Implement pet creation, current pet display, and file upload.
- [ ] Display pending state immediately after acceptance.
- [ ] Implement cursor=0 polling, empty-204 handling, cancellation, and transient-error backoff.
- [ ] Display summary and processing failure clearly; distinguish connection failures.
- [ ] Keep the internal token and worker callback controls out of the browser.
- [ ] Add simple accessible labels, disabled submitting states, and readable layout.
- [ ] Verify a production frontend build and key polling behavior tests.

## 5. Final delivery — Friday

- [ ] Run the verification matrix and browser smoke flow.
- [ ] Finish README setup, API examples, test commands, tradeoffs, and omissions.
- [ ] Verify clean checkout instructions using only documented prerequisites.
- [ ] Prepare demonstration and discussion outline.
- [ ] Review repository for secrets, generated clutter, and misleading claims.
- [ ] Prepare repository link and meeting-request text; do not send automatically.

## Stretch: notifications

Start only after the delivery target works, including React and documentation, with time remaining for verification.

- [ ] Add dedicated per-process LISTEN connection and transactional NOTIFY.
- [ ] Preserve periodic database fallback and cancellation cleanup.
- [ ] Test registration race, missed notifications, listener reconnect, and cross-instance delivery.
- [ ] Compare complexity/query cost in the design notes; omit if incomplete.
