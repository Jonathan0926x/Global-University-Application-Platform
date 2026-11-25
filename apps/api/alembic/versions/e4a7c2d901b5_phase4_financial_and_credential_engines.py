"""phase4_financial_and_credential_engines

Revision ID: e4a7c2d901b5
Revises: d8f2a9b41e03
Create Date: 2026-11-25 01:00:00.000000

Adds structured financial-aid/scholarship eligibility schema and
international credential/grade equivalency rule tables for Phase 4.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4a7c2d901b5"
down_revision: Union[str, None] = "d8f2a9b41e03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend scholarship_programs with deterministic award, coverage, and criteria columns
    op.add_column("scholarship_programs", sa.Column("provider_type", sa.String(40), nullable=False, server_default="university"))
    op.add_column("scholarship_programs", sa.Column("award_type", sa.String(40), nullable=False, server_default="fixed_amount"))
    op.add_column("scholarship_programs", sa.Column("award_amount_min_usd", sa.Numeric(12, 2), nullable=True))
    op.add_column("scholarship_programs", sa.Column("award_amount_max_usd", sa.Numeric(12, 2), nullable=True))
    op.add_column("scholarship_programs", sa.Column("award_currency", sa.CHAR(3), nullable=False, server_default="USD"))
    op.add_column("scholarship_programs", sa.Column("is_renewable", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("scholarship_programs", sa.Column("covers_tuition", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("scholarship_programs", sa.Column("covers_fees", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("covers_housing", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("covers_meals", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("covers_health_insurance", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("provides_living_stipend", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("application_deadline_date", sa.Date(), nullable=True))
    op.add_column("scholarship_programs", sa.Column("is_deadline_rolling", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("min_gpa_4", sa.Numeric(4, 2), nullable=True))
    op.add_column("scholarship_programs", sa.Column("requires_financial_need", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("scholarship_programs", sa.Column("eligible_citizenships", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("scholarship_programs", sa.Column("eligible_residency_states", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("scholarship_programs", sa.Column("eligible_destination_countries", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("scholarship_programs", sa.Column("degree_levels", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[\"bachelors\"]'::jsonb")))
    op.add_column("scholarship_programs", sa.Column("is_guaranteed_statutory", sa.Boolean(), nullable=False, server_default=sa.text("false")))

    # 2. Structured scholarship_eligibility_rules table
    op.create_table(
        "scholarship_eligibility_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scholarship_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scholarship_programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_dimension", sa.String(50), nullable=False),
        sa.Column("rule_operator", sa.String(30), nullable=False),
        sa.Column("rule_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("human_label", sa.String(255), nullable=False),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_scholarship_elig_rules_scholarship_id", "scholarship_eligibility_rules", ["scholarship_id"])
    op.create_index("ix_scholarship_elig_rules_dimension", "scholarship_eligibility_rules", ["rule_dimension"])

    # 3. Grade conversion rules (international grading benchmarks)
    op.create_table(
        "grade_conversion_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_country_code", sa.String(2), nullable=False),
        sa.Column("grading_system_key", sa.String(60), nullable=False),
        sa.Column("scale_name", sa.String(160), nullable=False),
        sa.Column("academic_level", sa.String(30), nullable=False, server_default="secondary"),
        sa.Column("band_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_numeric", sa.Numeric(7, 2), nullable=True),
        sa.Column("max_numeric", sa.Numeric(7, 2), nullable=True),
        sa.Column("raw_grade_label", sa.String(40), nullable=True),
        sa.Column("classification_label", sa.String(120), nullable=False),
        sa.Column("target_letter_equivalent", sa.String(20), nullable=False),
        sa.Column("target_gpa_low", sa.Numeric(4, 2), nullable=False),
        sa.Column("target_gpa_high", sa.Numeric(4, 2), nullable=False),
        sa.Column("target_gpa_point", sa.Numeric(4, 2), nullable=False),
        sa.Column("is_passing", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_inverted_scale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("methodology", sa.String(50), nullable=False, server_default="distribution_percentile"),
        sa.Column("methodology_citation", sa.Text(), nullable=False),
        sa.Column("percentile_note", sa.Text(), nullable=True),
        sa.Column("confidence_level", sa.String(20), nullable=False, server_default="high"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_grade_conv_country_system", "grade_conversion_rules", ["source_country_code", "grading_system_key"])

    # 4. Credential recognition & gatekeeping rules (source country -> destination country)
    op.create_table(
        "credential_recognition_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_country_code", sa.String(2), nullable=False),
        sa.Column("destination_country_code", sa.String(2), nullable=False),
        sa.Column("source_credential_name", sa.String(255), nullable=False),
        sa.Column("is_directly_recognized", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_external_evaluation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("accepted_evaluation_agencies", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("requires_official_translation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("translation_requirements", sa.Text(), nullable=True),
        sa.Column("requires_apostille_or_legalization", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_direct_institutional_dispatch", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("english_waiver_policy", sa.Text(), nullable=True),
        sa.Column("pathway_notes", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="verified"),
    )
    op.create_index("ix_cred_rec_src_dest", "credential_recognition_rules", ["source_country_code", "destination_country_code"])


def downgrade() -> None:
    op.drop_index("ix_cred_rec_src_dest", table_name="credential_recognition_rules")
    op.drop_table("credential_recognition_rules")

    op.drop_index("ix_grade_conv_country_system", table_name="grade_conversion_rules")
    op.drop_table("grade_conversion_rules")

    op.drop_index("ix_scholarship_elig_rules_dimension", table_name="scholarship_eligibility_rules")
    op.drop_index("ix_scholarship_elig_rules_scholarship_id", table_name="scholarship_eligibility_rules")
    op.drop_table("scholarship_eligibility_rules")

    for col in (
        "is_guaranteed_statutory",
        "degree_levels",
        "eligible_destination_countries",
        "eligible_residency_states",
        "eligible_citizenships",
        "requires_financial_need",
        "min_gpa_4",
        "is_deadline_rolling",
        "application_deadline_date",
        "provides_living_stipend",
        "covers_health_insurance",
        "covers_meals",
        "covers_housing",
        "covers_fees",
        "covers_tuition",
        "is_renewable",
        "award_currency",
        "award_amount_max_usd",
        "award_amount_min_usd",
        "award_type",
        "provider_type",
    ):
        op.drop_column("scholarship_programs", col)
