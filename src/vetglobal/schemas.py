from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
