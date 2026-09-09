from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vetglobal.models import JobStatus


class PetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    owner_name: str = Field(min_length=1, max_length=200)

    @field_validator("name", "owner_name")
    @classmethod
    def strip_and_reject_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class PetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_name: str
    created_at: datetime


class ErrorResponse(BaseModel):
    code: str
    message: str


class DocumentAccepted(BaseModel):
    document_id: int
    job_id: int
    status: Literal[JobStatus.ENQUEUED]


class DocumentResponse(BaseModel):
    id: int
    pet_id: int
    filename: str
    media_type: str
    size_bytes: int
    created_at: datetime
    job_id: int
    status: JobStatus
    summary: str | None
    error: str | None
    completed_at: datetime | None


class DoneCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[JobStatus.DONE]
    summary: str = Field(min_length=1, max_length=10_000)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("summary must not be blank")
        return normalized


class FailedCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[JobStatus.FAILED]
    error: str = Field(min_length=1, max_length=2_000)

    @field_validator("error")
    @classmethod
    def normalize_error(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("error must not be blank")
        return normalized


JobCompletion = Annotated[DoneCompletion | FailedCompletion, Field(discriminator="status")]


class JobResponse(BaseModel):
    job_id: int
    document_id: int
    status: JobStatus
    summary: str | None
    error: str | None
    completed_at: datetime
