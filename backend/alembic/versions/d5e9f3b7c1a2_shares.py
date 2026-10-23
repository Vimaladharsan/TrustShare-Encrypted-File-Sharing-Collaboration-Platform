"""shares: secure share links and direct shares (Milestone 2)

Revision ID: d5e9f3b7c1a2
Revises: c4d8e2a6b9f0
Create Date: 2026-10-23 19:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e9f3b7c1a2"
down_revision: str | Sequence[str] | None = "c4d8e2a6b9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", sa.String(length=24), nullable=False),  # MongoDB file id
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("share_type", sa.String(length=10), nullable=False),  # link | user
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=True),
        # SHA-256 of the link token – the token itself is shown once and never stored
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("permission", sa.String(length=10), nullable=False),  # view | download
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_downloads", sa.Integer(), nullable=True),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.CheckConstraint("share_type IN ('link', 'user')", name=op.f("ck_shares_share_type")),
        sa.CheckConstraint("permission IN ('view', 'download')", name=op.f("ck_shares_permission")),
        sa.CheckConstraint(
            "(share_type = 'link') = (token_hash IS NOT NULL)", name=op.f("ck_shares_link_has_token")
        ),
        sa.CheckConstraint(
            "(share_type = 'user') = (recipient_id IS NOT NULL)",
            name=op.f("ck_shares_user_has_recipient"),
        ),
        sa.CheckConstraint(
            "max_downloads IS NULL OR max_downloads > 0", name=op.f("ck_shares_max_downloads")
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], name=op.f("fk_shares_owner_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name=op.f("fk_shares_recipient_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shares")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_shares_token_hash")),
    )
    op.create_index(op.f("ix_shares_file_id"), "shares", ["file_id"])
    op.create_index(op.f("ix_shares_owner_id"), "shares", ["owner_id"])
    op.create_index(op.f("ix_shares_recipient_id"), "shares", ["recipient_id"])
    op.create_index(
        "uq_shares_active_recipient",
        "shares",
        ["file_id", "recipient_id"],
        unique=True,
        postgresql_where=sa.text("recipient_id IS NOT NULL AND revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_shares_active_recipient", table_name="shares")
    op.drop_index(op.f("ix_shares_recipient_id"), table_name="shares")
    op.drop_index(op.f("ix_shares_owner_id"), table_name="shares")
    op.drop_index(op.f("ix_shares_file_id"), table_name="shares")
    op.drop_table("shares")
