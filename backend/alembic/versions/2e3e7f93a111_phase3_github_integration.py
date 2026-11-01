"""phase3_github_integration

Revision ID: 2e3e7f93a111
Revises: 9744288c9940
Create Date: 2026-10-21 19:49:15.770460

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e3e7f93a111"
down_revision: str | Sequence[str] | None = "9744288c9940"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create github_configs
    op.create_table(
        "github_configs",
        sa.Column("id", sa.Integer(), primary_key=True, default=1),
        sa.Column("org_name", sa.String(length=100), nullable=True),
        sa.Column("encrypted_token", sa.Text(), nullable=True),
        sa.Column("token_last4", sa.String(length=10), nullable=True),
        sa.Column("connected", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_before_audit", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 2. Create sync_runs
    op.create_table(
        "sync_runs",
        sa.Column("id", sa.String(length=50), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("repos_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("members_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("collaborators_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("assignments_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("assignments_updated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("assignments_revoked", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )

    # 3. Create github_identity_map
    op.create_table(
        "github_identity_map",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("login", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("mapped_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("mapped_by", sa.String(length=150), nullable=True),
    )
    op.create_index("ix_github_identity_map_login", "github_identity_map", ["login"], unique=True)

    # 4. Add columns to assignments table
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.add_column(sa.Column("origin", sa.String(length=20), server_default="sample", nullable=False))
        batch_op.add_column(sa.Column("external_status", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("github_login", sa.String(length=100), nullable=True))
        batch_op.create_index("ix_assignments_github_login", ["github_login"])


def downgrade() -> None:
    with op.batch_alter_table("assignments") as batch_op:
        batch_op.drop_index("ix_assignments_github_login")
        batch_op.drop_column("github_login")
        batch_op.drop_column("external_status")
        batch_op.drop_column("origin")

    op.drop_index("ix_github_identity_map_login", table_name="github_identity_map")
    op.drop_table("github_identity_map")
    op.drop_table("sync_runs")
    op.drop_table("github_configs")
