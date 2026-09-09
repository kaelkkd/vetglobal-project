import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from vetglobal.db import session_dependency
from vetglobal.errors import DomainError
from vetglobal.schemas import ErrorResponse, JobCompletion, JobResponse
from vetglobal.services.jobs import complete_job

router = APIRouter(prefix="/internal/jobs", tags=["internal"])


async def require_internal_token(
    request: Request,
    token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> None:
    expected = request.app.state.settings.internal_service_token.get_secret_value()
    if token is None or not secrets.compare_digest(token.encode(), expected.encode()):
        raise DomainError(401, "invalid_internal_token", "Invalid internal service token")


@router.post(
    "/{job_id}/complete",
    response_model=JobResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_internal_token)],
)
async def complete_job_route(
    job_id: Annotated[int, Path(gt=0)],
    payload: JobCompletion,
    session: Annotated[AsyncSession, Depends(session_dependency)],
) -> JobResponse:
    return await complete_job(session, job_id, payload)
