"""Master keys (KEKs) and envelope encryption of file keys (DEKs).

Every file is encrypted with its own random data key (DEK). The DEK is never stored as-is: it is
"wrapped" (encrypted) with a master key – a key-encryption key (KEK) – and only the wrapped form is
saved in PostgreSQL. Master keys are versioned so they can be rotated:

    MASTER_KEYS="1:<base64 32 bytes>,2:<base64 32 bytes>"     ACTIVE_MASTER_KEY_VERSION=2

New files are wrapped with the active version; older files keep working because each wrapped key
records the version that wrapped it. See docs/key-management.md.

This module is the only place that sees master keys. They never appear in logs or responses.
"""

import base64
import binascii
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

KEY_BYTES = 32  # AES-256
NONCE_BYTES = 12  # 96-bit nonce, the size AES-GCM is designed for


class KeyUnwrapError(Exception):
    """A wrapped key could not be opened (wrong master key, wrong file, or tampered data)."""


def parse_master_keys(raw: str) -> dict[int, bytes]:
    """'1:base64,2:base64' -> {1: key, 2: key}. Raises ValueError with a helpful message."""
    keys: dict[int, bytes] = {}
    for part in filter(None, (p.strip() for p in raw.split(","))):
        version_text, sep, encoded = part.partition(":")
        if not sep or not version_text.strip().isdigit():
            raise ValueError("MASTER_KEYS must look like '1:<base64 key>,2:<base64 key>'")
        try:
            key = base64.b64decode(encoded.strip(), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"MASTER_KEYS version {version_text}: not valid base64") from exc
        if len(key) != KEY_BYTES:
            raise ValueError(f"MASTER_KEYS version {version_text}: must be 32 bytes (256 bits)")
        keys[int(version_text)] = key
    if not keys:
        raise ValueError("MASTER_KEYS is empty – generate one (see .env.example)")
    return keys


def new_master_key() -> str:
    """A fresh base64 master key, for setup and rotation."""
    return base64.b64encode(os.urandom(KEY_BYTES)).decode()


class Keyring:
    def __init__(self, keys: dict[int, bytes], active_version: int) -> None:
        if active_version not in keys:
            raise ValueError("The active master key version is missing")
        self._keys = keys
        self.active_version = active_version

    def __repr__(self) -> str:  # never print key material, even by accident
        return f"Keyring(versions={sorted(self._keys)}, active={self.active_version})"

    @property
    def versions(self) -> list[int]:
        return sorted(self._keys)

    @staticmethod
    def _aad(file_id: str, version: int) -> bytes:
        # Binds the wrapped key to its file and master-key version: it can't be copied elsewhere.
        return f"trustshare:dek:{file_id}:v{version}".encode()

    def wrap(self, dek: bytes, file_id: str) -> tuple[bytes, int]:
        """Encrypt a file key with the active master key. Returns (nonce + ciphertext, version)."""
        version = self.active_version
        nonce = os.urandom(NONCE_BYTES)
        wrapped = AESGCM(self._keys[version]).encrypt(nonce, dek, self._aad(file_id, version))
        return nonce + wrapped, version

    def unwrap(self, wrapped: bytes, version: int, file_id: str) -> bytes:
        """Recover a file key. Raises KeyUnwrapError if anything doesn't match."""
        key = self._keys.get(version)
        if key is None:
            raise KeyUnwrapError(f"Master key version {version} is not configured")
        nonce, ciphertext = wrapped[:NONCE_BYTES], wrapped[NONCE_BYTES:]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, self._aad(file_id, version))
        except InvalidTag as exc:
            raise KeyUnwrapError("Wrapped key failed authentication") from exc


@lru_cache
def get_keyring() -> Keyring:
    settings = get_settings()
    keys = parse_master_keys(settings.master_keys.get_secret_value())
    return Keyring(keys, settings.active_master_key_version)
