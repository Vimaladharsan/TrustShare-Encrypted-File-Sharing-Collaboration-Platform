"""Vault cryptography: a key made from the user's vault password protects their vault files.

    vault key = scrypt(vault password, random salt)          – never stored anywhere
    verifier  = HMAC-SHA256(vault key, "trustshare-vault")   – stored, to check the password

A vault file's DEK gets two locks (see docs/key-management.md, "Secure vault"):

    inner = AES-256-GCM(vault key, DEK, AAD = "trustshare:vault:<file id>")
    file_keys.wrapped_key = Keyring.wrap(inner)              – the normal master-key envelope

So opening a vault file needs BOTH the server's master key and the user's vault password: someone
with the database and the master keys still can't read it. The vault file's name is sealed with
the vault key too. Forgetting the vault password means the files can't be recovered – by design.
"""

import base64
import hashlib
import hmac
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

SALT_BYTES = 16
NONCE_BYTES = 12
KDF_N = 2**15  # scrypt cost: ~32 MB of memory per guess – makes brute force expensive
KDF_R, KDF_P = 8, 1
VERIFY_LABEL = b"trustshare-vault"


class VaultKeyError(Exception):
    """Something sealed with a vault key could not be opened (wrong key or tampered)."""


def new_salt() -> bytes:
    return os.urandom(SALT_BYTES)


def derive_key(password: str, salt: bytes, n: int = KDF_N) -> bytes:
    """The 256-bit vault key for a password (slow on purpose)."""
    return Scrypt(salt=salt, length=32, n=n, r=KDF_R, p=KDF_P).derive(password.encode())


def verifier(vault_key: bytes) -> bytes:
    """Stored to check a password later; reveals nothing about the key itself."""
    return hmac.new(vault_key, VERIFY_LABEL, hashlib.sha256).digest()


def matches(vault_key: bytes, stored_verifier: bytes) -> bool:
    return hmac.compare_digest(verifier(vault_key), stored_verifier)


def seal_key(vault_key: bytes, dek: bytes, file_id: str) -> bytes:
    """Inner lock on a file key: nonce + AES-GCM(vault key, DEK), bound to the file id."""
    nonce = os.urandom(NONCE_BYTES)
    return nonce + AESGCM(vault_key).encrypt(nonce, dek, f"trustshare:vault:{file_id}".encode())


def open_key(vault_key: bytes, sealed: bytes, file_id: str) -> bytes:
    nonce, ciphertext = sealed[:NONCE_BYTES], sealed[NONCE_BYTES:]
    try:
        return AESGCM(vault_key).decrypt(nonce, ciphertext, f"trustshare:vault:{file_id}".encode())
    except InvalidTag as exc:
        raise VaultKeyError("Vault key does not match") from exc


def seal_name(vault_key: bytes, name: str, file_id: str) -> str:
    """The file name, encrypted – stored in MongoDB instead of the real name."""
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(vault_key).encrypt(
        nonce, name.encode(), f"trustshare:vault-name:{file_id}".encode()
    )
    return base64.b64encode(nonce + sealed).decode()


def open_name(vault_key: bytes, sealed: str, file_id: str) -> str:
    raw = base64.b64decode(sealed)
    try:
        return (
            AESGCM(vault_key)
            .decrypt(
                raw[:NONCE_BYTES], raw[NONCE_BYTES:], f"trustshare:vault-name:{file_id}".encode()
            )
            .decode()
        )
    except InvalidTag as exc:
        raise VaultKeyError("Vault key does not match") from exc
