from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vetglobal.errors import DocumentValidationError, NotFoundError
from vetglobal.models import Document, Job, JobStatus, Pet
from vetglobal.schemas import DocumentAccepted, DocumentResponse

READ_CHUNK_SIZE = 64 * 1024


@dataclass(frozen=True, slots=True)
class ValidatedDocument:
    filename: str
    media_type: str
    content: bytes


def normalize_filename(filename: str | None) -> str:
    normalized = PurePosixPath((filename or "").replace("\\", "/")).name.strip()
    if not normalized:
        raise DocumentValidationError(422, "invalid_filename", "A filename is required")
    if len(normalized) > 255:
        raise DocumentValidationError(422, "invalid_filename", "Filename is too long")
    return normalized


async def validate_upload(file: UploadFile, max_file_size_bytes: int) -> ValidatedDocument:
    filename = normalize_filename(file.filename)
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in {".txt", ".pdf"}:
        raise DocumentValidationError(
            415,
            "unsupported_document_type",
            "Only .txt and .pdf documents are supported",
        )

    content = bytearray()
    try:
        while chunk := await file.read(READ_CHUNK_SIZE):
            content.extend(chunk)
            if len(content) > max_file_size_bytes:
                raise DocumentValidationError(
                    413,
                    "document_too_large",
                    "Document exceeds the configured size limit",
                )
    finally:
        await file.close()

    if not content:
        raise DocumentValidationError(422, "empty_document", "Document must not be empty")

    raw_content = bytes(content)
    if extension == ".txt":
        try:
            raw_content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise DocumentValidationError(
                422, "invalid_text_document", "Text documents must contain valid UTF-8"
            ) from error
        media_type = "text/plain"
    else:
        if not raw_content.startswith(b"%PDF-"):
            raise DocumentValidationError(
                422, "invalid_pdf_document", "PDF documents must have a valid PDF signature"
            )
        media_type = "application/pdf"

    return ValidatedDocument(filename, media_type, raw_content)


async def create_document_job(
    session: AsyncSession,
    pet_id: int,
    upload: ValidatedDocument,
) -> DocumentAccepted:
    import hashlib

    async with session.begin():
        pet_exists = await session.scalar(select(Pet.id).where(Pet.id == pet_id))
        if pet_exists is None:
            raise NotFoundError("pet")

        document = Document(
            pet_id=pet_id,
            original_filename=upload.filename,
            media_type=upload.media_type,
            size_bytes=len(upload.content),
            sha256=hashlib.sha256(upload.content).hexdigest(),
            content=upload.content,
        )
        session.add(document)
        await session.flush()

        job = Job(document_id=document.id, status=JobStatus.ENQUEUED)
        session.add(job)
        await session.flush()

    return DocumentAccepted(document_id=document.id, job_id=job.id, status=JobStatus.ENQUEUED)


async def get_document(session: AsyncSession, document_id: int) -> DocumentResponse:
    row = (
        (
            await session.execute(
                select(
                    Document.id,
                    Document.pet_id,
                    Document.original_filename.label("filename"),
                    Document.media_type,
                    Document.size_bytes,
                    Document.created_at,
                    Job.id.label("job_id"),
                    Job.status,
                    Job.summary,
                    Job.error,
                    Job.completed_at,
                )
                .join(Job, Job.document_id == Document.id)
                .where(Document.id == document_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFoundError("document")
    return DocumentResponse.model_validate(row)
