from datetime import datetime

from pydantic import BaseModel, Field


class VaultStatus(BaseModel):
    available: bool  # the role may store files (Guests are read-only, so no vault)
    exists: bool
    file_count: int
    size_bytes: int
    locked_minutes: int  # > 0 while the vault is locked after wrong passwords
    created_at: datetime | None


class VaultCreate(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class VaultFile(BaseModel):
    id: str
    name: str  # decrypted for this response only – stored encrypted
    extension: str
    category: str
    size_bytes: int
    can_preview: bool
    created_at: datetime


class VaultFileList(BaseModel):
    items: list[VaultFile]


class VaultRename(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class VaultPasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class VaultReset(BaseModel):
    """Forgot the vault password: delete the vault and everything in it."""

    account_password: str | None = Field(None, max_length=128)  # accounts that have a password
    confirm: str = Field(max_length=320)  # "DELETE" (Google-only accounts: their email)
