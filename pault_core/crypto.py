import base64
import hashlib
import os
from typing import Optional

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DEFAULT_KDF = {
    "name": "argon2id",
    "memory_cost_kib": 65536,
    "time_cost": 3,
    "parallelism": 1,
    "hash_len": 32,
}


def derive_key(password: str, salt: bytes, *, memory_cost_kib: int = 65536, time_cost: int = 3, parallelism: int = 1, hash_len: int = 32) -> bytes:
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    if not isinstance(salt, (bytes, bytearray)) or len(salt) < 16:
        raise ValueError("Salt must be at least 16 random bytes.")
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=bytes(salt),
        time_cost=time_cost,
        memory_cost=memory_cost_kib,
        parallelism=parallelism,
        hash_len=hash_len,
        type=Type.ID,
    )


def encode_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def decode_b64(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def sha256_digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def aes_encrypt(key: bytes, plaintext: bytes, associated_data: Optional[bytes] = None) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, associated_data)
    return nonce, ciphertext


def aes_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, associated_data: Optional[bytes] = None) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, associated_data)
    except InvalidTag as exc:  # pragma: no cover - exercised via public API
        raise ValueError("Incorrect password.") from exc
