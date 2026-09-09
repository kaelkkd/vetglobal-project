"""Create pets, documents, and jobs.

Revision ID: 20260908_01
Revises:
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(btrim(name)) > 0", name="ck_pets_name_nonempty"),
        sa.CheckConstraint("char_length(btrim(owner_name)) > 0", name="ck_pets_owner_nonempty"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pet_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes > 0", name="ck_documents_size_positive"),
        sa.CheckConstraint("octet_length(sha256) = 64", name="ck_documents_sha256_length"),
        sa.ForeignKeyConstraint(["pet_id"], ["pets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_pet_id", "documents", ["pet_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.String(length=10000), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'ENQUEUED' AND summary IS NULL AND error IS NULL "
            "AND completed_at IS NULL) OR "
            "(status = 'DONE' AND summary IS NOT NULL AND error IS NULL "
            "AND completed_at IS NOT NULL) OR "
            "(status = 'FAILED' AND summary IS NULL AND error IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_jobs_valid_state",
        ),
        sa.CheckConstraint(
            "summary IS NULL OR char_length(btrim(summary)) > 0", name="ck_jobs_summary"
        ),
        sa.CheckConstraint("error IS NULL OR char_length(btrim(error)) > 0", name="ck_jobs_error"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_index("ix_documents_pet_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("pets")
