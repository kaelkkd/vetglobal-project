import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vetglobal.errors import ConflictError, NotFoundError
from vetglobal.models import Job, JobStatus
from vetglobal.schemas import DoneCompletion, JobCompletion, JobResponse

logger = logging.getLogger("vetglobal.jobs")


def _matches_existing(job: Job, payload: JobCompletion) -> bool:
    if payload.status != job.status:
        return False
    if isinstance(payload, DoneCompletion):
        return job.summary == payload.summary and job.error is None
    return job.error == payload.error and job.summary is None


async def complete_job(
    session: AsyncSession,
    job_id: int,
    payload: JobCompletion,
) -> JobResponse:
    async with session.begin():
        job = await session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None:
            raise NotFoundError("job")

        if job.status != JobStatus.ENQUEUED:
            if not _matches_existing(job, payload):
                raise ConflictError(
                    "job_already_completed",
                    "Job has already completed with a different result",
                )
        else:
            job.status = payload.status
            job.completed_at = datetime.now(UTC)
            if isinstance(payload, DoneCompletion):
                job.summary = payload.summary
            else:
                job.error = payload.error
            await session.flush()

    if job.completed_at is None:  # Protected by the state constraint and transition above.
        raise RuntimeError("terminal job is missing completed_at")

    duration_ms = max(0, int((job.completed_at - job.created_at).total_seconds() * 1000))
    logger.info(
        "job completed",
        extra={
            "document_id": job.document_id,
            "job_id": job.id,
            "job_status": job.status,
            "job_duration_ms": duration_ms,
        },
    )
    return JobResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=JobStatus(job.status),
        summary=job.summary,
        error=job.error,
        completed_at=job.completed_at,
    )
