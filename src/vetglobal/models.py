from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobStatus(StrEnum):
    ENQUEUED = "ENQUEUED"
    DONE = "DONE"
    FAILED = "FAILED"


class Pet(Base):
    __tablename__ = "pets"
    __table_args__ = (
        CheckConstraint("char_length(btrim(name)) > 0", name="ck_pets_name_nonempty"),
        CheckConstraint("char_length(btrim(owner_name)) > 0", name="ck_pets_owner_nonempty"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    owner_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="pet")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_documents_size_positive"),
        CheckConstraint("octet_length(sha256) = 64", name="ck_documents_sha256_length"),
        Index("ix_documents_pet_id", "pet_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id", ondelete="RESTRICT"))
    original_filename: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pet: Mapped[Pet] = relationship(back_populates="documents")
    job: Mapped["Job"] = relationship(back_populates="document", uselist=False)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "(status = 'ENQUEUED' AND summary IS NULL AND error IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'DONE' AND summary IS NOT NULL AND error IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'FAILED' AND summary IS NULL AND error IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_jobs_valid_state",
        ),
        CheckConstraint(
            "summary IS NULL OR char_length(btrim(summary)) > 0", name="ck_jobs_summary"
        ),
        CheckConstraint("error IS NULL OR char_length(btrim(error)) > 0", name="ck_jobs_error"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), unique=True
    )
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.ENQUEUED)
    summary: Mapped[str | None] = mapped_column(String(10_000))
    error: Mapped[str | None] = mapped_column(String(2_000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document] = relationship(back_populates="job")
