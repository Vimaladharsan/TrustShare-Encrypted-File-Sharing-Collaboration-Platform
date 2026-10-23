import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Share(Base):
    """Permission for someone else to open one file (Milestone 2).

    Two kinds, one table:
      - "link": anyone holding the secret link. Only the SHA-256 of the link token is stored, so
        a database leak doesn't reveal working links.
      - "user": a registered person (recipient_id) – shows up in their "Shared with Me".
    A share never grants more than `permission` ("view" = preview, "download" = preview + download)
    and stops working when revoked, expired, used up, or when the file / owner is no longer active.
    """

    __tablename__ = "shares"
    __table_args__ = (
        CheckConstraint("share_type IN ('link', 'user')", name="share_type"),
        CheckConstraint("permission IN ('view', 'download')", name="permission"),
        CheckConstraint("(share_type = 'link') = (token_hash IS NOT NULL)", name="link_has_token"),
        CheckConstraint(
            "(share_type = 'user') = (recipient_id IS NOT NULL)", name="user_has_recipient"
        ),
        CheckConstraint("max_downloads IS NULL OR max_downloads > 0", name="max_downloads"),
        # One active (not revoked) direct share per person and file.
        Index(
            "uq_shares_active_recipient",
            "file_id",
            "recipient_id",
            unique=True,
            postgresql_where=text("recipient_id IS NOT NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id: Mapped[str] = mapped_column(String(24), index=True)  # MongoDB ObjectId (hex)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    share_type: Mapped[str] = mapped_column(String(10))
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    permission: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_downloads: Mapped[int | None] = mapped_column(Integer)
    download_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # never print the token hash
        return f"Share(id={self.id}, type={self.share_type!r}, file_id={self.file_id!r})"
