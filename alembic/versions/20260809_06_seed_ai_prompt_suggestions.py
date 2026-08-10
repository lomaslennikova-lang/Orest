"""Seed the shared AI prompt suggestions used before the managed list.

Revision ID: 20260809_06
Revises: 20260809_05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert


revision: str = "20260809_06"
down_revision: Union[str, Sequence[str], None] = "20260809_05"
branch_labels = None
depends_on = None


PROMPT_SUGGESTIONS = [
    "Покажи найбільші витрати за {{month}}.",
    "Порівняй доходи й витрати за {{month}}.",
    "Які категорії витрат найбільше вплинули на бюджет у {{month}}?",
    "Чи були витрати вищими за доходи у {{month}}?",
    "Покажи динаміку витрат за {{month}}.",
]

prompt_suggestions = sa.table(
    "ai_prompt_suggestions",
    sa.column("content", sa.Text()),
)


def upgrade() -> None:
    op.get_bind().execute(
        insert(prompt_suggestions)
        .values([{"content": content} for content in PROMPT_SUGGESTIONS])
        .on_conflict_do_nothing(index_elements=["content"]),
    )


def downgrade() -> None:
    op.execute(
        prompt_suggestions.delete().where(
            prompt_suggestions.c.content.in_(PROMPT_SUGGESTIONS),
        )
    )
