"""phase4_provenance_and_freshness_governance

Revision ID: f1c9e4a2b870
Revises: e4a7c2d901b5
Create Date: 2026-11-25 06:00:00.000000

Extends ScholarshipProgram, GradeConversionRule, CredentialRecognitionRule,
and CountryQualification with verifiable provenance, native currency/duration
metadata, qualification structure fields, and non-destructive data freshness
governance without fabricating missing historical dates, versions, or reviewers.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f1c9e4a2b870"
down_revision: Union[str, None] = "e4a7c2d901b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ScholarshipProgram provenance, native amounts, duration & freshness
    op.add_column("scholarship_programs", sa.Column("sponsoring_institution", sa.String(255), nullable=True))
    op.add_column(
        "scholarship_programs",
        sa.Column("source_type", sa.String(40), nullable=False, server_default="unknown"),
    )
    op.add_column("scholarship_programs", sa.Column("source_version", sa.String(64), nullable=True))
    op.add_column("scholarship_programs", sa.Column("academic_year", sa.String(20), nullable=True))
    op.add_column("scholarship_programs", sa.Column("award_fixed_usd", sa.Numeric(12, 2), nullable=True))
    op.add_column("scholarship_programs", sa.Column("native_amount_min", sa.Numeric(14, 2), nullable=True))
    op.add_column("scholarship_programs", sa.Column("native_amount_max", sa.Numeric(14, 2), nullable=True))
    op.add_column(
        "scholarship_programs",
        sa.Column("covers_travel", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("scholarship_programs", sa.Column("funding_duration_years", sa.Numeric(4, 2), nullable=True))
    op.add_column("scholarship_programs", sa.Column("max_funding_periods", sa.Integer(), nullable=True))
    op.add_column("scholarship_programs", sa.Column("renewal_conditions", sa.Text(), nullable=True))
    op.add_column(
        "scholarship_programs",
        sa.Column("verification_method", sa.String(60), nullable=False, server_default="unknown"),
    )
    op.add_column("scholarship_programs", sa.Column("verified_by", sa.String(255), nullable=True))
    op.add_column("scholarship_programs", sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "scholarship_programs",
        sa.Column("freshness_status", sa.String(40), nullable=False, server_default="requires_manual_review"),
    )
    op.add_column(
        "scholarship_programs",
        sa.Column("requires_manual_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "scholarship_programs",
        sa.Column(
            "claim_provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("scholarship_programs", sa.Column("conflict_notes", sa.Text(), nullable=True))
    op.create_index("ix_scholarship_programs_freshness_status", "scholarship_programs", ["freshness_status"])

    # 2. GradeConversionRule provenance, structure & freshness
    op.add_column("grade_conversion_rules", sa.Column("issuing_authority", sa.String(255), nullable=True))
    op.add_column("grade_conversion_rules", sa.Column("grading_structure", sa.String(120), nullable=True))
    op.add_column("grade_conversion_rules", sa.Column("framework_version", sa.String(64), nullable=True))
    op.add_column(
        "grade_conversion_rules",
        sa.Column("equivalency_classification", sa.String(40), nullable=False, server_default="reference_benchmark"),
    )
    op.add_column("grade_conversion_rules", sa.Column("source_url", sa.String(500), nullable=True))
    op.add_column("grade_conversion_rules", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("grade_conversion_rules", sa.Column("verified_by", sa.String(255), nullable=True))
    op.add_column("grade_conversion_rules", sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "grade_conversion_rules",
        sa.Column("freshness_status", sa.String(40), nullable=False, server_default="requires_manual_review"),
    )
    op.create_index("ix_grade_conversion_rules_freshness_status", "grade_conversion_rules", ["freshness_status"])

    # 3. CredentialRecognitionRule provenance, structure & freshness
    op.add_column("credential_recognition_rules", sa.Column("issuing_authority", sa.String(255), nullable=True))
    op.add_column(
        "credential_recognition_rules",
        sa.Column("education_level", sa.String(40), nullable=False, server_default="secondary"),
    )
    op.add_column("credential_recognition_rules", sa.Column("exam_structure", sa.String(200), nullable=True))
    op.add_column("credential_recognition_rules", sa.Column("framework_version", sa.String(64), nullable=True))
    op.add_column(
        "credential_recognition_rules",
        sa.Column("equivalency_classification", sa.String(40), nullable=False, server_default="official_equivalency"),
    )
    op.add_column("credential_recognition_rules", sa.Column("verified_by", sa.String(255), nullable=True))
    op.add_column(
        "credential_recognition_rules",
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "credential_recognition_rules",
        sa.Column("freshness_status", sa.String(40), nullable=False, server_default="requires_manual_review"),
    )
    op.create_index("ix_credential_recognition_rules_freshness_status", "credential_recognition_rules", ["freshness_status"])

    # 4. CountryQualification structure, authority & freshness
    op.add_column("country_qualifications", sa.Column("issuing_authority", sa.String(255), nullable=True))
    op.add_column(
        "country_qualifications",
        sa.Column("education_level", sa.String(40), nullable=False, server_default="secondary"),
    )
    op.add_column("country_qualifications", sa.Column("highest_grade", sa.String(60), nullable=True))
    op.add_column("country_qualifications", sa.Column("subject_structure", sa.Text(), nullable=True))
    op.add_column("country_qualifications", sa.Column("exam_structure", sa.Text(), nullable=True))
    op.add_column("country_qualifications", sa.Column("academic_duration", sa.String(60), nullable=True))
    op.add_column("country_qualifications", sa.Column("framework_version", sa.String(64), nullable=True))
    op.add_column(
        "country_qualifications",
        sa.Column("equivalency_classification", sa.String(40), nullable=False, server_default="reference_benchmark"),
    )
    op.add_column("country_qualifications", sa.Column("verified_by", sa.String(255), nullable=True))
    op.add_column("country_qualifications", sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "country_qualifications",
        sa.Column("freshness_status", sa.String(40), nullable=False, server_default="requires_manual_review"),
    )
    op.create_index("ix_country_qualifications_freshness_status", "country_qualifications", ["freshness_status"])


def downgrade() -> None:
    op.drop_index("ix_country_qualifications_freshness_status", table_name="country_qualifications")
    for col in (
        "freshness_status",
        "verification_expires_at",
        "verified_by",
        "equivalency_classification",
        "framework_version",
        "academic_duration",
        "exam_structure",
        "subject_structure",
        "highest_grade",
        "education_level",
        "issuing_authority",
    ):
        op.drop_column("country_qualifications", col)

    op.drop_index("ix_credential_recognition_rules_freshness_status", table_name="credential_recognition_rules")
    for col in (
        "freshness_status",
        "verification_expires_at",
        "verified_by",
        "equivalency_classification",
        "framework_version",
        "exam_structure",
        "education_level",
        "issuing_authority",
    ):
        op.drop_column("credential_recognition_rules", col)

    op.drop_index("ix_grade_conversion_rules_freshness_status", table_name="grade_conversion_rules")
    for col in (
        "freshness_status",
        "verification_expires_at",
        "verified_by",
        "verified_at",
        "source_url",
        "equivalency_classification",
        "framework_version",
        "grading_structure",
        "issuing_authority",
    ):
        op.drop_column("grade_conversion_rules", col)

    op.drop_index("ix_scholarship_programs_freshness_status", table_name="scholarship_programs")
    for col in (
        "conflict_notes",
        "claim_provenance",
        "requires_manual_review",
        "freshness_status",
        "verification_expires_at",
        "verified_by",
        "verification_method",
        "renewal_conditions",
        "max_funding_periods",
        "funding_duration_years",
        "covers_travel",
        "native_amount_max",
        "native_amount_min",
        "award_fixed_usd",
        "academic_year",
        "source_version",
        "source_type",
        "sponsoring_institution",
    ):
        op.drop_column("scholarship_programs", col)
