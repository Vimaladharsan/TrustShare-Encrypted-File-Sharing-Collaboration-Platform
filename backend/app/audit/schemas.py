from datetime import datetime

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    log_id: str
    seq: int
    user_id: str | None
    username: str | None
    activity_type: str
    action: str
    file_id: str | None
    description: str
    status: str
    ip_address: str | None
    created_at: datetime
    imported: bool = False  # brought in from the history recorded before the audit log existed
    hash: str


class AuditLogPage(BaseModel):
    items: list[AuditLogEntry]
    total: int


class AuditVerification(BaseModel):
    """Result of re-computing every hash in the chain."""

    valid: bool
    checked: int
    last_seq: int | None
    broken_at_seq: int | None = None
    reason: str | None = None
