# VetGlobal development plan

Status: implementation in progress; the September 8–10 deliverables are complete.

Target completion: **Friday, September 11, 2026**, America/Sao_Paulo.

## Reading order

1. [Assessment](PROJECT.md): original requirements; do not rewrite.
2. [Architecture and decisions](docs/ARCHITECTURE.md): scope, persistence, concurrency, and tradeoffs.
3. [API contract](docs/API.md): expected requests, responses, and edge cases.
4. [Implementation checklist](docs/IMPLEMENTATION.md): ordered work and the backend gate.
5. [Verification and delivery](docs/VERIFICATION.md): tests, demo, and submission checks.

These files describe intended behavior, not features that already exist. Update checkboxes only after implementing and verifying the associated behavior. Record deviations and their reasons in the decision log in ARCHITECTURE.md. Keep the API contract synchronized with implementation. Actual commands and validation results belong in the final README and verification evidence.

## Priorities

- Use Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL, Pydantic, and pytest.
- Use uv with pyproject.toml and a committed uv.lock; no pip-based setup instructions.
- Include Docker Compose and Alembic in the backend foundation.
- Finish and verify the backend before beginning React, TypeScript, and Vite.
- Keep the solution small enough to understand and present in a 30-minute discussion.
- Use persisted jobs as the queue simulation. Redis and fake SQS are unnecessary for the agreed initial design.

## Compressed schedule

| Day | Deliverable | Completion condition |
| --- | --- | --- |
| Tuesday, September 8 | Foundation and persistence | uv project, settings, Compose PostgreSQL, initial migration, pet creation, test harness |
| Wednesday, September 9 | Complete backend workflow | Upload, document retrieval, callback, worker simulator, database-backed long polling, core error tests |
| Thursday, September 10, first part | Backend review gate | Idempotency and concurrency tests, quality checks, clean-start verification, backend documentation |
| Thursday, September 10, after gate | Minimal React workflow | Create pet, upload, poll, display success/failure; no frontend work before gate |
| Friday, September 11 | Verification and delivery | Browser smoke checks, complete README, demo rehearsal, final review and submission materials |

This is a deliverable sequence, not a claim that work will run automatically on those days. If implementation begins later, preserve the dependency order and reduce optional scope.

## Scope controls for Friday

Core requirements, tests, documentation, completion idempotency, Compose, Alembic, and the small React screen are the delivery target. Upload idempotency is planned but may be deferred if it threatens the backend gate. LISTEN/NOTIFY is a stretch enhancement, implemented only after the end-to-end delivery target works and time remains for its race-condition tests.

Do not trade away correctness, stateless behavior, or failure handling for bonus features. Defer notifications first, upload idempotency second, and visual polish third. If the backend gate slips, record the remaining frontend scope explicitly; do not silently declare completion.

## Definition of done

- All five required endpoints satisfy the documented contract.
- Success and failure flows work across two API instances sharing PostgreSQL.
- Long polling does not block the event loop or hold database transactions while waiting.
- Automated tests and quality checks pass against the actual implementation.
- A clean checkout can be installed, migrated, run, and tested using the README.
- React demonstrates the verified backend flow.
- Tradeoffs, limitations, and deliberate omissions are documented.
- Submission notes and a 30-minute presentation outline are ready. Publishing or sending messages is separate from this planning work.
