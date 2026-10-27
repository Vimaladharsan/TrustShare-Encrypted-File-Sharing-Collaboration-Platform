"""vaults: per-user secure vault (password check data only)

Revision ID: e7a1b3c5d9f2
Revises: d5e9f3b7c1a2
Create Date: 2026-10-27 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7a1b3c5d9f2"
down_revision: str | Sequence[str] | None = "d5e9f3b7c1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vaults",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("salt", sa.LargeBinary(), nullable=False),
        sa.Column("kdf_n", sa.Integer(), nullable=False),
        # HMAC of the derived vault key – checks the password; the key itself is never stored
        sa.Column("verifier", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_vaults_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_vaults")),
    )


def downgrade() -> None:
    op.drop_table("vaults")
