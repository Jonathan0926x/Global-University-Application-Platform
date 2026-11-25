"""m7_3_database_enforced_audit_retention

Revision ID: d8f2a9b41e03
Revises: c3e8a4f19d72
Create Date: 2026-11-25 00:15:00.000000

Enforces append-only retention at the PostgreSQL layer for:
- application_route_audits
- application_status_history
- evidence_review_audits

Preserves safe parent deletion (`Application`, `ApplicationSubmissionEvidence`,
`ApplicationRoute`, `User`) by switching audit FKs from `ON DELETE CASCADE` to
`ON DELETE SET NULL`, retaining original parent UUIDs in `retained_*_id` and
recording `parent_deleted_at` via database triggers while blocking all direct
UPDATE and DELETE operations on audit records.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d8f2a9b41e03"
down_revision: Union[str, None] = "c3e8a4f19d72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Retained parent identifier & deletion timestamp columns
    op.add_column(
        "application_route_audits",
        sa.Column("retained_route_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "application_route_audits",
        sa.Column("parent_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "application_status_history",
        sa.Column("retained_application_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "application_status_history",
        sa.Column("parent_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "evidence_review_audits",
        sa.Column("retained_evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "evidence_review_audits",
        sa.Column("retained_application_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "evidence_review_audits",
        sa.Column("parent_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Backfill retained parent IDs for existing audit rows
    op.execute(
        "UPDATE application_route_audits SET retained_route_id = route_id WHERE retained_route_id IS NULL;"
    )
    op.execute(
        "UPDATE application_status_history SET retained_application_id = application_id WHERE retained_application_id IS NULL;"
    )
    op.execute(
        "UPDATE evidence_review_audits SET retained_evidence_id = evidence_id, retained_application_id = application_id "
        "WHERE retained_evidence_id IS NULL OR retained_application_id IS NULL;"
    )

    op.create_index("ix_application_route_audits_retained_route_id", "application_route_audits", ["retained_route_id"])
    op.create_index("ix_application_status_history_retained_app_id", "application_status_history", ["retained_application_id"])
    op.create_index("ix_evidence_review_audits_retained_evidence_id", "evidence_review_audits", ["retained_evidence_id"])
    op.create_index("ix_evidence_review_audits_retained_app_id", "evidence_review_audits", ["retained_application_id"])

    # 2. Switch parent FKs on audit tables from ON DELETE CASCADE -> nullable + ON DELETE SET NULL
    op.alter_column("application_route_audits", "route_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.drop_constraint("application_route_audits_route_id_fkey", "application_route_audits", type_="foreignkey")
    op.create_foreign_key(
        "application_route_audits_route_id_fkey",
        "application_route_audits",
        "application_routes",
        ["route_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("application_status_history", "application_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.drop_constraint("application_status_history_application_id_fkey", "application_status_history", type_="foreignkey")
    op.create_foreign_key(
        "application_status_history_application_id_fkey",
        "application_status_history",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("evidence_review_audits", "evidence_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.drop_constraint("evidence_review_audits_evidence_id_fkey", "evidence_review_audits", type_="foreignkey")
    op.create_foreign_key(
        "evidence_review_audits_evidence_id_fkey",
        "evidence_review_audits",
        "application_submission_evidence",
        ["evidence_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column("evidence_review_audits", "application_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.drop_constraint("evidence_review_audits_application_id_fkey", "evidence_review_audits", type_="foreignkey")
    op.create_foreign_key(
        "evidence_review_audits_application_id_fkey",
        "evidence_review_audits",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Database triggers: populate retained_*_id on INSERT; block DELETE and non-RI UPDATE
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_populate_retained_ids()
        RETURNS trigger AS $$
        BEGIN
            IF TG_TABLE_NAME = 'application_route_audits' THEN
                NEW.retained_route_id := COALESCE(NEW.retained_route_id, NEW.route_id);
            ELSIF TG_TABLE_NAME = 'application_status_history' THEN
                NEW.retained_application_id := COALESCE(NEW.retained_application_id, NEW.application_id);
            ELSIF TG_TABLE_NAME = 'evidence_review_audits' THEN
                NEW.retained_evidence_id := COALESCE(NEW.retained_evidence_id, NEW.evidence_id);
                NEW.retained_application_id := COALESCE(NEW.retained_application_id, NEW.application_id);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_mutation()
        RETURNS trigger AS $$
        DECLARE
            immutable_unchanged BOOLEAN := FALSE;
            fk_safely_detached BOOLEAN := FALSE;
            parent_detached BOOLEAN := FALSE;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'Audit table % is append-only; deletes are prohibited', TG_TABLE_NAME
                    USING ERRCODE = 'check_violation';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                -- Only PostgreSQL referential-integrity triggers (ON DELETE SET NULL) may clear
                -- nullable FK pointers when a parent record is deleted; all direct UPDATEs fail.
                IF pg_trigger_depth() > 0 THEN
                    IF TG_TABLE_NAME = 'application_route_audits' THEN
                        immutable_unchanged :=
                            (NEW.id, NEW.from_status, NEW.to_status, NEW.action, NEW.actor_role,
                             NEW.actor_email, NEW.rejection_reason_code, NEW.notes, NEW.checks_json,
                             NEW.created_at, NEW.retained_route_id)
                            IS NOT DISTINCT FROM
                            (OLD.id, OLD.from_status, OLD.to_status, OLD.action, OLD.actor_role,
                             OLD.actor_email, OLD.rejection_reason_code, OLD.notes, OLD.checks_json,
                             OLD.created_at, OLD.retained_route_id);
                        fk_safely_detached :=
                            (NEW.route_id IS NOT DISTINCT FROM OLD.route_id OR (OLD.route_id IS NOT NULL AND NEW.route_id IS NULL))
                            AND (NEW.actor_user_id IS NOT DISTINCT FROM OLD.actor_user_id OR (OLD.actor_user_id IS NOT NULL AND NEW.actor_user_id IS NULL))
                            AND ((NEW.route_id IS DISTINCT FROM OLD.route_id) OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id));
                        parent_detached := (OLD.route_id IS NOT NULL AND NEW.route_id IS NULL);
                    ELSIF TG_TABLE_NAME = 'application_status_history' THEN
                        immutable_unchanged :=
                            (NEW.id, NEW.from_status, NEW.to_status, NEW.actor_role,
                             NEW.reason, NEW.metadata_json, NEW.changed_at, NEW.retained_application_id)
                            IS NOT DISTINCT FROM
                            (OLD.id, OLD.from_status, OLD.to_status, OLD.actor_role,
                             OLD.reason, OLD.metadata_json, OLD.changed_at, OLD.retained_application_id);
                        fk_safely_detached :=
                            (NEW.application_id IS NOT DISTINCT FROM OLD.application_id OR (OLD.application_id IS NOT NULL AND NEW.application_id IS NULL))
                            AND (NEW.actor_user_id IS NOT DISTINCT FROM OLD.actor_user_id OR (OLD.actor_user_id IS NOT NULL AND NEW.actor_user_id IS NULL))
                            AND ((NEW.application_id IS DISTINCT FROM OLD.application_id) OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id));
                        parent_detached := (OLD.application_id IS NOT NULL AND NEW.application_id IS NULL);
                    ELSIF TG_TABLE_NAME = 'evidence_review_audits' THEN
                        immutable_unchanged :=
                            (NEW.id, NEW.from_review_status, NEW.to_review_status, NEW.action, NEW.actor_role,
                             NEW.actor_email, NEW.rejection_reason_code, NEW.notes, NEW.created_at,
                             NEW.retained_evidence_id, NEW.retained_application_id)
                            IS NOT DISTINCT FROM
                            (OLD.id, OLD.from_review_status, OLD.to_review_status, OLD.action, OLD.actor_role,
                             OLD.actor_email, OLD.rejection_reason_code, OLD.notes, OLD.created_at,
                             OLD.retained_evidence_id, OLD.retained_application_id);
                        fk_safely_detached :=
                            (NEW.evidence_id IS NOT DISTINCT FROM OLD.evidence_id OR (OLD.evidence_id IS NOT NULL AND NEW.evidence_id IS NULL))
                            AND (NEW.application_id IS NOT DISTINCT FROM OLD.application_id OR (OLD.application_id IS NOT NULL AND NEW.application_id IS NULL))
                            AND (NEW.actor_user_id IS NOT DISTINCT FROM OLD.actor_user_id OR (OLD.actor_user_id IS NOT NULL AND NEW.actor_user_id IS NULL))
                            AND ((NEW.evidence_id IS DISTINCT FROM OLD.evidence_id) OR (NEW.application_id IS DISTINCT FROM OLD.application_id) OR (NEW.actor_user_id IS DISTINCT FROM OLD.actor_user_id));
                        parent_detached := (OLD.evidence_id IS NOT NULL AND NEW.evidence_id IS NULL) OR (OLD.application_id IS NOT NULL AND NEW.application_id IS NULL);
                    END IF;

                    IF immutable_unchanged AND fk_safely_detached THEN
                        IF parent_detached THEN
                            NEW.parent_deleted_at := COALESCE(OLD.parent_deleted_at, clock_timestamp());
                        ELSE
                            NEW.parent_deleted_at := OLD.parent_deleted_at;
                        END IF;
                        RETURN NEW;
                    END IF;
                END IF;

                RAISE EXCEPTION 'Audit table % is append-only; updates are prohibited', TG_TABLE_NAME
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for tbl in ("application_route_audits", "application_status_history", "evidence_review_audits"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{tbl}_retain_parent
            BEFORE INSERT ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION audit_populate_retained_ids();
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{tbl}_append_only
            BEFORE UPDATE OR DELETE ON {tbl}
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();
            """
        )


