# Verification and delivery

Status: September 8–10 implementation checks completed; final browser smoke and delivery review remain for September 11.

## Testing approach

Use pytest integration tests against a real PostgreSQL service; SQLite cannot validate the concurrency and notification behavior we depend on. Use separate sessions/connections for concurrent operations. Prefer explicit synchronization over arbitrary sleeps. Run migrations on an empty test database and isolate data between tests. Never run destructive test cleanup against the development database.

Use short configurable polling intervals/timeouts for most tests and a focused test of the production 25-second configuration/bound. Verify timeout responses and request cancellation without making every test wait 25 seconds. Unit tests are for meaningful pure validation/state logic, not implementation mirrors.

## Acceptance matrix

| Area | Required evidence |
| --- | --- |
| Pets | 201 with persisted ID; whitespace/blank/oversized names rejected |
| Upload | Valid TXT and PDF return 202 with persisted document/job; unsupported, empty, invalid, and oversized input handled |
| Upload limits | Enforce chunked requests without Content-Length and multipart intake limits |
| Atomicity | Failed persistence leaves neither orphan document nor orphan job |
| Reads | Correct metadata for ENQUEUED, DONE, FAILED; no binary payload; unknown ID 404 |
| Callback auth | Missing/invalid token rejected; token never appears in public responses or logs |
| Callback validation | DONE/FAILED payload requirements and contradictory fields checked |
| Callback retries | Identical replay leaves timestamp unchanged; conflict 409; concurrent outcomes deterministic |
| Polling | Already complete, delayed success, failure, timeout, cursor equality, invalid cursor, missing document |
| Polling resources | No connection held while waiting; cancellation releases resources; unrelated requests remain responsive |
| Multiple instances | Poll through API A, complete through API B, observe persisted result |
| Upload idempotency, if included | Same input/key reuses IDs; changed input conflicts; concurrent requests create one pair; no-key duplicates remain distinct |
| Notifications, if included | Registration race, disconnect/reconnect, missed event fallback, cross-process wake-up |
| Tooling | Clean migration, uv locked install, pytest, lint, formatting, and type checks |
| Frontend | Build passes; 204 does not trigger JSON parsing; polling stops on terminal state; obsolete requests cancelled |

Database errors caused by predictable domain conflicts must map to the documented response rather than 500. Unexpected failures should be logged safely and rolled back.

## Planned command inventory

These are intended command shapes, not verified commands. Finalize module paths/options during implementation and publish only working commands in README.

```text
uv sync --locked
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn vetglobal.main:app --reload
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Also document full Compose startup, test database configuration, the worker simulator invocation, frontend install/dev/build commands, and how to stop services without deleting data. Choose one frontend package manager and lockfile. CI must use its reproducible installation command.

## Demo script

1. Start PostgreSQL/API using README instructions and show API docs.
2. Create Hank and upload a small text document.
3. Show the accepted document/job IDs and pending state.
4. Start polling, run the simulator with success, and show the summary.
5. Upload a PDF and simulate failure; show the failure state.
6. Replay the same completion and then a conflicting completion; explain 200 versus 409.
7. Show a missing-resource response and a polling timeout.
8. Demonstrate the same flow in React after the backend gate.
9. Explain that summaries are canned and there is no real clinical processing.

## README acceptance checklist

- [ ] Prerequisites and tested Python/PostgreSQL/Node versions.
- [ ] uv installation reference, locked dependency setup, environment configuration.
- [ ] Local and Docker startup, migration, test, and frontend commands.
- [ ] Example requests for every required endpoint, including failure.
- [ ] Cursor semantics, 204 handling, and worker simulation instructions.
- [ ] Storage, queue simulation, duplicate handling, idempotency, access-control limitations.
- [ ] Stateless scaling and polling tradeoffs.
- [ ] Deliberately omitted and incomplete features accurately listed.
- [ ] LLM assistance and human review described honestly.

## Presentation preparation

Suggested 30-minute allocation: 5 minutes context/demo, 10 minutes architecture and concurrency, 5 minutes tests/error handling, 5 minutes limitations and scaling, 5 minutes questions. Be ready to explain every dependency and major transaction, the difference between callback retries and reprocessing, why owner_name is not authorization, and how a real queue/object store would change the design.

Prepare a submission message containing the repository link, setup/test pointers, known limitations, and a request for a 30-minute meeting. Do not send messages or publish without the user's instruction.

## Evidence log

| Date | Check | Result | Notes |
| --- | --- | --- | --- |
| 2026-09-08 | Planning artifacts created | Planning only | No application code or automated checks exist yet |
| 2026-09-08 | `uv lock` and `uv sync --locked` | Pass | Python 3.12.5; 45 packages resolved and locked |
| 2026-09-08 | Initial migration SQL generation | Pass | Transactional PostgreSQL DDL generated for pets, documents, and jobs |
| 2026-09-08 | PostgreSQL integration suite | Pass | 5 tests passed against PostgreSQL 17; migration upgraded and downgraded cleanly; FastAPI/Starlette emitted 2 upstream TestClient deprecation warnings |
| 2026-09-08 | Ruff lint and format | Pass | `ruff check .` and `ruff format --check .` |
| 2026-09-08 | Mypy | Pass | Strict check passed for all 8 application source files |
| 2026-09-08 | Container build | Pass | Locked production install completed in Python 3.12 image |
| 2026-09-08 | Compose startup and HTTP smoke | Pass | Database became healthy, migration exited successfully, API liveness/readiness and pet creation returned expected responses |
| 2026-09-09 | Async HTTP test client migration | Pass | 5 PostgreSQL integration tests passed with no warnings; deprecated Starlette TestClient compatibility path removed |
| 2026-09-09 | Core backend workflow suite | Pass | 28 tests passed against PostgreSQL 17, covering upload validation and limits, atomicity, reads, callbacks, polling, and the worker simulator |
| 2026-09-09 | Core quality checks | Pass | Ruff lint/format and strict mypy passed for 18 application source files; lockfile is current |
| 2026-09-09 | Container and live workflow | Pass | Images rebuilt, migration and API started without runtime dependency sync, and upload → simulator → GET/poll succeeded |
| 2026-09-09 | Structured logging review | Pass | Request/job IDs, statuses, paths, elapsed times, and enqueue-to-completion duration emitted as JSON without clinical content or secrets |
| 2026-09-10 | Reliability and concurrency suite | Pass | 37 PostgreSQL tests passed, including upload/callback races, cross-instance polling, deadline completion, connection release, cancellation, and idempotent replay |
| 2026-09-10 | Backend quality gate | Pass | Ruff lint/format and strict mypy passed; CI workflow now runs migrations and the same checks with PostgreSQL 17 |
| 2026-09-10 | Compose and simulator smoke | Pass | Images rebuilt, migration completed, API started, and live upload → `.env`-configured simulator → poll returned DONE |
| 2026-09-10 | Frontend tests and production build | Pass | 3 Vitest tests covered empty 204 handling, terminal polling stop, and cancellation; TypeScript and Vite production build completed with Node 22.20.0 |
| 2026-09-10 | Frontend local preview | Pass | Vite served the workflow at `http://127.0.0.1:5173/` and returned HTTP 200; browser workflow smoke remains scheduled for final delivery |

Append actual command outcomes, failures, fixes, and unresolved limitations during implementation. A planned test is not evidence of a passing test.
