# Planned API contract

Status: contract in progress. Pet creation and health routes are implemented; document and job routes remain planned. See [architecture](ARCHITECTURE.md) for storage and concurrency rules.

## Conventions

JSON responses except multipart upload and empty 204 responses. IDs are positive integers; after_job_id is a nonnegative integer, default 0. UTC timestamps use ISO 8601. Reject blank names after trimming; proposed name limits are 120 characters for a pet and 200 for an owner. Set finite limits on filenames, idempotency keys, summaries, and errors in implementation and test them.

Use a consistent documented error envelope with a machine-readable code and safe message; validation responses may include field-level details. Never return 500 for known validation, absence, authentication, or state-conflict errors. Exclude secrets and input file contents from errors.

## POST /pets

Request:

```json
{"name": "Hank", "owner_name": "John Bergeson"}
```

Return 201 with id, name, owner_name, and created_at. Invalid fields return 422.

## POST /pets/{pet_id}/documents

Multipart field: file. Optional header: Idempotency-Key (when the planned enhancement is enabled). Accept a nonempty UTF-8 .txt or basic-signature-valid .pdf, up to 5 MiB. Extension matching is case-insensitive.

Return 202 after commit:

```json
{"document_id": 10, "job_id": 55, "status": "ENQUEUED"}
```

The returned IDs support GET and polling. No worker processing occurs inside this request.

An idempotent replay returns the same original 202 body, even if the job has since finished. This response is an acceptance receipt; GET provides current state. Same key with different input returns 409. Without a key, repeats create distinct documents.

Errors: unknown pet 404; unsupported extension 415; oversized body/file 413; empty or invalid content 422; invalid path/header input 422.

## POST /internal/jobs/{job_id}/complete

Require X-Internal-Token. Missing or invalid token returns 401. Validate authentication before exposing job existence.

Success request:

```json
{"status": "DONE", "summary": "Patient has a history of intermittent vomiting."}
```

Failure request:

```json
{"status": "FAILED", "error": "Could not parse document"}
```

Use discriminated Pydantic schemas: DONE requires a nonempty summary and forbids error; FAILED requires a nonempty error and forbids summary. Reject unsupported status and extra fields. Return 200 with job_id, document_id, status, summary, error, and completed_at. The inapplicable result field is null.

Identical terminal callback: 200 with unchanged result and timestamp. Conflicting terminal callback: 409. Unknown job: 404. Invalid payload: 422.

## GET /documents/{document_id}

Return 200 with current metadata and job result:

```json
{
  "id": 10,
  "pet_id": 1,
  "filename": "hank.txt",
  "media_type": "text/plain",
  "size_bytes": 128,
  "created_at": "2026-09-09T12:00:00Z",
  "job_id": 55,
  "status": "DONE",
  "summary": "Patient has a history of intermittent vomiting.",
  "error": null,
  "completed_at": "2026-09-09T12:00:03Z"
}
```

ENQUEUED has null summary, error, and completed_at. FAILED has a nonempty error, null summary, and a completion timestamp. Never return file bytes or internal credentials. Unknown document returns 404.

## GET /documents/{document_id}/poll?after_job_id=0

The cursor is the last **terminal result consumed**, not the newly accepted job ID.

1. Check existence; return 404 immediately if absent.
2. Return 200 with the same document schema as GET if its job is terminal and job_id > after_job_id.
3. Otherwise, wait and recheck for at most 25 seconds.
4. Return 204 with an empty body when no qualifying terminal result arrives.

FAILED is a successful HTTP read of a failed job, so return 200 with status FAILED and error. Invalid/negative cursors return 422. A cursor equal to or greater than this document's job ID yields no qualifying result and eventually 204; it does not imply a missing document. Set Cache-Control: no-store on document reads and polling.

Client algorithm:

```text
upload -> save document_id and job_id
cursor = 0
poll(document_id, cursor)
  204 -> poll again with unchanged cursor
  200 DONE/FAILED -> consume result, update cursor to job_id, stop
  network error or transient 5xx -> bounded exponential backoff and retry
  permanent 4xx -> show error, stop
```

Use a client timeout longer than 25 seconds and cancel obsolete requests. Do not parse JSON from a 204 response. One active polling request per displayed document is enough. No reprocessing endpoint is planned, so the client stops after its first terminal result.

## Supporting health routes

GET /health/live: process liveness, 200. GET /health/ready: database connectivity, 200 or 503. Return no credentials or detailed database exceptions.
