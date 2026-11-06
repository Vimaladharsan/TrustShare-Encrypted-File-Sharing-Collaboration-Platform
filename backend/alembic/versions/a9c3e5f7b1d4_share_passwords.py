"""shares: optional password for share links (bcrypt hash)

Revision ID: a9c3e5f7b1d4
Revises: f8b2c4d6e0a1
Create Date: 2026-11-06 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9c3e5f7b1d4"
down_revision: str | Sequence[str] | None = "f8b2c4d6e0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("shares", sa.Column("password_hash", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("shares", "password_hash")
