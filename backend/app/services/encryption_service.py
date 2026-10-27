"""File encryption with AES-256-GCM – one random key per file, processed in chunks.

Why chunks: a file is encrypted 1 MiB at a time, so memory use stays small and decryption can stream
to the user while every piece is still verified. Each chunk is authenticated on its own:

    object = header | chunk_0 | chunk_1 | … | chunk_n
    header = b"TSE1" | version (1 byte) | chunk size (4 bytes) | nonce prefix (7 random bytes)
    chunk  = AES-256-GCM ciphertext + 16-byte tag

    nonce(i) = nonce prefix (7) | i (4 bytes) | 1 if last chunk else 0 (1 byte)
               → 12 bytes, never reused for the same key
    AAD(i)   = "trustshare:file:<file id>:<i>"
               → binds each chunk to its file and position

This detects every kind of tampering: changed bytes (tag fails), chunks swapped or reordered
(wrong position in AAD/nonce), chunks taken from another file (wrong file id), and a file cut
short (the last chunk must carry the "last" flag). Nothing is released to the caller before its
tag has been checked.

The file key (DEK) is wrapped by the Keyring (envelope encryption) – see docs/key-management.md.
Callers never see master keys; raw DEKs only live in memory during a request.
"""

import os
import struct
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.crypto import vault_crypto
from app.crypto.keyring import Keyring, KeyUnwrapError, get_keyring

ALGORITHM = "AES-256-GCM"
FORMAT = "TSE1-chunked"
MAGIC = b"TSE1"
FORMAT_VERSION = 1
CHUNK_SIZE = 1024 * 1024  # 1 MiB of plaintext per chunk
TAG_BYTES = 16
PREFIX_BYTES = 7
HEADER = struct.Struct(">4sBI7s")  # magic, version, chunk size, nonce prefix → 16 bytes
MAX_CHUNK_SIZE = 16 * 1024 * 1024


class DecryptionError(Exception):
    """The encrypted data could not be verified – wrong key, corrupted or tampered with."""


@dataclass(frozen=True)
class EncryptedKey:
    """What gets stored in PostgreSQL file_keys – the DEK only in wrapped form."""

    wrapped_key: bytes
    key_version: int


def generate_dek() -> bytes:
    """A fresh random 256-bit file key from the operating system's secure random generator."""
    return AESGCM.generate_key(bit_length=256)


def _nonce(prefix: bytes, index: int, last: bool) -> bytes:
    return prefix + struct.pack(">IB", index, 1 if last else 0)


def _aad(file_id: str, index: int) -> bytes:
    return f"trustshare:file:{file_id}:{index}".encode()


# ---------- encryption ----------


def encrypt_file(
    dek: bytes, file_id: str, src: BinaryIO, dst: BinaryIO, chunk_size: int = CHUNK_SIZE
) -> int:
    """Encrypt everything from src into dst. Returns the number of bytes written."""
    if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError("Invalid chunk size")
    aes = AESGCM(dek)
    prefix = os.urandom(PREFIX_BYTES)  # random per encryption, so the same file never repeats
    written = dst.write(HEADER.pack(MAGIC, FORMAT_VERSION, chunk_size, prefix))

    index = 0
    current = src.read(chunk_size)
    while True:
        following = src.read(chunk_size) if len(current) == chunk_size else b""
        last = not following  # look one chunk ahead to know which chunk is the final one
        sealed = aes.encrypt(_nonce(prefix, index, last), current, _aad(file_id, index))
        written += dst.write(sealed)
        if last:
            return written
        current, index = following, index + 1


