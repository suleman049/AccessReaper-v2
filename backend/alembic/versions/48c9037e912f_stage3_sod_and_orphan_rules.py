"""stage3_sod_and_orphan_rules

Revision ID: 48c9037e912f
Revises: edaf100302b6
Create Date: 2026-10-22 11:20:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48c9037e912f"
down_revision: str | Sequence[str] | None = "edaf100302b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create sod_conflicts table
    sod_table = op.create_table(
        "sod_conflicts",
        sa.Column("id", sa.String(length=36), nullable=False, primary_key=True),
        sa.Column("pattern_a", sa.String(length=100), nullable=False),
        sa.Column("access_a", sa.String(length=20), server_default="Admin", nullable=False),
        sa.Column("pattern_b", sa.String(length=100), nullable=False),
        sa.Column("access_b", sa.String(length=20), server_default="Admin", nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("points", sa.Integer(), server_default="50", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Insert default SoD rule: *terraform* Admin + *payment* Admin
    now_utc = datetime.now(UTC)
    op.bulk_insert(
        sod_table,
        [
            {
                "id": "sod-default-infra-billing",
                "pattern_a": "*terraform*",
                "access_a": "Admin",
                "pattern_b": "*payment*",
                "access_b": "Admin",
                "description": "Separation of Duties: Infrastructure Admin and Payment/Billing Admin conflict",
                "points": 50,
                "enabled": True,
                "created_at": now_utc,
            }
        ],
    )

    # 3. Add is_archived column to resources
    op.add_column("resources", sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False))

    # 4. Add is_outside_collaborator column to assignments
    op.add_column(
        "assignments", sa.Column("is_outside_collaborator", sa.Boolean(), server_default=sa.false(), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("assignments", "is_outside_collaborator")
    op.drop_column("resources", "is_archived")
    op.drop_table("sod_conflicts")
