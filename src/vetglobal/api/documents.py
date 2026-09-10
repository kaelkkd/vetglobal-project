from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vetglobal.config import Settings
from vetglobal.db import session_dependency
from vetglobal.schemas import DocumentAccepted, DocumentResponse, ErrorResponse
from vetglobal.services.documents import create_document_job, get_document, validate_upload
from vetglobal.services.polling import poll_document

router = APIRouter(tags=["documents"])


@router.post(
    "/pets/{pet_id}/documents",
    response_model=DocumentAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
)
async def upload_document(
    pet_id: Annotated[int, Path(gt=0)],
    file: Annotated[UploadFile, File()],
    request: Request,
    session: Annotated[AsyncSession, Depends(session_dependency)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> DocumentAccepted:
    settings: Settings = request.app.state.settings
    validated = await validate_upload(file, settings.max_file_size_bytes)
    return await create_document_job(session, pet_id, validated, idempotency_key)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    responses={404: {"model": ErrorResponse}},
)
async def read_document(
    document_id: Annotated[int, Path(gt=0)],
    response: Response,
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> DocumentResponse:
    response.headers["Cache-Control"] = "no-store"
    return await get_document(session, document_id)


@router.get(
    "/documents/{document_id}/poll",
    response_model=DocumentResponse,
    responses={
        204: {"description": "No qualifying terminal result before the timeout"},
        404: {"model": ErrorResponse},
    },
)
async def poll_document_route(
    document_id: Annotated[int, Path(gt=0)],
    request: Request,
    after_job_id: Annotated[int, Query(ge=0)] = 0,
) -> DocumentResponse | Response:
    settings: Settings = request.app.state.settings
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    document = await poll_document(
        request,
        session_factory,
        document_id,
        after_job_id,
        settings.polling_timeout_seconds,
        settings.polling_interval_seconds,
    )
    if document is None:
        return Response(
            status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"}
        )
    return document