def encrypted_size(plain_size: int, chunk_size: int = CHUNK_SIZE) -> int:
    """Size of the encrypted object for a plaintext of plain_size bytes."""
    chunks = max(1, -(-plain_size // chunk_size))  # an empty file still has one (empty) chunk
    return HEADER.size + plain_size + chunks * TAG_BYTES


# ---------- decryption ----------


class _ChunkDecryptor:
    """Turns arbitrary pieces of ciphertext into verified plaintext chunks."""

    def __init__(self, dek: bytes, file_id: str) -> None:
        self._aes = AESGCM(dek)
        self._file_id = file_id
        self._buffer = bytearray()
        self._header_read = False
        self._prefix = b""
        self._sealed_size = 0
        self._index = 0

    def _read_header(self) -> None:
        magic, version, chunk_size, prefix = HEADER.unpack(bytes(self._buffer[: HEADER.size]))
        if magic != MAGIC or version != FORMAT_VERSION or not 1 <= chunk_size <= MAX_CHUNK_SIZE:
            raise DecryptionError("Not a TrustShare encrypted object")
        del self._buffer[: HEADER.size]
        self._prefix, self._sealed_size = prefix, chunk_size + TAG_BYTES
        self._header_read = True

    def _open(self, sealed: bytes, last: bool) -> bytes:
        try:
            plain = self._aes.decrypt(
                _nonce(self._prefix, self._index, last), sealed, _aad(self._file_id, self._index)
            )
        except InvalidTag as exc:
            raise DecryptionError("Integrity check failed – the file was altered") from exc
        self._index += 1
        return plain

    def feed(self, piece: bytes) -> Iterator[bytes]:
        self._buffer += piece
        if not self._header_read:
            if len(self._buffer) < HEADER.size:
                return
            self._read_header()
        # Keep one full chunk back: it might be the last one (which uses a different nonce).
        while len(self._buffer) > self._sealed_size:
            sealed = bytes(self._buffer[: self._sealed_size])
            del self._buffer[: self._sealed_size]
            yield self._open(sealed, last=False)

    def finish(self) -> bytes:
        if not self._header_read or len(self._buffer) < TAG_BYTES:
            raise DecryptionError("Encrypted object is truncated")
        return self._open(bytes(self._buffer), last=True)


async def decrypt_stream(
    dek: bytes, file_id: str, pieces: AsyncIterator[bytes]
) -> AsyncIterator[bytes]:
    """Decrypt an encrypted object as it streams in, yielding only verified plaintext."""
    decryptor = _ChunkDecryptor(dek, file_id)
    async for piece in pieces:
        for plain in decryptor.feed(piece):
            yield plain
    yield decryptor.finish()


def decrypt_bytes(dek: bytes, file_id: str, data: bytes) -> bytes:
    """Decrypt a whole encrypted object held in memory (used by tests and small files)."""
    decryptor = _ChunkDecryptor(dek, file_id)
    return b"".join([*decryptor.feed(data), decryptor.finish()])


# ---------- key envelope ----------


class EncryptionService:
    """The only entry point the rest of the backend uses for keys."""

    def __init__(self, keyring: Keyring | None = None) -> None:
        self.keyring = keyring or get_keyring()

    def new_file_key(
        self, file_id: str, vault_key: bytes | None = None
    ) -> tuple[bytes, EncryptedKey]:
        """A fresh DEK for a file, plus its wrapped form to store. With a vault key the DEK is
        first sealed with it (inner lock), then wrapped by the master key as usual."""
        dek = generate_dek()
        return dek, self.wrap_file_key(file_id, dek, vault_key)

    def wrap_file_key(
        self, file_id: str, dek: bytes, vault_key: bytes | None = None
    ) -> EncryptedKey:
        inner = vault_crypto.seal_key(vault_key, dek, file_id) if vault_key else dek
        wrapped, version = self.keyring.wrap(inner, file_id)
        return EncryptedKey(wrapped, version)

    def open_file_key(
        self, file_id: str, stored: EncryptedKey, vault_key: bytes | None = None
    ) -> bytes:
        """Unwrap a stored DEK. Raises DecryptionError if the wrapped key doesn't verify."""
        try:
            inner = self.keyring.unwrap(stored.wrapped_key, stored.key_version, file_id)
            return vault_crypto.open_key(vault_key, inner, file_id) if vault_key else inner
        except (KeyUnwrapError, vault_crypto.VaultKeyError) as exc:
            raise DecryptionError(str(exc)) from exc

    def rekey(
        self,
        file_id: str,
        stored: EncryptedKey,
        old_vault_key: bytes | None,
        new_vault_key: bytes | None,
    ) -> EncryptedKey:
        """Move a file key into / out of a vault, or to a new vault password. Only the key is
        re-locked - the file's encrypted bytes don't change."""
        dek = self.open_file_key(file_id, stored, old_vault_key)
        return self.wrap_file_key(file_id, dek, new_vault_key)

    def rewrap(self, file_id: str, stored: EncryptedKey) -> EncryptedKey:
        """Key rotation: re-wrap a DEK with the active master key (the file itself is untouched)."""
        dek = self.open_file_key(file_id, stored)
        wrapped, version = self.keyring.wrap(dek, file_id)
        return EncryptedKey(wrapped, version)
