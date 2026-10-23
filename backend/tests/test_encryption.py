"""AES-256-GCM file encryption and envelope keys (Milestone 2, Phase 2).

These are pure unit tests – no database or storage needed.
"""

import asyncio
import base64
import io
import os

import pytest

from app.crypto.keyring import Keyring, KeyUnwrapError, parse_master_keys
from app.services.encryption_service import (
    HEADER,
    TAG_BYTES,
    DecryptionError,
    EncryptionService,
    decrypt_bytes,
    decrypt_stream,
    encrypt_file,
    encrypted_size,
    generate_dek,
)

FILE_ID = "6718c2f0a1b2c3d4e5f60789"
SMALL = 64  # tiny chunks so the tests exercise many chunks quickly


def encrypt(data: bytes, dek: bytes, file_id: str = FILE_ID, chunk_size: int = SMALL) -> bytes:
    out = io.BytesIO()
    encrypt_file(dek, file_id, io.BytesIO(data), out, chunk_size=chunk_size)
    return out.getvalue()


def sealed_chunks(blob: bytes, chunk_size: int = SMALL) -> tuple[bytes, list[bytes]]:
    """Split an encrypted object into its header and sealed chunks."""
    size = chunk_size + TAG_BYTES
    body = blob[HEADER.size :]
    return blob[: HEADER.size], [body[i : i + size] for i in range(0, len(body), size)]


# ---------- round trip ----------


@pytest.mark.parametrize("length", [0, 1, SMALL - 1, SMALL, SMALL + 1, SMALL * 5, SMALL * 5 + 7])
def test_round_trip_for_every_size(length: int) -> None:
    dek, data = generate_dek(), os.urandom(length)

    blob = encrypt(data, dek)

    assert decrypt_bytes(dek, FILE_ID, blob) == data
    assert len(blob) == encrypted_size(length, SMALL)


def test_ciphertext_does_not_contain_the_plaintext() -> None:
    data = b"Confidential Project_Report contents " * 50

    blob = encrypt(data, generate_dek())

    assert b"Confidential" not in blob


def test_same_file_encrypts_differently_each_time() -> None:
    dek, data = generate_dek(), b"same content" * 20

    assert encrypt(data, dek) != encrypt(data, dek)  # random nonce prefix per encryption


def test_file_keys_are_256_bit_and_unique() -> None:
    keys = {generate_dek() for _ in range(100)}

    assert len(keys) == 100
    assert all(len(key) == 32 for key in keys)


def test_streaming_decryption_with_odd_piece_sizes() -> None:
    dek, data = generate_dek(), os.urandom(1000)
    blob = encrypt(data, dek)

    async def pieces():
        for i in range(0, len(blob), 37):  # boundaries that never match chunk edges
            yield blob[i : i + 37]

    async def collect() -> bytes:
        return b"".join([chunk async for chunk in decrypt_stream(dek, FILE_ID, pieces())])

    assert asyncio.run(collect()) == data


def test_default_chunk_size_large_file() -> None:
    dek, data = generate_dek(), os.urandom(2 * 1024 * 1024 + 123)  # spans three 1 MiB chunks

    out = io.BytesIO()
    encrypt_file(dek, FILE_ID, io.BytesIO(data), out)

    assert decrypt_bytes(dek, FILE_ID, out.getvalue()) == data


# ---------- tampering is detected ----------


def test_flipped_bit_is_rejected() -> None:
    dek = generate_dek()
    blob = bytearray(encrypt(b"x" * 300, dek))
    blob[HEADER.size + 10] ^= 0x01

    with pytest.raises(DecryptionError):
        decrypt_bytes(dek, FILE_ID, bytes(blob))


def test_truncated_file_is_rejected() -> None:
    dek = generate_dek()
    header, chunks = sealed_chunks(encrypt(b"y" * (SMALL * 4), dek))

    cut = header + b"".join(chunks[:-1])  # drop the real last chunk

    with pytest.raises(DecryptionError):
        decrypt_bytes(dek, FILE_ID, cut)


