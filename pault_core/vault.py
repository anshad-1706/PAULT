import json
import hashlib
import io
import os
import struct
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterable

from .crypto import DEFAULT_KDF, aes_decrypt, aes_encrypt, decode_b64, derive_key, encode_b64
from .storage import atomic_write_json, fsync_directory, normalize_relative_path


_OBJECT_MAGIC = b"PAULTOBJ2\n"
_CHUNK_SIZE = 1024 * 1024
_MAX_CIPHERTEXT_CHUNK = _CHUNK_SIZE + 16


class VaultIntegrityError(RuntimeError):
    """Raised when the encrypted vault metadata or file contents fail authentication."""


class VaultSession:
    def __init__(self, vault_path: str | Path, *, vault_id: str, salt: bytes, vault_secret: bytes, entries: dict[str, Any], kdf: dict[str, Any], format_version: int = 2, created_at: str | None = None):
        self.vault_path = Path(vault_path)
        self.password_key = b""
        self.vault_id = vault_id
        self.salt = salt
        self.vault_secret = vault_secret
        self.entries = entries
        self.kdf = {**DEFAULT_KDF, **kdf}
        self.format_version = format_version
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.closed = False

    @property
    def version(self) -> int:
        return self.format_version

    def lock(self) -> None:
        self.password_key = b"\x00" * 32
        self.vault_secret = b"\x00" * 32
        self.entries = {}
        self.closed = True

    def close(self) -> None:
        self.lock()

    def list_files(self) -> list[str]:
        self._ensure_open()
        return sorted(path for path, entry in self.entries.items() if entry.get("kind") == "file")

    def list_entries(self, folder: str = "") -> list[dict[str, Any]]:
        self._ensure_open()
        prefix = normalize_relative_path(folder) + "/" if folder else ""
        results = []
        for path, entry in self.entries.items():
            if not path.startswith(prefix):
                continue
            relative = path[len(prefix):]
            if "/" in relative:
                child = relative.split("/", 1)[0]
                child_path = f"{prefix}{child}"
                if not any(item["path"] == child_path for item in results):
                    results.append({"path": child_path, "kind": "folder", "size": 0, "modified_at": ""})
            else:
                results.append({"path": path, **entry})
        return sorted(results, key=lambda item: (item["kind"] != "folder", item["path"].casefold()))

    def read_file(self, path: str) -> bytes:
        self._ensure_open()
        output = io.BytesIO()
        self.read_file_to(path, output)
        return output.getvalue()

    def read_file_to(self, path: str, destination: BinaryIO, *, progress: Callable[[int, int], None] | None = None) -> None:
        self._ensure_open()
        normalized = normalize_relative_path(path)
        entry = self.entries.get(normalized)
        if entry is None:
            raise FileNotFoundError(f"File not found: {normalized}")
        if entry.get("kind") != "file":
            raise ValueError(f"Path is not a file: {normalized}")
        if "object_id" in entry:
            self._stream_object(
                self._object_path(entry["object_id"]),
                entry["object_id"],
                destination,
                expected_size=entry["size"],
                expected_digest=entry["sha256"],
                progress=progress,
            )
            return
        digest = hashlib.sha256()
        size = 0
        for chunk in entry["chunks"]:
            plaintext = aes_decrypt(self.vault_secret, decode_b64(chunk["nonce"]), decode_b64(chunk["ciphertext"]))
            destination.write(plaintext)
            digest.update(plaintext)
            size += len(plaintext)
            if progress:
                progress(size, entry.get("size", size))
        if entry.get("sha256") and encode_b64(digest.digest()) != entry["sha256"]:
            raise VaultIntegrityError("Vault integrity check failed.")

    def import_file(self, source_path: str | Path, vault_path: str, *, progress: Callable[[int, int], None] | None = None) -> None:
        source = Path(source_path)
        with source.open("rb") as handle:
            self.put_file_stream(vault_path, handle, total_size=source.stat().st_size, progress=progress)

    def put_file(self, path: str, data: bytes) -> None:
        self.put_file_stream(path, io.BytesIO(data), total_size=len(data))

    def put_file_stream(self, path: str, source: BinaryIO, *, total_size: int | None = None, progress: Callable[[int, int], None] | None = None) -> None:
        self._ensure_open()
        normalized = normalize_relative_path(path)
        previous_entries = self.entries.copy()
        previous = self.entries.get(normalized)
        if previous is not None and previous.get("kind") == "folder":
            raise IsADirectoryError(normalized)
        self._ensure_casefold_available(normalized, allow_exact=True)
        object_id = uuid.uuid4().hex
        size, digest = self._write_object(object_id, self._source_chunks(source, total_size, progress))
        entry = {
            "kind": "file",
            "sha256": digest,
            "size": size,
            "object_id": object_id,
            "modified_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._ensure_parent_folders(normalized)
            self.entries[normalized] = entry
            self._persist()
        except Exception:
            self.entries = previous_entries
            self._object_path(object_id).unlink(missing_ok=True)
            raise
        if previous and previous.get("object_id"):
            self._object_path(previous["object_id"]).unlink(missing_ok=True)

    def delete_file(self, path: str) -> None:
        self._ensure_open()
        normalized = normalize_relative_path(path)
        if normalized not in self.entries:
            raise FileNotFoundError(f"Path not found: {normalized}")
        removed_paths = [name for name in self.entries if name == normalized or name.startswith(normalized + "/")]
        previous_entries = self.entries
        self.entries = {name: entry for name, entry in self.entries.items() if name not in removed_paths}
        try:
            self._persist()
        except Exception:
            self.entries = previous_entries
            raise
        for name in removed_paths:
            object_id = previous_entries[name].get("object_id")
            if object_id:
                self._object_path(object_id).unlink(missing_ok=True)

    def create_folder(self, path: str) -> None:
        self._ensure_open()
        normalized = normalize_relative_path(path)
        if any(existing.casefold() == normalized.casefold() for existing in self.entries):
            raise FileExistsError(normalized)
        previous_entries = self.entries.copy()
        try:
            self._ensure_parent_folders(normalized)
            self.entries[normalized] = {"kind": "folder", "modified_at": datetime.now(timezone.utc).isoformat()}
            self._persist()
        except Exception:
            self.entries = previous_entries
            raise

    def rename(self, old_path: str, new_path: str) -> None:
        self._ensure_open()
        old = normalize_relative_path(old_path)
        new = normalize_relative_path(new_path)
        if old == new:
            return
        if old not in self.entries:
            raise FileNotFoundError(f"Path not found: {old}")
        if new.startswith(old + "/"):
            raise ValueError("A folder cannot be moved inside itself.")
        moving = {name: entry for name, entry in self.entries.items() if name == old or name.startswith(old + "/")}
        renamed = {new + name[len(old):]: entry for name, entry in moving.items()}
        moving_folded = {name.casefold() for name in moving}
        occupied_folded = {existing.casefold() for existing in self.entries if existing.casefold() not in moving_folded}
        if any(name.casefold() in occupied_folded for name in renamed):
            raise FileExistsError(new)
        previous_entries = self.entries.copy()
        try:
            self._ensure_parent_folders(new)
            for name in moving:
                self.entries.pop(name)
            self.entries.update(renamed)
            self._persist()
        except Exception:
            self.entries = previous_entries
            raise

    def export_file(self, path: str, destination: str | Path, *, progress: Callable[[int, int], None] | None = None) -> None:
        self._ensure_open()
        destination_path = Path(destination)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="wb", dir=destination_path.parent, prefix=f".{destination_path.name}.", suffix=".tmp", delete=False) as handle:
                temporary_path = Path(handle.name)
                self.read_file_to(path, handle, progress=progress)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, destination_path)
            fsync_directory(destination_path.parent)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def change_password(self, new_password: str) -> None:
        self._ensure_open()
        if not new_password or not isinstance(new_password, str):
            raise ValueError("New password must be non-empty.")
        new_salt = os.urandom(16)
        new_key = derive_key(new_password, new_salt, **{key: self.kdf[key] for key in ("memory_cost_kib", "time_cost", "parallelism", "hash_len") if key in self.kdf})
        entries_payload = json.dumps({"files": self.entries}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        entries_nonce, entries_ciphertext = aes_encrypt(self.vault_secret, entries_payload)
        vault_secret_nonce, vault_secret_ciphertext = aes_encrypt(new_key, self.vault_secret)
        previous_salt, previous_key = self.salt, self.password_key
        try:
            self.salt = new_salt
            self.password_key = new_key
            self.kdf = {**DEFAULT_KDF, **self.kdf}
            self._write_document(entries_nonce, entries_ciphertext, vault_secret_nonce, vault_secret_ciphertext)
        except Exception:
            self.salt, self.password_key = previous_salt, previous_key
            raise

    def _ensure_open(self) -> None:
        if self.closed or not self.vault_secret or not self.password_key:
            raise ValueError("Vault is locked.")

    def _persist(self) -> None:
        entries_payload = json.dumps({"files": self.entries}, sort_keys=True, separators=(",", ":")).encode("utf-8")
        entries_nonce, entries_ciphertext = aes_encrypt(self.vault_secret, entries_payload)
        vault_secret_nonce, vault_secret_ciphertext = aes_encrypt(self.password_key, self.vault_secret)
        self._write_document(entries_nonce, entries_ciphertext, vault_secret_nonce, vault_secret_ciphertext)

    def _ensure_parent_folders(self, path: str) -> None:
        parts = path.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            parent = "/".join(parts[:index])
            entry = self.entries.get(parent)
            if any(existing.casefold() == parent.casefold() and existing != parent for existing in self.entries):
                raise FileExistsError(parent)
            if entry is not None and entry.get("kind") != "folder":
                raise NotADirectoryError(parent)
            if entry is None:
                self.entries[parent] = {"kind": "folder", "modified_at": datetime.now(timezone.utc).isoformat()}

    def _ensure_casefold_available(self, path: str, *, allow_exact: bool = False) -> None:
        for existing in self.entries:
            if existing.casefold() == path.casefold() and not (allow_exact and existing == path):
                raise FileExistsError(path)

    def _source_chunks(self, source: BinaryIO, total_size: int | None, progress: Callable[[int, int], None] | None) -> Iterable[bytes]:
        size = 0
        while True:
            chunk = source.read(_CHUNK_SIZE)
            if not chunk:
                break
            size += len(chunk)
            if progress:
                progress(size, total_size if total_size is not None else -1)
            yield chunk

    def _object_path(self, object_id: str) -> Path:
        return self.vault_path / "objects" / f"{object_id}.paultobj"

    def _write_object(self, object_id: str, chunks: Iterable[bytes]) -> tuple[int, str]:
        object_path = self._object_path(object_id)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = object_path.with_name(f".{object_id}.tmp")
        digest = hashlib.sha256()
        size = 0
        try:
            with temporary_path.open("xb") as handle:
                handle.write(_OBJECT_MAGIC)
                for index, chunk in enumerate(chunks):
                    digest.update(chunk)
                    size += len(chunk)
                    associated_data = f"{self.vault_id}:{object_id}:{index}".encode("ascii")
                    nonce, ciphertext = aes_encrypt(self.vault_secret, chunk, associated_data)
                    handle.write(struct.pack(">I", len(ciphertext)))
                    handle.write(nonce)
                    handle.write(ciphertext)
                handle.write(struct.pack(">I", 0))
                handle.flush()
                os.fsync(handle.fileno())
            digest_b64 = encode_b64(digest.digest())
            self._stream_object(temporary_path, object_id, None, expected_size=size, expected_digest=digest_b64)
            os.replace(temporary_path, object_path)
            fsync_directory(object_path.parent)
            return size, digest_b64
        except Exception:
            temporary_path.unlink(missing_ok=True)
            object_path.unlink(missing_ok=True)
            raise

    def _stream_object(self, object_path: Path, object_id: str, destination: BinaryIO | None, *, expected_size: int, expected_digest: str, progress: Callable[[int, int], None] | None = None) -> None:
        digest = hashlib.sha256()
        size = 0
        try:
            with object_path.open("rb") as handle:
                if handle.read(len(_OBJECT_MAGIC)) != _OBJECT_MAGIC:
                    raise VaultIntegrityError("Vault integrity check failed.")
                index = 0
                while True:
                    length_data = handle.read(4)
                    if len(length_data) != 4:
                        raise VaultIntegrityError("Vault integrity check failed.")
                    encrypted_size = struct.unpack(">I", length_data)[0]
                    if encrypted_size == 0:
                        if handle.read(1):
                            raise VaultIntegrityError("Vault integrity check failed.")
                        break
                    if encrypted_size < 16 or encrypted_size > _MAX_CIPHERTEXT_CHUNK:
                        raise VaultIntegrityError("Vault integrity check failed.")
                    nonce = handle.read(12)
                    ciphertext = handle.read(encrypted_size)
                    if len(nonce) != 12 or len(ciphertext) != encrypted_size:
                        raise VaultIntegrityError("Vault integrity check failed.")
                    associated_data = f"{self.vault_id}:{object_id}:{index}".encode("ascii")
                    plaintext = aes_decrypt(self.vault_secret, nonce, ciphertext, associated_data)
                    if destination is not None:
                        destination.write(plaintext)
                    digest.update(plaintext)
                    size += len(plaintext)
                    index += 1
                    if progress:
                        progress(size, expected_size)
        except (OSError, ValueError, struct.error) as exc:
            raise VaultIntegrityError("Vault integrity check failed.") from exc
        if size != expected_size or encode_b64(digest.digest()) != expected_digest:
            raise VaultIntegrityError("Vault integrity check failed.")

    def _migrate_legacy_entries(self) -> None:
        previous_entries = self.entries
        previous_version = self.format_version
        migrated = {}
        created_objects = []
        try:
            for path, entry in previous_entries.items():
                if entry.get("kind") != "file" or "chunks" not in entry:
                    migrated[path] = entry
                    continue
                object_id = uuid.uuid4().hex

                def plaintext_chunks():
                    for chunk in entry["chunks"]:
                        yield aes_decrypt(self.vault_secret, decode_b64(chunk["nonce"]), decode_b64(chunk["ciphertext"]))

                size, digest = self._write_object(object_id, plaintext_chunks())
                if size != entry.get("size", size) or (entry.get("sha256") and digest != entry["sha256"]):
                    raise VaultIntegrityError("Vault integrity check failed.")
                created_objects.append(object_id)
                migrated[path] = {
                    "kind": "file",
                    "object_id": object_id,
                    "sha256": digest,
                    "size": size,
                    "modified_at": entry.get("modified_at", datetime.now(timezone.utc).isoformat()),
                }
            self.entries = migrated
            self.format_version = 2
            self._persist()
        except Exception:
            self.entries = previous_entries
            self.format_version = previous_version
            for object_id in created_objects:
                self._object_path(object_id).unlink(missing_ok=True)
            raise

    def _write_document(self, entries_nonce: bytes, entries_ciphertext: bytes, vault_secret_nonce: bytes | None = None, vault_secret_ciphertext: bytes | None = None) -> None:
        self.vault_path.mkdir(parents=True, exist_ok=True)
        vault_file = self.vault_path / "vault.json"
        if vault_secret_nonce is None or vault_secret_ciphertext is None:
            vault_secret_nonce, vault_secret_ciphertext = aes_encrypt(self.password_key, self.vault_secret)
        document = {
            "vault_version": self.format_version,
            "vault_id": self.vault_id,
            "salt": encode_b64(self.salt),
            "kdf": self.kdf,
            "entries_nonce": encode_b64(entries_nonce),
            "entries_ciphertext": encode_b64(entries_ciphertext),
            "vault_secret_nonce": encode_b64(vault_secret_nonce),
            "vault_secret_ciphertext": encode_b64(vault_secret_ciphertext),
            "created_at": self.created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(vault_file, document)


def create_vault(vault_path: str | Path, password: str) -> VaultSession:
    path = Path(vault_path)
    if path.exists() and path.is_file():
        raise ValueError("Vault path must be a directory.")
    if (path / "vault.json").exists():
        raise FileExistsError("A vault already exists at this location.")
    path.mkdir(parents=True, exist_ok=True)
    salt = os.urandom(16)
    vault_secret = os.urandom(32)
    kdf = {**DEFAULT_KDF}
    password_key = derive_key(password, salt, **{key: kdf[key] for key in ("memory_cost_kib", "time_cost", "parallelism", "hash_len")})
    session = VaultSession(
        path,
        vault_id=uuid.uuid4().hex,
        salt=salt,
        vault_secret=vault_secret,
        entries={},
        kdf=kdf,
        format_version=2,
    )
    session.password_key = password_key
    session._persist()
    return session


def unlock_vault(vault_path: str | Path, password: str) -> VaultSession:
    vault_file = Path(vault_path) / "vault.json"
    if not vault_file.exists():
        raise FileNotFoundError("Vault not found.")
    try:
        document = json.loads(vault_file.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VaultIntegrityError("Vault integrity check failed.") from exc

    salt = decode_b64(document["salt"])
    kdf = document.get("kdf", DEFAULT_KDF)
    password_key = derive_key(password, salt, **{key: kdf[key] for key in ("memory_cost_kib", "time_cost", "parallelism", "hash_len") if key in kdf})

    try:
        vault_secret = aes_decrypt(
            password_key,
            decode_b64(document["vault_secret_nonce"]),
            decode_b64(document["vault_secret_ciphertext"]),
        )
    except ValueError as exc:
        raise ValueError("Incorrect password.") from exc

    try:
        entries_payload = aes_decrypt(
            vault_secret,
            decode_b64(document["entries_nonce"]),
            decode_b64(document["entries_ciphertext"]),
        )
        entries = json.loads(entries_payload.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise VaultIntegrityError("Vault integrity check failed.") from exc

    version = document.get("vault_version", 1)
    if version not in (1, 2):
        raise VaultIntegrityError("Vault integrity check failed.")
    session = VaultSession(
        vault_path,
        vault_id=document["vault_id"],
        salt=salt,
        vault_secret=vault_secret,
        entries=entries.get("files", {}),
        kdf=kdf,
        format_version=version,
        created_at=document.get("created_at"),
    )
    session.password_key = password_key
    session.closed = False
    if version == 1:
        session._migrate_legacy_entries()
    return session


def open_vault(vault_path: str | Path, password: str) -> VaultSession:
    try:
        return unlock_vault(vault_path, password)
    except ValueError as exc:
        raise ValueError("Current password is incorrect.") from exc


__all__ = [
    "VaultIntegrityError",
    "VaultSession",
    "create_vault",
    "unlock_vault",
    "open_vault",
]