def downgrade() -> None:
    for tbl in ("application_route_audits", "application_status_history", "evidence_review_audits"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_append_only ON {tbl};")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tbl}_retain_parent ON {tbl};")

    op.execute("DROP FUNCTION IF EXISTS prevent_audit_mutation();")
    op.execute("DROP FUNCTION IF EXISTS audit_populate_retained_ids();")

    # Clean up detached audit rows before restoring NOT NULL + ON DELETE CASCADE on rollback
    op.execute("DELETE FROM evidence_review_audits WHERE evidence_id IS NULL OR application_id IS NULL;")
    op.execute("DELETE FROM application_status_history WHERE application_id IS NULL;")
    op.execute("DELETE FROM application_route_audits WHERE route_id IS NULL;")

    op.drop_constraint("evidence_review_audits_application_id_fkey", "evidence_review_audits", type_="foreignkey")
    op.create_foreign_key(
        "evidence_review_audits_application_id_fkey",
        "evidence_review_audits",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("evidence_review_audits", "application_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.drop_constraint("evidence_review_audits_evidence_id_fkey", "evidence_review_audits", type_="foreignkey")
    op.create_foreign_key(
        "evidence_review_audits_evidence_id_fkey",
        "evidence_review_audits",
        "application_submission_evidence",
        ["evidence_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("evidence_review_audits", "evidence_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.drop_constraint("application_status_history_application_id_fkey", "application_status_history", type_="foreignkey")
    op.create_foreign_key(
        "application_status_history_application_id_fkey",
        "application_status_history",
        "applications",
        ["application_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("application_status_history", "application_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.drop_constraint("application_route_audits_route_id_fkey", "application_route_audits", type_="foreignkey")
    op.create_foreign_key(
        "application_route_audits_route_id_fkey",
        "application_route_audits",
        "application_routes",
        ["route_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("application_route_audits", "route_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.drop_index("ix_evidence_review_audits_retained_app_id", table_name="evidence_review_audits")
    op.drop_index("ix_evidence_review_audits_retained_evidence_id", table_name="evidence_review_audits")
    op.drop_index("ix_application_status_history_retained_app_id", table_name="application_status_history")
    op.drop_index("ix_application_route_audits_retained_route_id", table_name="application_route_audits")

    op.drop_column("evidence_review_audits", "parent_deleted_at")
    op.drop_column("evidence_review_audits", "retained_application_id")
    op.drop_column("evidence_review_audits", "retained_evidence_id")

    op.drop_column("application_status_history", "parent_deleted_at")
    op.drop_column("application_status_history", "retained_application_id")

    op.drop_column("application_route_audits", "parent_deleted_at")
    op.drop_column("application_route_audits", "retained_route_id")
