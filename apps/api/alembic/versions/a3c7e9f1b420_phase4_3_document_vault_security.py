"""phase4_3_document_vault_security

Revision ID: a3c7e9f1b420
Revises: f1c9e4a2b870
Create Date: 2026-11-26 22:00:00.000000

Adds storage provider abstraction, MIME tracking, encryption-at-rest metadata,
and malware scanning / quarantine lifecycle fields to `documents`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3c7e9f1b420"
down_revision: Union[str, None] = "f1c9e4a2b870"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("mime_type", sa.String(100), nullable=False, server_default="application/octet-stream"),
    )
    op.add_column(
        "documents",
        sa.Column("storage_backend", sa.String(32), nullable=False, server_default="local"),
    )
    op.add_column("documents", sa.Column("storage_key", sa.String(500), nullable=True))
    op.add_column(
        "documents",
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "documents",
        sa.Column("scan_status", sa.String(32), nullable=False, server_default="uploaded"),
    )
    op.add_column("documents", sa.Column("scan_engine", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("scan_details", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("quarantined_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_scan_status", "documents", ["scan_status"])


def downgrade() -> None:
    op.drop_index("ix_documents_scan_status", table_name="documents")
    op.drop_column("documents", "quarantined_at")
    op.drop_column("documents", "scanned_at")
    op.drop_column("documents", "scan_details")
    op.drop_column("documents", "scan_engine")
    op.drop_column("documents", "scan_status")
    op.drop_column("documents", "is_encrypted")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "storage_backend")
    op.drop_column("documents", "mime_type")
