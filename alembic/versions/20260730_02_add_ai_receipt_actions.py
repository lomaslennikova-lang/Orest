"""Add receipt attachments and pending AI actions.

Revision ID: 20260730_02
Revises: 20260726_01
Create Date: 2026-07-30 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_02"
down_revision: Union[str, Sequence[str], None] = "20260726_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_receipt_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "media_type IN ('application/pdf', 'image/png', 'image/jpeg')",
            name="ck_ai_receipt_attachments_media_type",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_ai_receipt_attachments_owner_user_id",
        "ai_receipt_attachments",
        ["owner_user_id"],
        unique=False,
    )

    op.create_table(
        "ai_pending_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "action_type",
            sa.String(length=100),
            server_default="create_expense_transactions",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("draft_payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "action_type = 'create_expense_transactions'",
            name="ck_ai_pending_actions_action_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'needs_clarification', 'pending_confirmation', 'confirmed', "
            "'executed', 'cancelled', 'expired', 'failed'"
            ")",
            name="ck_ai_pending_actions_status",
        ),
        sa.ForeignKeyConstraint(
            ["attachment_id"],
            ["ai_receipt_attachments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_ai_pending_actions_attachment_id",
        "ai_pending_actions",
        ["attachment_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_pending_actions_conversation_id",
        "ai_pending_actions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_pending_actions_owner_user_id",
        "ai_pending_actions",
        ["owner_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_pending_actions_owner_user_id", table_name="ai_pending_actions")
    op.drop_index("ix_ai_pending_actions_conversation_id", table_name="ai_pending_actions")
    op.drop_index("ix_ai_pending_actions_attachment_id", table_name="ai_pending_actions")
    op.drop_table("ai_pending_actions")
    op.drop_index(
        "ix_ai_receipt_attachments_owner_user_id",
        table_name="ai_receipt_attachments",
    )
    op.drop_table("ai_receipt_attachments")
