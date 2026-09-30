import hashlib

import pytest

from pault_desktop.service import VaultService


def test_service_plans_imports_and_exports_without_changing_source(tmp_path):
    source_folder = tmp_path / "camera"
    (source_folder / "nested").mkdir(parents=True)
    source_file = source_folder / "nested" / "旅行.jpg"
    source_file.write_bytes(b"photo bytes" * 500)
    service = VaultService()
    service.create(tmp_path / "vault", "StrongPass!123")

    plan = service.plan_import([source_folder])
    assert len(plan.files) == 1
    assert plan.total_size == source_file.stat().st_size
    service.import_plan(plan)

    exported = tmp_path / "exported.jpg"
    service.export_file("camera/nested/旅行.jpg", exported)
    assert hashlib.sha256(exported.read_bytes()).digest() == hashlib.sha256(source_file.read_bytes()).digest()
    assert source_file.exists()
    service.lock()


def test_service_rejects_duplicate_and_symbolic_link_imports(tmp_path):
    service = VaultService()
    service.create(tmp_path / "vault", "StrongPass!123")
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"photo")
    service.plan_import([source])
    service.import_plan(service.plan_import([source]))

    with pytest.raises(FileExistsError):
        service.plan_import([source])

    link = tmp_path / "linked.jpg"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic links are unavailable in this environment.")
    with pytest.raises(ValueError, match="Symbolic links"):
        service.plan_import([link])
    service.lock()


def test_folder_export_preserves_structure_and_manifest(tmp_path):
    vault_path = tmp_path / "vault"
    service = VaultService()
    service.create(vault_path, "StrongPass!123")
    service.create_folder("Family Photos/2025")
    service.session.put_file("Family Photos/one.jpg", b"one" * 100)
    service.session.put_file("Family Photos/2025/two.jpg", b"two" * 100)
    manifest_before = (vault_path / "vault.json").read_bytes()
    destination = tmp_path / "Recovered PAULTs"

    plan = service.plan_export(["Family Photos"], destination)
    assert len(plan.files) == 2
    assert plan.total_size == 600
    exported = service.export_plan(plan, destination)

    assert (destination / "Family Photos" / "one.jpg").read_bytes() == b"one" * 100
    assert (destination / "Family Photos" / "2025" / "two.jpg").read_bytes() == b"two" * 100
    assert all(path.is_file() for path in exported)
    assert (vault_path / "vault.json").read_bytes() == manifest_before
    service.lock()


def test_export_conflict_keep_both_and_reject_vault_destination(tmp_path):
    vault_path = tmp_path / "vault"
    service = VaultService()
    service.create(vault_path, "StrongPass!123")
    service.session.put_file("photo.jpg", b"secret image bytes")
    destination = tmp_path / "Recovered PAULTs"
    destination.mkdir()
    (destination / "photo.jpg").write_bytes(b"preexisting export")
    plan = service.plan_export(["photo.jpg"], destination)

    with pytest.raises(FileExistsError):
        service.export_plan(plan, destination)
    exported = service.export_plan(plan, destination, conflict_policy="keep-both")
    assert exported == [destination / "photo (2).jpg"]
    assert exported[0].read_bytes() == b"secret image bytes"
    replaced = service.export_plan(plan, destination, conflict_policy="replace")
    assert replaced == [destination / "photo.jpg"]
    assert replaced[0].read_bytes() == b"secret image bytes"

    with pytest.raises(ValueError, match="outside the encrypted vault"):
        service.plan_export(["photo.jpg"], vault_path)
    service.lock()


def test_batch_export_keeps_both_when_selected_files_share_a_basename(tmp_path):
    service = VaultService()
    service.create(tmp_path / "vault", "StrongPass!123")
    service.session.put_file("first/shared.jpg", b"first image")
    service.session.put_file("second/shared.jpg", b"second image")
    destination = tmp_path / "Recovered PAULTs"
    plan = service.plan_export(["first/shared.jpg", "second/shared.jpg"], destination)

    exported = service.export_plan(plan, destination, conflict_policy="keep-both")

    assert [path.name for path in exported] == ["shared.jpg", "shared (2).jpg"]
    assert [path.read_bytes() for path in exported] == [b"first image", b"second image"]
    service.lock()