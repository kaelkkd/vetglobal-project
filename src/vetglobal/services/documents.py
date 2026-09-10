import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from vetglobal.errors import ConflictError, DocumentValidationError, NotFoundError
from vetglobal.models import Document, Job, JobStatus, Pet
from vetglobal.schemas import DocumentAccepted, DocumentResponse

READ_CHUNK_SIZE = 64 * 1024
IDEMPOTENCY_CONSTRAINT = "uq_documents_pet_id_idempotency_key"


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
    idempotency_key: str | None = None,
) -> DocumentAccepted:
    normalized_key = normalize_idempotency_key(idempotency_key)
    content_hash = hashlib.sha256(upload.content).hexdigest()
    fingerprint = request_fingerprint(upload, content_hash) if normalized_key else None

    try:
        async with session.begin():
            pet_exists = await session.scalar(select(Pet.id).where(Pet.id == pet_id))
            if pet_exists is None:
                raise NotFoundError("pet")

            if normalized_key is not None:
                existing = await _find_idempotent_upload(session, pet_id, normalized_key)
                if existing is not None:
                    return _replay_or_conflict(existing, fingerprint)

            document = Document(
                pet_id=pet_id,
                original_filename=upload.filename,
                media_type=upload.media_type,
                size_bytes=len(upload.content),
                sha256=content_hash,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
                content=upload.content,
            )
            session.add(document)
            await session.flush()

            job = Job(document_id=document.id, status=JobStatus.ENQUEUED)
            session.add(job)
            await session.flush()
    except IntegrityError as error:
        if _constraint_name(error) != IDEMPOTENCY_CONSTRAINT or normalized_key is None:
            raise
        existing = await _find_idempotent_upload(session, pet_id, normalized_key)
        if existing is None:
            raise
        return _replay_or_conflict(existing, fingerprint)

    return _acceptance(document.id, job.id)


def normalize_idempotency_key(key: str | None) -> str | None:
    if key is None:
        return None
    normalized = key.strip()
    if not normalized:
        raise DocumentValidationError(422, "invalid_idempotency_key", "Idempotency-Key is blank")
    return normalized


def request_fingerprint(upload: ValidatedDocument, content_hash: str) -> str:
    canonical = "\0".join((upload.filename, upload.media_type, content_hash)).encode()
    return hashlib.sha256(canonical).hexdigest()


async def _find_idempotent_upload(
    session: AsyncSession, pet_id: int, key: str
) -> tuple[int, str, int] | None:
    row = (
        await session.execute(
            select(
                Document.id.label("document_id"),
                Document.request_fingerprint,
                Job.id.label("job_id"),
            )
            .join(Job, Job.document_id == Document.id)
            .where(Document.pet_id == pet_id, Document.idempotency_key == key)
        )
    ).one_or_none()
    if row is None or row.request_fingerprint is None:
        return None
    return row.document_id, row.request_fingerprint, row.job_id


def _replay_or_conflict(
    existing: tuple[int, str, int], fingerprint: str | None
) -> DocumentAccepted:
    document_id, existing_fingerprint, job_id = existing
    if existing_fingerprint != fingerprint:
        raise ConflictError(
            "idempotency_key_conflict",
            "Idempotency-Key was already used with a different document",
        )
    return _acceptance(document_id, job_id)


def _acceptance(document_id: int, job_id: int) -> DocumentAccepted:
    return DocumentAccepted(
        document_id=document_id,
        job_id=job_id,
        status=JobStatus.ENQUEUED,
    )


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


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
