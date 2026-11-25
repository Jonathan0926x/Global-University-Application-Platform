"""m7_2_route_health_and_verification_infrastructure

Revision ID: c3e8a4f19d72
Revises: 9b4f21c8e310
Create Date: 2026-11-24 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3e8a4f19d72"
down_revision: Union[str, None] = "9b4f21c8e310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Verification expiration
    op.add_column(
        "application_routes",
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Link-health check tracking
    op.add_column(
        "application_routes",
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "application_routes",
        sa.Column("last_health_check_status", sa.String(20), nullable=True),
    )
    op.add_column(
        "application_routes",
        sa.Column("last_health_check_http_code", sa.Integer(), nullable=True),
    )

    # Pathway verification
    op.add_column(
        "application_routes",
        sa.Column("pathway_verified", sa.Boolean(), nullable=True),
    )

    # Redirect destination tracking
    op.add_column(
        "application_routes",
        sa.Column("final_redirect_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "application_routes",
        sa.Column("redirect_chain_length", sa.Integer(), nullable=True),
    )

    # Set verification_expires_at for existing verified routes (180 days from verified_at)
    op.execute(
        """
        UPDATE application_routes
        SET verification_expires_at = verified_at + INTERVAL '180 days'
        WHERE verification_status = 'verified' AND verified_at IS NOT NULL
        """
    )

    # Mark curated flagship/centralized routes (verification_method IS NULL and verified) as pathway_verified = true
    op.execute(
        """
        UPDATE application_routes
        SET pathway_verified = TRUE
        WHERE verification_status = 'verified' AND verification_method IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("application_routes", "redirect_chain_length")
    op.drop_column("application_routes", "final_redirect_url")
    op.drop_column("application_routes", "pathway_verified")
    op.drop_column("application_routes", "last_health_check_http_code")
    op.drop_column("application_routes", "last_health_check_status")
    op.drop_column("application_routes", "last_health_check_at")
    op.drop_column("application_routes", "verification_expires_at")
