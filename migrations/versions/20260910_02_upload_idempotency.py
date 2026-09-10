"""Add upload idempotency fields.

Revision ID: 20260910_02
Revises: 20260908_01
Create Date: 2026-09-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_02"
down_revision: str | None = "20260908_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("idempotency_key", sa.String(200), nullable=True))
    op.add_column("documents", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.create_check_constraint(
        "ck_documents_idempotency_pair",
        "documents",
        "(idempotency_key IS NULL AND request_fingerprint IS NULL) OR "
        "(idempotency_key IS NOT NULL AND request_fingerprint IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_documents_idempotency_key_nonempty",
        "documents",
        "idempotency_key IS NULL OR char_length(btrim(idempotency_key)) > 0",
    )
    op.create_check_constraint(
        "ck_documents_fingerprint_length",
        "documents",
        "request_fingerprint IS NULL OR octet_length(request_fingerprint) = 64",
    )
    op.create_unique_constraint(
        "uq_documents_pet_id_idempotency_key",
        "documents",
        ["pet_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_pet_id_idempotency_key", "documents", type_="unique")
    op.drop_constraint("ck_documents_fingerprint_length", "documents", type_="check")
    op.drop_constraint("ck_documents_idempotency_key_nonempty", "documents", type_="check")
    op.drop_constraint("ck_documents_idempotency_pair", "documents", type_="check")
    op.drop_column("documents", "request_fingerprint")
    op.drop_column("documents", "idempotency_key")
