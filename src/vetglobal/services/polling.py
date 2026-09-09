import asyncio
from time import monotonic

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vetglobal.errors import NotFoundError
from vetglobal.models import JobStatus
from vetglobal.schemas import DocumentResponse
from vetglobal.services.documents import get_document


async def _read_once(
    session_factory: async_sessionmaker[AsyncSession], document_id: int
) -> DocumentResponse:
    async with session_factory() as session:
        return await get_document(session, document_id)


async def poll_document(
    request: Request,
    session_factory: async_sessionmaker[AsyncSession],
    document_id: int,
    after_job_id: int,
    timeout_seconds: float,
    interval_seconds: float,
) -> DocumentResponse | None:
    deadline = monotonic() + timeout_seconds
    first_check = True

    while True:
        remaining = deadline - monotonic()
        if remaining <= 0 and not first_check:
            return None
        first_check = False

        try:
            async with asyncio.timeout(max(remaining, 0.001)):
                document = await _read_once(session_factory, document_id)
        except TimeoutError:
            return None
        except NotFoundError:
            raise

        if document.status in {JobStatus.DONE, JobStatus.FAILED} and document.job_id > after_job_id:
            return document

        if await request.is_disconnected():
            return None

        remaining = deadline - monotonic()
        if remaining <= 0:
            return None
        await asyncio.sleep(min(interval_seconds, remaining))
