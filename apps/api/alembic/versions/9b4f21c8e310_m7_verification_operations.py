"""m7_verification_operations

Revision ID: 9b4f21c8e310
Revises: 61d97d129fb9
Create Date: 2026-11-24 20:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9b4f21c8e310"
down_revision: Union[str, None] = "61d97d129fb9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("application_routes", sa.Column("verified_by_user_id", sa.UUID(), nullable=True))
    op.add_column("application_routes", sa.Column("verification_method", sa.String(length=60), nullable=True))
    op.add_column("application_routes", sa.Column("verification_notes", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_application_routes_verified_by_user_id",
        "application_routes",
        "users",
        ["verified_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "application_route_audits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("route_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(length=30), nullable=True),
        sa.Column("to_status", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_role", sa.String(length=30), nullable=False),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("rejection_reason_code", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checks_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["route_id"], ["application_routes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_application_route_audits_route_id"), "application_route_audits", ["route_id"], unique=False)
    op.create_index(op.f("ix_application_route_audits_to_status"), "application_route_audits", ["to_status"], unique=False)

    op.add_column(
        "application_submission_evidence",
        sa.Column("rejection_reason_code", sa.String(length=60), nullable=True),
    )

    op.create_table(
        "evidence_review_audits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("from_review_status", sa.String(length=30), nullable=True),
        sa.Column("to_review_status", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("actor_role", sa.String(length=30), nullable=False),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("rejection_reason_code", sa.String(length=60), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["application_submission_evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_evidence_review_audits_application_id"), "evidence_review_audits", ["application_id"], unique=False)
    op.create_index(op.f("ix_evidence_review_audits_evidence_id"), "evidence_review_audits", ["evidence_id"], unique=False)
    op.create_index(op.f("ix_evidence_review_audits_to_review_status"), "evidence_review_audits", ["to_review_status"], unique=False)

    # Backfill initial 'uploaded' audit records for any pre-migration evidence rows
    op.execute(
        """
        INSERT INTO evidence_review_audits (
            id, evidence_id, application_id, from_review_status, to_review_status,
            action, actor_role, notes, created_at
        )
        SELECT
            gen_random_uuid(), id, application_id, NULL, 'pending',
            'uploaded', 'student',
            COALESCE(submitted_note, 'Uploaded submission confirmation proof to Document Vault.'),
            submitted_at
        FROM application_submission_evidence
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence_review_audits a
            WHERE a.evidence_id = application_submission_evidence.id AND a.action = 'uploaded'
        )
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_evidence_review_audits_to_review_status"), table_name="evidence_review_audits")
    op.drop_index(op.f("ix_evidence_review_audits_evidence_id"), table_name="evidence_review_audits")
    op.drop_index(op.f("ix_evidence_review_audits_application_id"), table_name="evidence_review_audits")
    op.drop_table("evidence_review_audits")

    op.drop_column("application_submission_evidence", "rejection_reason_code")

    op.drop_index(op.f("ix_application_route_audits_to_status"), table_name="application_route_audits")
    op.drop_index(op.f("ix_application_route_audits_route_id"), table_name="application_route_audits")
    op.drop_table("application_route_audits")

    op.drop_constraint("fk_application_routes_verified_by_user_id", "application_routes", type_="foreignkey")
    op.drop_column("application_routes", "verification_notes")
    op.drop_column("application_routes", "verification_method")
    op.drop_column("application_routes", "verified_by_user_id")
