import hashlib
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncByteStream, AsyncClient
from sqlalchemy import create_engine, event, text

from vetglobal.models import Job


async def create_pet(client: AsyncClient) -> int:
    response = await client.post("/pets", json={"name": "Hank", "owner_name": "John"})
    assert response.status_code == 201
    return int(response.json()["id"])


async def test_upload_txt_creates_document_and_job_atomically(
    client: AsyncClient, migrated_database: str
) -> None:
    pet_id = await create_pet(client)
    content = b"Patient has intermittent vomiting."

    response = await client.post(
        f"/pets/{pet_id}/documents",
        files={"file": ("folder\\hank.TXT", content, "application/octet-stream")},
    )

    assert response.status_code == 202
    assert response.json() == {"document_id": 1, "job_id": 1, "status": "ENQUEUED"}

    read_response = await client.get("/documents/1")
    assert read_response.status_code == 200
    assert read_response.headers["cache-control"] == "no-store"
    assert read_response.json() == {
        "id": 1,
        "pet_id": pet_id,
        "filename": "hank.TXT",
        "media_type": "text/plain",
        "size_bytes": len(content),
        "created_at": read_response.json()["created_at"],
        "job_id": 1,
        "status": "ENQUEUED",
        "summary": None,
        "error": None,
        "completed_at": None,
    }

    engine = create_engine(migrated_database)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT content, sha256 FROM documents WHERE id = 1")).one()
    engine.dispose()
    assert row == (content, hashlib.sha256(content).hexdigest())


async def test_upload_accepts_basic_pdf_signature(client: AsyncClient) -> None:
    pet_id = await create_pet(client)
    content = b"%PDF-1.7\nminimal simulated PDF"

    response = await client.post(
        f"/pets/{pet_id}/documents",
        files={"file": ("record.pdf", content, "application/pdf")},
    )

    assert response.status_code == 202
    document = (await client.get("/documents/1")).json()
    assert document["media_type"] == "application/pdf"
    assert document["size_bytes"] == len(content)


async def test_duplicate_uploads_without_idempotency_key_create_distinct_jobs(
    client: AsyncClient,
) -> None:
    pet_id = await create_pet(client)
    files = {"file": ("record.txt", b"same content", "text/plain")}

    first = await client.post(f"/pets/{pet_id}/documents", files=files)
    second = await client.post(f"/pets/{pet_id}/documents", files=files)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["document_id"] != second.json()["document_id"]
    assert first.json()["job_id"] != second.json()["job_id"]


@pytest.mark.parametrize(
    ("filename", "content", "expected_status", "expected_code"),
    [
        ("record.docx", b"content", 415, "unsupported_document_type"),
        ("record.txt", b"", 422, "empty_document"),
        ("record.txt", b"\xff", 422, "invalid_text_document"),
        ("record.pdf", b"not a pdf", 422, "invalid_pdf_document"),
        ("record.txt", b"x" * 257, 413, "document_too_large"),
    ],
)
async def test_upload_rejects_invalid_content(
    client: AsyncClient,
    filename: str,
    content: bytes,
    expected_status: int,
    expected_code: str,
) -> None:
    pet_id = await create_pet(client)

    response = await client.post(
        f"/pets/{pet_id}/documents",
        files={"file": (filename, content, "application/octet-stream")},
    )

    assert response.status_code == expected_status
    assert response.json()["code"] == expected_code


async def test_upload_rejects_unknown_pet(client: AsyncClient) -> None:
    response = await client.post(
        "/pets/999/documents",
        files={"file": ("record.txt", b"valid", "text/plain")},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "pet_not_found"


class ChunkedBody(AsyncByteStream):
    async def __aiter__(self) -> AsyncIterator[bytes]:
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n\r\n'
        yield b"x" * 1200
        yield b"\r\n--boundary--\r\n"


async def test_chunked_request_body_limit_is_enforced(client: AsyncClient) -> None:
    pet_id = await create_pet(client)

    response = await client.post(
        f"/pets/{pet_id}/documents",
        headers={"Content-Type": "multipart/form-data; boundary=boundary"},
        content=ChunkedBody(),
    )

    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"


async def test_failed_job_insert_rolls_back_document(
    client: AsyncClient, migrated_database: str
) -> None:
    pet_id = await create_pet(client)

    def fail_job_insert(*args: object) -> None:
        raise RuntimeError("simulated job insert failure")

    event.listen(Job, "before_insert", fail_job_insert)
    try:
        with pytest.raises(RuntimeError, match="simulated job insert failure"):
            await client.post(
                f"/pets/{pet_id}/documents",
                files={"file": ("record.txt", b"valid", "text/plain")},
            )
    finally:
        event.remove(Job, "before_insert", fail_job_insert)

    engine = create_engine(migrated_database)
    with engine.connect() as connection:
        document_count = connection.scalar(text("SELECT count(*) FROM documents"))
        job_count = connection.scalar(text("SELECT count(*) FROM jobs"))
    engine.dispose()
    assert (document_count, job_count) == (0, 0)


async def test_get_unknown_document_returns_404(client: AsyncClient) -> None:
    response = await client.get("/documents/999")

    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"
