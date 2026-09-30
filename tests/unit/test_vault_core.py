import hashlib
import json
import os
from pathlib import Path

import pytest

from pault_core.crypto import DEFAULT_KDF, aes_encrypt, derive_key, encode_b64
from pault_core.storage import atomic_write_json
from pault_core.vault import (
    VaultIntegrityError,
    VaultSession,
    create_vault,
    open_vault,
    unlock_vault,
)


def test_atomic_write_preserves_previous_document_if_commit_fails(tmp_path, monkeypatch):
    document = tmp_path / "vault.json"
    document.write_text('{"generation":1}\n', encoding="utf-8")

    def interrupt_commit(source, destination):
        raise OSError("simulated interruption")

    monkeypatch.setattr("pault_core.storage.os.replace", interrupt_commit)

    with pytest.raises(OSError, match="simulated interruption"):
        atomic_write_json(document, {"generation": 2})

    assert document.read_text(encoding="utf-8") == '{"generation":1}\n'
    assert list(tmp_path.glob("*.tmp")) == []


def test_vault_create_and_unlock_roundtrip(tmp_path):
    vault_path = tmp_path / "vault"
    password = "StrongPass!123"

    vault = create_vault(vault_path, password)
    payload = b"hello from securely encrypted vault\n" * 100
    vault.put_file("photos/hello.bin", payload)
    vault.close()

    session = unlock_vault(vault_path, password)
    assert session.read_file("photos/hello.bin") == payload
    session.lock()


def test_wrong_password_fails(tmp_path):
    vault_path = tmp_path / "vault"
    create_vault(vault_path, "CorrectHorseBatteryStaple!")

    with pytest.raises(ValueError, match="Incorrect password"):
        unlock_vault(vault_path, "wrong-password")


def test_tampering_detected(tmp_path):
    vault_path = tmp_path / "vault"
    password = "StrongPass!123"
    vault = create_vault(vault_path, password)
    vault.put_file("photos/secret.txt", b"top secret")
    vault.close()

    metadata_path = vault_path / "vault.json"
    data = metadata_path.read_bytes()
    tampered = data[:-1] + bytes([data[-1] ^ 0xFF])
    metadata_path.write_bytes(tampered)

    with pytest.raises(VaultIntegrityError):
        unlock_vault(vault_path, password)


def test_change_password_requires_old_password(tmp_path):
    vault_path = tmp_path / "vault"
    create_vault(vault_path, "OldPass!123")

    with pytest.raises(ValueError, match="Current password is incorrect"):
        open_vault(vault_path, "Wrong!123").change_password("NewPass!456")

    session = unlock_vault(vault_path, "OldPass!123")
    session.change_password("NewPass!456")
    session.lock()

    unlocked = unlock_vault(vault_path, "NewPass!456")
    assert unlocked.list_files() == []
    unlocked.close()
    with pytest.raises(ValueError, match="Incorrect password"):
        unlock_vault(vault_path, "OldPass!123")


def test_large_file_stays_byte_identical(tmp_path):
    vault_path = tmp_path / "vault"
    password = "StrongPass!123"
    vault = create_vault(vault_path, password)

    payload = hashlib.sha256(b"pault-test-fixture").digest() * 8192
    vault.put_file("videos/test.bin", payload)
    vault.close()

    session = unlock_vault(vault_path, password)
    restored = session.read_file("videos/test.bin")
    assert restored == payload
    assert hashlib.sha256(restored).hexdigest() == hashlib.sha256(payload).hexdigest()
    session.lock()


def test_streaming_import_export_and_folder_operations(tmp_path):
    vault_path = tmp_path / "vault"
    source = tmp_path / "旅行.png"
    payload = bytes(range(251)) * 18000
    source.write_bytes(payload)
    vault = create_vault(vault_path, "StrongPass!123")

    vault.create_folder("Photos/2026")
    vault.import_file(source, "Photos/2026/旅行.png")
    assert vault.list_entries("Photos/2026")[0]["path"] == "Photos/2026/旅行.png"
    vault.rename("Photos/2026", "Photos/Archive")

    exported = tmp_path / "exported.png"
    vault.export_file("Photos/Archive/旅行.png", exported)
    assert hashlib.sha256(exported.read_bytes()).digest() == hashlib.sha256(payload).digest()
    vault.delete_file("Photos/Archive")
    assert vault.list_files() == []
    vault.close()


def test_empty_file_and_duplicate_path_behavior(tmp_path):
    vault = create_vault(tmp_path / "vault", "StrongPass!123")
    vault.put_file("empty", b"")
    assert vault.read_file("empty") == b""
    with pytest.raises(FileExistsError):
        vault.create_folder("empty")
    vault.put_file("Photos/cover.jpg", b"image")
    with pytest.raises(FileExistsError):
        vault.create_folder("photos")
    vault.close()


