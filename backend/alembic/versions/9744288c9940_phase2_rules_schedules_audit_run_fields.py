"""phase2_rules_schedules_audit_run_fields

Revision ID: 9744288c9940
Revises: 55d8eb8b1a95
Create Date: 2026-10-21 18:17:33.527180

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9744288c9940"
down_revision: str | Sequence[str] | None = "55d8eb8b1a95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new columns to audit_runs
    op.add_column("audit_runs", sa.Column("rule_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("audit_runs", sa.Column("trigger", sa.String(length=20), nullable=False, server_default="manual"))
    op.add_column("audit_runs", sa.Column("findings_snapshot", sa.JSON(), nullable=False, server_default="[]"))

    # 2. Create rule_configs table
    op.create_table(
        "rule_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index(op.f("ix_rule_configs_version"), "rule_configs", ["version"], unique=True)

    # 3. Create schedules table
    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="off"),
        sa.Column("time_of_day", sa.String(length=10), nullable=False, server_default="09:00"),
        sa.Column("day_of_week", sa.String(length=20), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=150), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("schedules")
    op.drop_index(op.f("ix_rule_configs_version"), table_name="rule_configs")
    op.drop_table("rule_configs")
    # For SQLite, batch drop columns if needed
    with op.batch_alter_table("audit_runs") as batch_op:
        batch_op.drop_column("findings_snapshot")
        batch_op.drop_column("trigger")
        batch_op.drop_column("rule_version")
