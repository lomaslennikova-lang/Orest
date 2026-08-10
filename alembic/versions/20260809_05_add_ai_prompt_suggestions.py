"""Add shared AI prompt suggestions.

Revision ID: 20260809_05
Revises: 20260804_04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260809_05"
down_revision: Union[str, Sequence[str], None] = "20260804_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_prompt_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content"),
    )


def downgrade() -> None:
    op.drop_table("ai_prompt_suggestions")
