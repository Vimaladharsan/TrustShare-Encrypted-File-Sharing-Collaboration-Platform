"""The storage "plug": every part of the app saves and reads file bytes only through this interface.

Milestone 1: LocalStorage writes to a folder on the server.
Milestone 2: an encrypted S3 storage implements the same three methods, and nothing else changes.
"""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    async def save(self, key: str, source: Path) -> None:
        """Store the finished, validated temporary file under `key` (the source is consumed)."""

    def open(self, key: str) -> AsyncIterator[bytes]:
        """Stream the stored bytes back in chunks."""

    async def delete(self, key: str) -> None:
        """Remove the stored bytes (no error if already gone)."""
