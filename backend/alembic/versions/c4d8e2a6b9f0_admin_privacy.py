"""admin privacy: drop file:read_all, add user:delete_inactive (Milestone 2)

Admins no longer see other users' files. Their extra power is deleting accounts that have been
inactive for INACTIVE_ACCOUNT_DAYS (default 30), together with all of the account's files.

Revision ID: c4d8e2a6b9f0
Revises: a3f1c9e2b7d4
Create Date: 2026-10-23 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e2a6b9f0"
down_revision: str | Sequence[str] | None = "a3f1c9e2b7d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_ROLE_ID = 1
READ_ALL_ID = 6
DELETE_INACTIVE_ID = 11


def upgrade() -> None:
    # Revoke "view files of every user" from every role, then remove the permission itself.
    op.execute(sa.text(f"DELETE FROM role_permissions WHERE permission_id = {READ_ALL_ID}"))
    op.execute(sa.text(f"DELETE FROM permissions WHERE id = {READ_ALL_ID}"))
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description) VALUES "
            f"({DELETE_INACTIVE_ID}, 'user:delete_inactive', "
            "'Delete accounts inactive for 30+ days, with all their files')"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            f"VALUES ({ADMIN_ROLE_ID}, {DELETE_INACTIVE_ID})"
        )
    )


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM role_permissions WHERE permission_id = {DELETE_INACTIVE_ID}"))
    op.execute(sa.text(f"DELETE FROM permissions WHERE id = {DELETE_INACTIVE_ID}"))
    op.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description) "
            f"VALUES ({READ_ALL_ID}, 'file:read_all', 'View files of every user')"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            f"VALUES ({ADMIN_ROLE_ID}, {READ_ALL_ID})"
        )
    )
