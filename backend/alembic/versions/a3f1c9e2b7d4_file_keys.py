"""file_keys: wrapped per-file encryption keys (Milestone 2)

Revision ID: a3f1c9e2b7d4
Revises: 80c68abe37ea
Create Date: 2026-10-23 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f1c9e2b7d4"
down_revision: str | Sequence[str] | None = "80c68abe37ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_keys",
        # MongoDB ObjectId of the file (24 hex characters)
        sa.Column("file_id", sa.String(length=24), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        # nonce + AES-256-GCM(master key, file key) + tag – never the raw key
        sa.Column("wrapped_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_file_keys_owner_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("file_id", name=op.f("pk_file_keys")),
    )
    op.create_index(op.f("ix_file_keys_owner_id"), "file_keys", ["owner_id"])
    op.create_index(op.f("ix_file_keys_key_version"), "file_keys", ["key_version"])


def downgrade() -> None:
    op.drop_index(op.f("ix_file_keys_key_version"), table_name="file_keys")
    op.drop_index(op.f("ix_file_keys_owner_id"), table_name="file_keys")
    op.drop_table("file_keys")
