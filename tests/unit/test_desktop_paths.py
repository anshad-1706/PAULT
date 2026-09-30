import shutil
import sys
from pathlib import Path

import pytest

from pault_core.vault import create_vault
from pault_desktop.paths import application_directory, default_vaults_directory, logo_resource_path, recovered_export_directory, resource_path, settings_file, validate_vault_destination, vault_directory_path
from pault_desktop.service import VaultService


def test_vault_can_be_created_and_opened_outside_repository(tmp_path):
    vault_path = tmp_path / "usb" / "PAULT" / "Vaults" / "Personal.pault"
    service = VaultService()

    service.create(vault_path, "StrongPass!123")
    assert service.vault_path == vault_path.resolve()
    service.lock()

    service.unlock(vault_path, "StrongPass!123")
    assert service.unlocked
    service.lock()


def test_vault_location_validation_rejects_relative_files_and_existing_vaults(tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        validate_vault_destination("relative-vault.pault")

    file_path = tmp_path / "not-a-directory"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="file"):
        validate_vault_destination(file_path)

    existing_vault = tmp_path / "existing.pault"
    create_vault(existing_vault, "StrongPass!123").close()
    with pytest.raises(FileExistsError, match="already contains a PAULT vault"):
        validate_vault_destination(existing_vault)


def test_vault_name_builds_absolute_pault_path_and_rejects_windows_names(tmp_path):
    assert vault_directory_path(tmp_path, "Personal") == (tmp_path / "Personal.pault").resolve()
    assert vault_directory_path(tmp_path, "Personal.PAULT") == (tmp_path / "Personal.PAULT").resolve()
    for invalid_name in ("", "..", "bad/name", "bad?name", "CON", "NUL.txt.pault", "LPT1.pault"):
        with pytest.raises(ValueError):
            vault_directory_path(tmp_path, invalid_name)


def test_vault_cannot_be_created_inside_another_vault(tmp_path):
    outer = tmp_path / "outer.pault"
    create_vault(outer, "StrongPass!123").close()

    with pytest.raises(ValueError, match="inside another PAULT vault"):
        validate_vault_destination(outer / "nested.pault")


def test_low_free_space_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr("pault_desktop.paths.shutil.disk_usage", lambda _path: shutil._ntuple_diskusage(10, 9, 1))

    with pytest.raises(OSError, match="Not enough storage"):
        validate_vault_destination(tmp_path / "new-vault", minimum_free_bytes=1024)


def test_portable_runtime_paths_follow_executable_directory(monkeypatch, tmp_path):
    executable = tmp_path / "PAULT" / "PAULT.exe"
    executable.parent.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert application_directory() == executable.parent
    assert default_vaults_directory() == executable.parent / "Vaults"
    assert settings_file() == executable.parent / "pault.ini"


def test_recovered_export_directory_uses_current_vault_volume(tmp_path):
    vault_path = tmp_path / "USB-ROOT" / "PAULT" / "Vaults" / "Personal.pault"
    assert recovered_export_directory(vault_path) == Path(vault_path.anchor) / "Recovered PAULTs"


def test_resource_path_uses_source_root_and_frozen_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    source_asset = logo_resource_path()
    assert source_asset.is_absolute()
    assert source_asset.parts[-3:] == ("pault_desktop", "assets", "pault_logo.png")

    bundle = tmp_path / "_internal"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert logo_resource_path() == bundle / "pault_desktop" / "assets" / "pault_logo.png"


def test_missing_vault_invalidates_session_and_reconnection_stays_locked(tmp_path):
    service = VaultService()
    vault_path = tmp_path / "removable" / "Personal.pault"
    service.create(vault_path, "StrongPass!123")
    manifest = (vault_path / "vault.json").read_bytes()
    (vault_path / "vault.json").unlink()

    assert not service.check_available()
    assert not service.unlocked

    (vault_path / "vault.json").write_bytes(manifest)
    assert not service.unlocked
    service.unlock(vault_path, "StrongPass!123")
    assert service.unlocked
    service.lock()


def test_temporary_video_copy_is_outside_vault_and_removed_on_lock(tmp_path):
    service = VaultService()
    vault_path = tmp_path / "vault"
    service.create(vault_path, "StrongPass!123")
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"temporary playback data")
    service.import_plan(service.plan_import([source]))

    temporary_path = service.temporary_video_path("clip.mp4")
    assert temporary_path.read_bytes() == source.read_bytes()
    assert vault_path not in temporary_path.parents
    service.lock()
    assert not temporary_path.exists()