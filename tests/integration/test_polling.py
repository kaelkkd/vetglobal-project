import asyncio
from time import monotonic

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


async def test_poll_returns_already_completed_result(client: AsyncClient) -> None:
    document_id, job_id = await enqueue_job(client)
    await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "DONE", "summary": "Ready"},
    )

    response = await client.get(f"/documents/{document_id}/poll?after_job_id=0")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["summary"] == "Ready"


async def test_poll_observes_delayed_failure(client: AsyncClient) -> None:
    document_id, job_id = await enqueue_job(client)
    poll_task = asyncio.create_task(client.get(f"/documents/{document_id}/poll"))
    await asyncio.sleep(0.02)

    await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "FAILED", "error": "Worker failed"},
    )
    response = await poll_task

    assert response.status_code == 200
    assert response.json()["status"] == "FAILED"
    assert response.json()["error"] == "Worker failed"


async def test_poll_times_out_with_empty_204(client: AsyncClient) -> None:
    document_id, _ = await enqueue_job(client)
    started = monotonic()

    response = await client.get(f"/documents/{document_id}/poll")

    elapsed = monotonic() - started
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"
    assert 0.06 <= elapsed < 0.5


async def test_consumed_cursor_times_out(client: AsyncClient) -> None:
    document_id, job_id = await enqueue_job(client)
    await client.post(
        f"/internal/jobs/{job_id}/complete",
        headers=INTERNAL_HEADERS,
        json={"status": "DONE", "summary": "Consumed"},
    )

    response = await client.get(f"/documents/{document_id}/poll", params={"after_job_id": job_id})

    assert response.status_code == 204


async def test_poll_validates_document_and_cursor(client: AsyncClient) -> None:
    missing = await client.get("/documents/999/poll")
    invalid_cursor = await client.get("/documents/1/poll?after_job_id=-1")

    assert missing.status_code == 404
    assert invalid_cursor.status_code == 422
