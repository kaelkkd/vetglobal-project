import asyncio

from httpx import AsyncClient

INTERNAL_HEADERS = {"X-Internal-Token": "test-internal-token-value"}


async def enqueue_job(client: AsyncClient) -> tuple[int, int]:
    pet = await client.post("/pets", json={"name": "Hank", "owner_name": "John"})
    upload = await client.post(
        f"/pets/{pet.json()['id']}/documents",
        files={"file": ("record.txt", b"clinical content", "text/plain")},
    )
    assert upload.status_code == 202
    return int(upload.json()["document_id"]), int(upload.json()["job_id"])


async def test_completion_requires_auth_before_job_lookup(client: AsyncClient) -> None:
    missing = await client.post(
        "/internal/jobs/999/complete",
        json={"status": "DONE", "summary": "Summary"},
    )
    invalid = await client.post(
        "/internal/jobs/999/complete",
        headers={"X-Internal-Token": "wrong-token-value"},
        json={"status": "DONE", "summary": "Summary"},
    )
    invalid_payload = await client.post(
        "/internal/jobs/999/complete",
        json={"status": "DONE", "error": "Contradictory"},
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert invalid_payload.status_code == 401
    assert missing.json()["code"] == "invalid_internal_token"


async def test_complete_success_and_identical_replay(client: AsyncClient) -> None:
    document_id, job_id = await enqueue_job(client)
    payload = {"status": "DONE", "summary": "  Patient is stable.  "}

    first = await client.post(
        f"/internal/jobs/{job_id}/complete", headers=INTERNAL_HEADERS, json=payload
    )
    replay = await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "DONE", "summary": "Patient is stable."},
    )

    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["summary"] == "Patient is stable."
    document = (await client.get(f"/documents/{document_id}")).json()
    assert document["status"] == "DONE"
    assert document["summary"] == "Patient is stable."


async def test_conflicting_completion_returns_409(client: AsyncClient) -> None:
    _, job_id = await enqueue_job(client)
    await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "DONE", "summary": "First result"},
    )

    response = await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "FAILED", "error": "Conflicting result"},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "job_already_completed"


async def test_failed_completion_is_publicly_readable(client: AsyncClient) -> None:
    document_id, job_id = await enqueue_job(client)

    response = await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "FAILED", "error": "  Could not parse document  "},
    )

    assert response.status_code == 200
    document = (await client.get(f"/documents/{document_id}")).json()
    assert document["status"] == "FAILED"
    assert document["summary"] is None
    assert document["error"] == "Could not parse document"
    assert document["completed_at"] is not None


async def test_unknown_job_and_invalid_payloads(client: AsyncClient) -> None:
    unknown = await client.post(
        "/internal/jobs/999/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "DONE", "summary": "Summary"},
    )
    contradictory = await client.post(
        "/internal/jobs/999/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "DONE", "summary": "Summary", "error": "Unexpected"},
    )
    blank = await client.post(
        "/internal/jobs/999/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "FAILED", "error": "   "},
    )

    assert unknown.status_code == 404
    assert contradictory.status_code == 422
    assert blank.status_code == 422


async def test_concurrent_identical_callbacks_are_idempotent(
    client_pair: tuple[AsyncClient, AsyncClient],
) -> None:
    first_client, second_client = client_pair
    _, job_id = await enqueue_job(first_client)
    payload = {"status": "DONE", "summary": "Concurrent result"}

    first, second = await asyncio.gather(
        first_client.post(
            f"/internal/jobs/{job_id}/complete", headers=INTERNAL_HEADERS, json=payload
        ),
        second_client.post(
            f"/internal/jobs/{job_id}/complete", headers=INTERNAL_HEADERS, json=payload
        ),
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


async def test_concurrent_conflicting_callbacks_choose_one_winner(
    client_pair: tuple[AsyncClient, AsyncClient],
) -> None:
    first_client, second_client = client_pair
    document_id, job_id = await enqueue_job(first_client)

    success, failure = await asyncio.gather(
        first_client.post(
            f"/internal/jobs/{job_id}/complete",
            headers=INTERNAL_HEADERS,
            json={"status": "DONE", "summary": "Success won"},
        ),
        second_client.post(
            f"/internal/jobs/{job_id}/complete",
            headers=INTERNAL_HEADERS,
            json={"status": "FAILED", "error": "Failure won"},
        ),
    )

    assert sorted((success.status_code, failure.status_code)) == [200, 409]
    document = (await second_client.get(f"/documents/{document_id}")).json()
    assert document["status"] in {"DONE", "FAILED"}
    assert (document["summary"] is None) != (document["error"] is None)
