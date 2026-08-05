"""Add Google Drive receipt metadata.

Revision ID: 20260804_04
Revises: 20260730_03
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260804_04"
down_revision: Union[str, Sequence[str], None] = "20260730_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_receipt_attachments",
        sa.Column("storage_backend", sa.String(length=20), server_default="local", nullable=False),
    )
    op.add_column(
        "ai_receipt_attachments", sa.Column("drive_file_id", sa.String(length=255), nullable=True),
    )
    op.create_unique_constraint(
        "uq_ai_receipt_attachments_drive_file_id",
        "ai_receipt_attachments", ["drive_file_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_ai_receipt_attachments_drive_file_id", "ai_receipt_attachments", type_="unique")
    op.drop_column("ai_receipt_attachments", "drive_file_id")
    op.drop_column("ai_receipt_attachments", "storage_backend")