def test_reordered_chunks_are_rejected() -> None:
    dek = generate_dek()
    header, chunks = sealed_chunks(encrypt(os.urandom(SMALL * 4), dek))

    swapped = header + chunks[1] + chunks[0] + b"".join(chunks[2:])

    with pytest.raises(DecryptionError):
        decrypt_bytes(dek, FILE_ID, swapped)


def test_extra_chunk_appended_is_rejected() -> None:
    dek = generate_dek()
    blob = encrypt(os.urandom(SMALL * 2), dek)
    _, chunks = sealed_chunks(blob)

    with pytest.raises(DecryptionError):
        decrypt_bytes(dek, FILE_ID, blob + chunks[0])


def test_object_from_another_file_is_rejected() -> None:
    dek = generate_dek()
    blob = encrypt(b"belongs to file A", dek, file_id="a" * 24)

    with pytest.raises(DecryptionError):
        decrypt_bytes(dek, "b" * 24, blob)


def test_wrong_key_is_rejected() -> None:
    blob = encrypt(b"secret", generate_dek())

    with pytest.raises(DecryptionError):
        decrypt_bytes(generate_dek(), FILE_ID, blob)


def test_garbage_is_rejected() -> None:
    with pytest.raises(DecryptionError):
        decrypt_bytes(generate_dek(), FILE_ID, b"%PDF-1.4 not encrypted at all")


# ---------- envelope keys and the keyring ----------


def keyring(*versions: int, active: int) -> Keyring:
    return Keyring({v: os.urandom(32) for v in versions}, active)


def test_wrapped_key_round_trip_and_is_not_the_raw_key() -> None:
    service = EncryptionService(keyring(1, active=1))

    dek, stored = service.new_file_key(FILE_ID)

    assert dek not in stored.wrapped_key
    assert stored.key_version == 1
    assert service.open_file_key(FILE_ID, stored) == dek


def test_wrapped_key_is_bound_to_its_file() -> None:
    service = EncryptionService(keyring(1, active=1))
    _, stored = service.new_file_key("a" * 24)

    with pytest.raises(DecryptionError):
        service.open_file_key("b" * 24, stored)


def test_wrong_master_key_cannot_unwrap() -> None:
    _, stored = EncryptionService(keyring(1, active=1)).new_file_key(FILE_ID)

    with pytest.raises(DecryptionError):
        EncryptionService(keyring(1, active=1)).open_file_key(FILE_ID, stored)


def test_rotation_rewraps_with_new_version_and_old_files_still_open() -> None:
    old_ring = keyring(1, active=1)
    dek, stored_v1 = EncryptionService(old_ring).new_file_key(FILE_ID)
    # Rotation: add v2 and make it active, keeping v1 for files not yet re-wrapped.
    new_ring = Keyring({1: old_ring._keys[1], 2: os.urandom(32)}, active_version=2)
    service = EncryptionService(new_ring)

    assert service.open_file_key(FILE_ID, stored_v1) == dek  # still readable before re-wrap
    stored_v2 = service.rewrap(FILE_ID, stored_v1)

    assert stored_v2.key_version == 2
    assert service.open_file_key(FILE_ID, stored_v2) == dek  # same file key, new wrapping


def test_missing_master_key_version() -> None:
    ring = keyring(1, active=1)

    with pytest.raises(KeyUnwrapError):
        ring.unwrap(b"\x00" * 60, 9, FILE_ID)


def test_keyring_never_prints_keys() -> None:
    ring = keyring(1, 2, active=2)

    assert "versions=[1, 2]" in repr(ring)
    assert all(base64.b64encode(k).decode() not in repr(ring) for k in ring._keys.values())


# ---------- MASTER_KEYS parsing ----------


def test_parse_master_keys() -> None:
    k1, k2 = os.urandom(32), os.urandom(32)
    raw = f"1:{base64.b64encode(k1).decode()}, 2:{base64.b64encode(k2).decode()}"

    assert parse_master_keys(raw) == {1: k1, 2: k2}


@pytest.mark.parametrize(
    "raw",
    ["", "nonsense", "1:not-base64!!", f"1:{base64.b64encode(b'short').decode()}"],
)
def test_bad_master_keys_are_refused(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_master_keys(raw)
