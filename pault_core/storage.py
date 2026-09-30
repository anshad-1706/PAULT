import json
import os
import tempfile
from pathlib import Path
from typing import Iterable


def normalize_relative_path(path: str) -> str:
    clean = str(path).replace('\\', '/')
    if clean.startswith('/') or clean.startswith('..') or clean in ('', '.'):
        raise ValueError("Invalid vault path.")
    normalized = []
    for part in clean.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            raise ValueError("Invalid vault path.")
        normalized.append(part)
    return '/'.join(normalized)


def chunk_bytes(data: bytes, chunk_size: int = 1024 * 1024) -> Iterable[bytes]:
    for idx in range(0, len(data), chunk_size):
        yield data[idx : idx + chunk_size]


def atomic_write_json(path: Path, payload: dict) -> None:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        fsync_directory(path.parent)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory_fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass
