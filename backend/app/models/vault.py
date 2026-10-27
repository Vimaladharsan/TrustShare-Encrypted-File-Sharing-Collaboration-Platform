import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Vault(Base):
    """A user's secure vault: only what is needed to CHECK the vault password.

    The vault key itself is never stored – it is derived from the password on every request
    (app/crypto/vault_crypto.py). Deleting the user deletes the vault row too.
    """

    __tablename__ = "vaults"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    salt: Mapped[bytes] = mapped_column(LargeBinary)  # random, for scrypt
    kdf_n: Mapped[int] = mapped_column(Integer)  # scrypt cost used for this vault
    verifier: Mapped[bytes] = mapped_column(LargeBinary)  # HMAC(vault key, label)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:  # never print salt/verifier
        return f"Vault(user_id={self.user_id!r})"
