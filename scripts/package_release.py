from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((repository_root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = project["version"]
    distribution_root = repository_root / "dist"
    portable_directory = distribution_root / "PAULT"
    required_paths = (
        portable_directory / "PAULT.exe",
        portable_directory / "_internal",
        portable_directory / "Vaults",
        portable_directory / "_internal" / "pault_desktop" / "assets" / "pault_logo.png",
    )
    missing_paths = [path.relative_to(repository_root) for path in required_paths if not path.exists()]
    if missing_paths:
        raise SystemExit("Build the portable application first; missing: " + ", ".join(map(str, missing_paths)))

    if any((portable_directory / "Vaults").rglob("*.pault")):
        raise SystemExit("Refusing to package a vault found in the release Vaults directory.")

    forbidden_names = {".env", ".envrc", ".netrc", ".pypirc", "pault.ini", "vault.json", "id_rsa", "id_ed25519"}
    forbidden_prefixes = (".env.", "credentials.", "secrets.")
    forbidden_suffixes = {".pault", ".paultobj", ".log", ".sqlite", ".sqlite3", ".db", ".key", ".pem", ".p12", ".pfx"}
    for path in portable_directory.rglob("*"):
        name = path.name.casefold()
        if path.is_file() and (name in forbidden_names or name.startswith(forbidden_prefixes) or path.suffix.casefold() in forbidden_suffixes):
            raise SystemExit(f"Refusing to package local data: {path.relative_to(repository_root)}")

    archive_path = distribution_root / f"PAULT-v{version}-windows-x64.zip"
    temporary_archive = archive_path.with_suffix(archive_path.suffix + ".tmp")
    try:
        with ZipFile(temporary_archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(portable_directory.rglob("*")):
                archive_name = path.relative_to(distribution_root).as_posix()
                if path.is_dir():
                    archive.writestr(archive_name.rstrip("/") + "/", "")
                elif path.is_file():
                    archive.write(path, archive_name)

        with ZipFile(temporary_archive, "r") as archive:
            names = set(archive.namelist())
            expected_entries = {
                "PAULT/PAULT.exe",
                "PAULT/_internal/",
                "PAULT/Vaults/",
                "PAULT/_internal/pault_desktop/assets/pault_logo.png",
            }
            if not expected_entries.issubset(names):
                raise SystemExit("Release archive is missing expected portable application entries.")
            if any(name.endswith(".pault") or name.endswith(".paultobj") for name in names):
                raise SystemExit("Release archive unexpectedly contains vault data.")

        temporary_archive.replace(archive_path)
    finally:
        temporary_archive.unlink(missing_ok=True)

    print(f"Release archive created: {archive_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())