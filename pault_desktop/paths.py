from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


MINIMUM_FREE_BYTES = 1024 * 1024
_INVALID_NAME_CHARACTERS = set('<>:"/\\|?*')
_RESERVED_WINDOWS_NAMES = {"con", "prn", "aux", "nul", *(f"com{index}" for index in range(1, 10)), *(f"lpt{index}" for index in range(1, 10))}


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_path(relative_path: str | Path) -> Path:
    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", application_directory()))
    else:
        root = Path(__file__).resolve().parents[1]
    return root / relative_path


def logo_resource_path() -> Path:
    return resource_path("pault_desktop/assets/pault_logo.png")


def default_vaults_directory() -> Path:
    if getattr(sys, "frozen", False):
        return application_directory() / "Vaults"
    return Path.home() / "PAULT" / "Vaults"


def settings_file() -> Path:
    if getattr(sys, "frozen", False):
        return application_directory() / "pault.ini"
    return Path.home() / ".pault" / "pault.ini"


def recovered_export_directory(vault_path: str | Path) -> Path:
    resolved = Path(vault_path).resolve()
    return Path(resolved.anchor) / "Recovered PAULTs"


def existing_picker_directory(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate if candidate.is_dir() else Path.home()


def vault_directory_path(parent: str | Path, name: str) -> Path:
    cleaned_name = name.strip()
    if not cleaned_name or cleaned_name in {".", ".."} or any(character in _INVALID_NAME_CHARACTERS or ord(character) < 32 for character in cleaned_name) or cleaned_name.endswith((".", " ")):
        raise ValueError("Enter a valid vault name without path separators or reserved characters.")
    stem = cleaned_name[:-6] if cleaned_name.casefold().endswith(".pault") else cleaned_name
    if stem.split(".", 1)[0].casefold() in _RESERVED_WINDOWS_NAMES:
        raise ValueError("That name is reserved by Windows.")
    parent_path = Path(parent).expanduser()
    if not parent_path.is_absolute():
        raise ValueError("Choose an absolute parent folder for the vault.")
    filename = cleaned_name if cleaned_name.lower().endswith(".pault") else f"{cleaned_name}.pault"
    return (parent_path / filename).resolve(strict=False)


def validate_vault_destination(path: str | Path, *, minimum_free_bytes: int = MINIMUM_FREE_BYTES) -> Path:
    destination = Path(path).expanduser()
    if not destination.is_absolute():
        raise ValueError("Choose an absolute vault location.")

    try:
        destination = destination.resolve(strict=False)
        if destination.exists():
            if not destination.is_dir():
                raise ValueError("That location is a file, not a folder.")
            if (destination / "vault.json").is_file():
                raise FileExistsError("That location already contains a PAULT vault.")
            if any(destination.iterdir()):
                raise FileExistsError("Choose an empty folder for the new vault.")

        for ancestor in destination.parents:
            if (ancestor / "vault.json").is_file():
                raise ValueError("A vault cannot be created inside another PAULT vault.")

        probe_directory = next((parent for parent in (destination, *destination.parents) if parent.exists()), None)
        if probe_directory is None or not probe_directory.is_dir():
            raise ValueError("That location is not accessible.")
        with tempfile.NamedTemporaryFile(prefix=".pault-write-test-", dir=probe_directory, delete=True):
            pass
        if shutil.disk_usage(probe_directory).free < minimum_free_bytes:
            raise OSError("Not enough storage available.")
    except FileExistsError:
        raise
    except ValueError:
        raise
    except OSError as error:
        if "Not enough storage" in str(error):
            raise
        raise PermissionError("Unable to write to this location.") from error
    return destination
