"""stage4_ai_and_notifications

Revision ID: 5c18a221f92e
Revises: 48c9037e912f
Create Date: 2026-10-22 11:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c18a221f92e"
down_revision: str | Sequence[str] | None = "48c9037e912f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. ai_explanations
    op.create_table(
        "ai_explanations",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("audit_runs.id"), nullable=False),
        sa.Column("finding_id", sa.String(length=64), nullable=True),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="success", nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_explanations_run_id", "ai_explanations", ["run_id"])
    op.create_index("ix_ai_explanations_finding_id", "ai_explanations", ["finding_id"])

    # 2. notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("admin_email", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=255), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_admin_email", "notifications", ["admin_email"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    # 3. notification_preferences
    op.create_table(
        "notification_preferences",
        sa.Column("admin_email", sa.String(length=255), primary_key=True, nullable=False),
        sa.Column("email_digest_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. email_digests_sent
    op.create_table(
        "email_digests_sent",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("admin_email", sa.String(length=255), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="sent", nullable=False),
    )
    op.create_index("ix_email_digests_sent_run_id", "email_digests_sent", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_email_digests_sent_run_id", table_name="email_digests_sent")
    op.drop_table("email_digests_sent")
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_is_read", table_name="notifications")
    op.drop_index("ix_notifications_admin_email", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_ai_explanations_finding_id", table_name="ai_explanations")
    op.drop_index("ix_ai_explanations_run_id", table_name="ai_explanations")
    op.drop_table("ai_explanations")
