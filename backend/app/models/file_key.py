import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FileKey(Base):
    """A file's encryption key – stored ONLY in wrapped (encrypted) form.

    The file bytes are in object storage, the file's metadata in MongoDB, and this wrapped key in
    PostgreSQL: none of them alone reveals the file. See docs/key-management.md.
    """

    __tablename__ = "file_keys"

    file_id: Mapped[str] = mapped_column(String(24), primary_key=True)  # MongoDB ObjectId (hex)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary)  # nonce + AES-GCM(master key, DEK)
    # Which master key (KEK) version wrapped it – needed for key rotation.
    key_version: Mapped[int] = mapped_column(SmallInteger, index=True)
    algorithm: Mapped[str] = mapped_column(String(32), default="AES-256-GCM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # keep key material out of logs and error messages
        return f"FileKey(file_id={self.file_id!r}, key_version={self.key_version})"
