"""stage1_automation_fields

Revision ID: 37a684375ac9
Revises: 2e3e7f93a111
Create Date: 2026-10-22 10:27:48.485281

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "37a684375ac9"
down_revision: str | Sequence[str] | None = "2e3e7f93a111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("pause_note", sa.Text(), nullable=True))
    op.add_column("audit_runs", sa.Column("degraded_reason", sa.Text(), nullable=True))
    # Enable automatic 24-hour audit schedule by default at 02:00 PKT
    op.execute("UPDATE schedules SET enabled = 1, frequency = 'daily', time_of_day = '02:00' WHERE id = 1")


def downgrade() -> None:
    op.drop_column("audit_runs", "degraded_reason")
    op.drop_column("schedules", "pause_note")
