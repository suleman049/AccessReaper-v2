"""stage2_identity_and_classification

Revision ID: edaf100302b6
Revises: 37a684375ac9
Create Date: 2026-10-22 10:47:52.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "edaf100302b6"
down_revision: str | Sequence[str] | None = "37a684375ac9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "github_identity_map", sa.Column("account_type", sa.String(length=20), server_default="user", nullable=False)
    )
    op.add_column("github_identity_map", sa.Column("note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("github_identity_map", "note")
    op.drop_column("github_identity_map", "account_type")
