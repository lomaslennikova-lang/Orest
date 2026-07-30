"""Persist idempotent results of executed AI actions.

Revision ID: 20260730_03
Revises: 20260730_02
Create Date: 2026-07-30 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_03"
down_revision: Union[str, Sequence[str], None] = "20260730_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_pending_actions",
        sa.Column("execution_result", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_pending_actions", "execution_result")
