"""shares: reminder_sent_at + expiry_recorded_at (Milestone 3 notifications)

Revision ID: f8b2c4d6e0a1
Revises: e7a1b3c5d9f2
Create Date: 2026-11-02 18:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8b2c4d6e0a1"
down_revision: str | Sequence[str] | None = "e7a1b3c5d9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shares", sa.Column("reminder_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "shares", sa.Column("expiry_recorded_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("shares", "expiry_recorded_at")
    op.drop_column("shares", "reminder_sent_at")