def test_interrupted_manifest_commit_keeps_previous_vault_valid(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    vault = create_vault(vault_path, "StrongPass!123")
    vault.put_file("keep.txt", b"committed")
    original_document = (vault_path / "vault.json").read_bytes()

    def interrupt_commit(path, payload):
        raise OSError("simulated interruption")

    monkeypatch.setattr("pault_core.vault.atomic_write_json", interrupt_commit)
    with pytest.raises(OSError, match="simulated interruption"):
        vault.put_file("never-committed.txt", b"staged only")

    assert (vault_path / "vault.json").read_bytes() == original_document
    vault.close()
    recovered = unlock_vault(vault_path, "StrongPass!123")
    assert recovered.list_files() == ["keep.txt"]
    assert recovered.read_file("keep.txt") == b"committed"
    recovered.close()


def test_encrypted_object_tampering_is_detected(tmp_path):
    vault_path = tmp_path / "vault"
    vault = create_vault(vault_path, "StrongPass!123")
    vault.put_file("private.bin", b"authenticated file data")
    object_id = vault.entries["private.bin"]["object_id"]
    vault.close()

    object_path = vault_path / "objects" / f"{object_id}.paultobj"
    ciphertext = bytearray(object_path.read_bytes())
    ciphertext[25] ^= 0x01
    object_path.write_bytes(ciphertext)

    session = unlock_vault(vault_path, "StrongPass!123")
    with pytest.raises(VaultIntegrityError):
        session.read_file("private.bin")
    session.close()


def test_interrupted_password_change_keeps_old_credentials_usable(tmp_path, monkeypatch):
    vault_path = tmp_path / "vault"
    vault = create_vault(vault_path, "OldPass!123")
    vault.put_file("keep.txt", b"still committed")
    previous_document = (vault_path / "vault.json").read_bytes()

    def interrupt_commit(path, payload):
        raise OSError("simulated interruption")

    monkeypatch.setattr("pault_core.vault.atomic_write_json", interrupt_commit)
    with pytest.raises(OSError, match="simulated interruption"):
        vault.change_password("NewPass!456")

    assert (vault_path / "vault.json").read_bytes() == previous_document
    assert vault.read_file("keep.txt") == b"still committed"
    vault.close()
    recovered = unlock_vault(vault_path, "OldPass!123")
    assert recovered.read_file("keep.txt") == b"still committed"
    recovered.close()


def test_v1_vault_migrates_to_streamed_v2_on_unlock(tmp_path):
    vault_path = tmp_path / "legacy-vault"
    vault_path.mkdir()
    password = "LegacyPass!123"
    salt = os.urandom(16)
    vault_secret = os.urandom(32)
    password_key = derive_key(password, salt, **{key: DEFAULT_KDF[key] for key in ("memory_cost_kib", "time_cost", "parallelism", "hash_len")})
    payload = b"legacy encrypted bytes" * 100
    chunk_nonce, encrypted_chunk = aes_encrypt(vault_secret, payload)
    entries = {"files": {"legacy.txt": {"kind": "file", "sha256": encode_b64(hashlib.sha256(payload).digest()), "size": len(payload), "chunks": [{"nonce": encode_b64(chunk_nonce), "ciphertext": encode_b64(encrypted_chunk)}]}}}
    entries_nonce, encrypted_entries = aes_encrypt(vault_secret, json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    secret_nonce, encrypted_secret = aes_encrypt(password_key, vault_secret)
    atomic_write_json(vault_path / "vault.json", {
        "vault_version": 1,
        "vault_id": "legacy-vault-id",
        "salt": encode_b64(salt),
        "kdf": DEFAULT_KDF,
        "entries_nonce": encode_b64(entries_nonce),
        "entries_ciphertext": encode_b64(encrypted_entries),
        "vault_secret_nonce": encode_b64(secret_nonce),
        "vault_secret_ciphertext": encode_b64(encrypted_secret),
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    })

    session = unlock_vault(vault_path, password)
    assert session.version == 2
    assert session.read_file("legacy.txt") == payload
    session.close()
    assert json.loads((vault_path / "vault.json").read_text(encoding="utf-8"))["vault_version"] == 2


def test_raw_vault_files_do_not_contain_plaintext_or_names(tmp_path):
    vault_path = tmp_path / "vault"
    secret_name = "private-photo-name.jpg"
    plaintext_marker = b"PAULT-PLAINTEXT-MARKER-7d94c2"
    vault = create_vault(vault_path, "StrongPass!123")
    vault.put_file(secret_name, plaintext_marker * 200)
    vault.close()

    stored_bytes = b"".join(path.read_bytes() for path in vault_path.rglob("*") if path.is_file())
    assert secret_name.encode("utf-8") not in stored_bytes
    assert plaintext_marker not in stored_bytes
