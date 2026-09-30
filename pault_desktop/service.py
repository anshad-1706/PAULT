from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from pault_core.vault import VaultSession, create_vault, unlock_vault
from pault_core.storage import normalize_relative_path
from .paths import validate_vault_destination


@dataclass(frozen=True)
class ImportFile:
    source: Path
    destination: str
    size: int


@dataclass(frozen=True)
class ImportPlan:
    files: tuple[ImportFile, ...]
    folders: tuple[str, ...]
    total_size: int


@dataclass(frozen=True)
class ExportFile:
    vault_path: str
    relative_path: Path
    size: int


@dataclass(frozen=True)
class ExportPlan:
    files: tuple[ExportFile, ...]
    directories: tuple[Path, ...]
    total_size: int


class VaultService:
    """UI-facing vault operations; encryption remains inside pault_core."""

    def __init__(self) -> None:
        self.session: VaultSession | None = None
        self.vault_path: Path | None = None
        self._temporary_media: set[Path] = set()

    @property
    def unlocked(self) -> bool:
        return self.session is not None and not self.session.closed

    def create(self, path: str | Path, password: str) -> None:
        validated_path = validate_vault_destination(path)
        self.lock()
        self.session = create_vault(validated_path, password)
        self.vault_path = validated_path

    def unlock(self, path: str | Path, password: str) -> None:
        self.lock()
        self.session = unlock_vault(path, password)
        self.vault_path = Path(path)

    def lock(self) -> None:
        if self.session is not None:
            self.session.lock()
        self.session = None
        for temporary_path in self._temporary_media:
            temporary_path.unlink(missing_ok=True)
        self._temporary_media.clear()

    def check_available(self) -> bool:
        if not self.unlocked:
            return False
        if self.vault_path is None or not (self.vault_path / "vault.json").is_file():
            self.lock()
            return False
        return True

    def list_entries(self, folder: str = "") -> list[dict]:
        return self._session().list_entries(folder)

    def get_entry(self, path: str) -> dict | None:
        entry = self._session().entries.get(path)
        return dict(entry) if entry is not None else None

    def create_folder(self, path: str) -> None:
        self._session().create_folder(path)

    def rename(self, old_path: str, new_path: str) -> None:
        self._session().rename(old_path, new_path)

    def delete(self, path: str) -> None:
        self._session().delete_file(path)

    def search_entries(self, query: str = "", category: str = "all") -> list[dict]:
        session = self._session()
        needle = query.casefold()
        results = []
        for path, entry in session.entries.items():
            if category == "folders":
                if entry.get("kind") == "folder" and (not needle or needle in path.casefold()):
                    results.append({"path": path, **entry})
                continue
            if entry.get("kind") == "folder":
                if category == "all" and needle and needle in path.casefold():
                    results.append({"path": path, **entry})
                continue
            if entry.get("kind") != "file":
                continue
            suffix = Path(path).suffix.casefold()
            if category == "photos" and suffix not in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
                continue
            if category == "videos" and suffix not in {".mp4", ".mov", ".mkv"}:
                continue
            if needle and needle not in path.casefold():
                continue
            results.append({"path": path, **entry})
        if category == "recent":
            results.sort(key=lambda item: item.get("modified_at", ""), reverse=True)
        else:
            results.sort(key=lambda item: item["path"].casefold())
        return results

    def read_file(self, vault_path: str) -> bytes:
        return self._session().read_file(vault_path)

    def plan_import(self, sources: Iterable[str | Path], destination: str = "") -> ImportPlan:
        session = self._session()
        target_prefix = normalize_relative_path(destination) if destination else ""
        files: list[ImportFile] = []
        folders: set[str] = set()

        def target_path(relative: str) -> str:
            return normalize_relative_path(f"{target_prefix}/{relative}" if target_prefix else relative)

        for supplied_path in sources:
            source = Path(supplied_path)
            if source.is_symlink():
                raise ValueError(f"Symbolic links cannot be imported: {source.name}")
            if not source.exists():
                raise FileNotFoundError(source)
            if source.is_file():
                files.append(ImportFile(source, target_path(source.name), source.stat().st_size))
                continue
            if not source.is_dir():
                raise ValueError(f"Unsupported import source: {source.name}")
            root_relative = source.name
            folders.add(target_path(root_relative))
            for current, directory_names, file_names in os.walk(source, followlinks=False):
                current_path = Path(current)
                for directory_name in tuple(directory_names):
                    directory_path = current_path / directory_name
                    if directory_path.is_symlink():
                        raise ValueError(f"Symbolic links cannot be imported: {directory_path.name}")
                    relative = Path(root_relative) / directory_path.relative_to(source)
                    folders.add(target_path(relative.as_posix()))
                for file_name in sorted(file_names):
                    file_path = current_path / file_name
                    if file_path.is_symlink() or not file_path.is_file():
                        raise ValueError(f"Unsupported import source: {file_path.name}")
                    relative = Path(root_relative) / file_path.relative_to(source)
                    files.append(ImportFile(file_path, target_path(relative.as_posix()), file_path.stat().st_size))

        targets = [*folders, *(file.destination for file in files)]
        folded_targets = [path.casefold() for path in targets]
        if len(set(folded_targets)) != len(folded_targets):
            raise FileExistsError("The import contains duplicate names.")
        existing = {path.casefold() for path in session.entries}
        if any(path in existing for path in folded_targets):
            raise FileExistsError("An item with the same name already exists in the destination.")
        return ImportPlan(tuple(files), tuple(sorted(folders, key=lambda path: (path.count("/"), path.casefold()))), sum(item.size for item in files))

    def import_plan(self, plan: ImportPlan, *, progress: Callable[[int, int], None] | None = None) -> None:
        session = self._session()
        for folder in plan.folders:
            if folder not in session.entries:
                session.create_folder(folder)
        completed = 0
        for item in plan.files:
            with item.source.open("rb") as source:
                session.put_file_stream(
                    item.destination,
                    source,
                    total_size=item.size,
                    progress=lambda current, _total: progress(completed + current, plan.total_size) if progress else None,
                )
            completed += item.size
            if progress:
                progress(completed, plan.total_size)

    def export_file(self, vault_path: str, destination: str | Path, *, progress: Callable[[int, int], None] | None = None) -> None:
        self._session().export_file(vault_path, destination, progress=progress)

    def plan_export(self, paths: Iterable[str], destination: str | Path) -> ExportPlan:
        session = self._session()
        output_root = Path(destination).expanduser().resolve(strict=False)
        vault_root = session.vault_path.resolve()
        if output_root == vault_root or vault_root in output_root.parents:
            raise ValueError("Export destination must be outside the encrypted vault.")
        selected = list(dict.fromkeys(paths))
        selected_folders = [path for path in selected if session.entries.get(path, {}).get("kind") == "folder"]
        selected_folders = [path for path in selected_folders if not any(path.startswith(parent + "/") for parent in selected_folders if parent != path)]
        selected_files = [path for path in selected if session.entries.get(path, {}).get("kind") == "file"]
        if any(path not in session.entries for path in selected):
            raise FileNotFoundError("A selected vault item no longer exists.")

        exported_files: dict[str, ExportFile] = {}
        directories: set[Path] = set()
        folder_prefixes = tuple(path + "/" for path in selected_folders)
        for folder in selected_folders:
            folder_name = Path(folder).name
            directories.add(Path(folder_name))
            for source_path, entry in session.entries.items():
                if not source_path.startswith(folder + "/"):
                    continue
                suffix = source_path[len(folder) + 1:]
                relative = Path(folder_name) / Path(suffix)
                if entry.get("kind") == "folder":
                    directories.add(relative)
                elif entry.get("kind") == "file":
                    exported_files[source_path] = ExportFile(source_path, relative, int(entry.get("size", 0)))

        for source_path in selected_files:
            if any(source_path.startswith(prefix) for prefix in folder_prefixes):
                continue
            entry = session.entries[source_path]
            exported_files[source_path] = ExportFile(source_path, Path(source_path).name, int(entry.get("size", 0)))

        return ExportPlan(
            tuple(exported_files.values()),
            tuple(sorted(directories, key=lambda path: (len(path.parts), str(path).casefold()))),
            sum(item.size for item in exported_files.values()),
        )

    def export_plan(self, plan: ExportPlan, destination: str | Path, *, conflict_policy: str = "cancel", progress: Callable[[int, int], None] | None = None) -> list[Path]:
        session = self._session()
        output_root = Path(destination).expanduser().resolve(strict=False)
        vault_root = session.vault_path.resolve()
        if output_root == vault_root or vault_root in output_root.parents:
            raise ValueError("Export destination must be outside the encrypted vault.")
        if conflict_policy not in {"cancel", "replace", "keep-both"}:
            raise ValueError("Unknown export conflict policy.")

        targets: list[tuple[ExportFile, Path]] = []
        reserved: set[str] = set()
        for item in plan.files:
            relative = item.relative_path
            target = output_root / relative
            folded = str(relative).casefold()
            collision = target.exists() or folded in reserved
            if collision and conflict_policy == "cancel":
                raise FileExistsError(f"An export file already exists: {target}")
            if collision and conflict_policy == "keep-both":
                target = self._keep_both_path(target, output_root, reserved)
                relative = target.relative_to(output_root)
                folded = str(relative).casefold()
            reserved.add(folded)
            targets.append((item, target))

        output_root.mkdir(parents=True, exist_ok=True)
        for directory in plan.directories:
            (output_root / directory).mkdir(parents=True, exist_ok=True)
        completed = 0
        exported = []
        for item, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)

            def update_progress(current: int, _total: int, completed_before: int = completed) -> None:
                if progress:
                    progress(completed_before + current, plan.total_size)

            session.export_file(item.vault_path, target, progress=update_progress)
            completed += item.size
            exported.append(target)
            if progress:
                progress(completed, plan.total_size)
        return exported

    @staticmethod
    def _keep_both_path(target: Path, output_root: Path, reserved: set[str]) -> Path:
        stem = target.stem
        suffix = target.suffix
        index = 2
        while True:
            candidate = target.with_name(f"{stem} ({index}){suffix}")
            relative_candidate = str(candidate.relative_to(output_root)).casefold()
            if not candidate.exists() and relative_candidate not in reserved:
                return candidate
            index += 1

    def change_password(self, current_password: str, new_password: str) -> None:
        if self.vault_path is None:
            raise ValueError("No vault is open.")
        verification = unlock_vault(self.vault_path, current_password)
        try:
            if self.session is not None and verification.vault_id != self.session.vault_id:
                raise ValueError("Current password is incorrect.")
            verification.change_password(new_password)
        finally:
            verification.lock()
        if self.session is not None:
            self.session.lock()
            self.session = None

    def temporary_video_path(self, vault_path: str) -> Path:
        session = self._session()
        suffix = Path(vault_path).suffix
        descriptor, name = tempfile.mkstemp(prefix="pault-preview-", suffix=suffix)
        os.close(descriptor)
        temporary_path = Path(name)
        try:
            session.export_file(vault_path, temporary_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        self._temporary_media.add(temporary_path)
        return temporary_path

    def _session(self) -> VaultSession:
        if not self.check_available():
            raise ValueError("Vault is locked or unavailable.")
        assert self.session is not None
        return self.session