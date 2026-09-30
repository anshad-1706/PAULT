import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from pault_desktop.app import MainWindow
from pault_desktop.gallery import MediaGrid
from pault_desktop.paths import logo_resource_path


_APP = QApplication.instance() or QApplication([])


def make_png_bytes():
    image = QImage(40, 24, QImage.Format.Format_RGB32)
    image.fill(QColor("#c8a45c"))
    data = QByteArray()
    buffer = QBuffer(data)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def test_grid_supports_multi_selection_and_distinct_folder_video_tiles():
    grid = MediaGrid(lambda _path: b"")
    grid.set_entries([
        {"path": "Family", "kind": "folder"},
        {"path": "birthday.mp4", "kind": "file", "size": 10},
    ])

    assert grid.count() == 2
    grid.item(0).setSelected(True)
    grid.item(1).setSelected(True)
    assert set(grid.selected_paths) == {"Family", "birthday.mp4"}
    assert not grid.item(0).icon().isNull()
    assert not grid.item(1).icon().isNull()


def test_supplied_logo_resource_loads_and_is_used_as_window_icon():
    logo_path = logo_resource_path()
    logo = QPixmap(str(logo_path))
    window = MainWindow()

    assert logo_path.is_file()
    assert logo.size().width() == 1254
    assert logo.size().height() == 1254
    assert not window.windowIcon().isNull()
    assert window.logo_path == logo_path
    window.close()


def test_security_settings_dialog_uses_official_branding(monkeypatch):
    window = MainWindow()
    dialogs = []

    def capture_dialog(dialog):
        dialogs.append(dialog)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", capture_dialog)
    window.open_security_settings()
    dialog = dialogs[0]
    brand = dialog.findChild(QLabel, "settingsBrand")
    logo_labels = [label for label in brand.parentWidget().findChildren(QLabel) if label is not brand]

    assert not dialog.windowIcon().isNull()
    assert any(label.pixmap() is not None and not label.pixmap().isNull() for label in logo_labels)
    window.close()


def test_image_thumbnail_is_generated_in_memory_without_disk_cache(tmp_path):
    original_files = set(tmp_path.iterdir())
    grid = MediaGrid(lambda _path: make_png_bytes())

    thumbnail = grid._make_thumbnail("holiday.png", {"size": 128})

    assert not thumbnail.isNull()
    assert set(tmp_path.iterdir()) == original_files


def test_viewer_and_selection_export_controls_dispatch_selected_paths(tmp_path):
    window = MainWindow()
    window.show()
    window.grid.set_entries([
        {"path": "one.png", "kind": "file", "size": 12},
        {"path": "two.png", "kind": "file", "size": 24},
    ])
    dispatched = []
    window.begin_export = lambda paths, destination=None: dispatched.append((paths, destination))
    window.grid.item(0).setSelected(True)
    window.grid.item(1).setSelected(True)
    window.selection_export_button.click()
    assert dispatched[-1][0] == ["one.png", "two.png"]

    window.viewer_path = "one.png"
    window.viewer_export_button.click()
    assert dispatched[-1][0] == ["one.png"]
    window.close()


def test_missing_storage_locks_and_clears_gallery_and_viewer_state(tmp_path):
    window = MainWindow()
    window.show()
    vault_path = tmp_path / "Personal.pault"
    window.active_path = vault_path
    window.service.create(vault_path, "StrongPass!123")
    window.grid.set_entries([{"path": "private.jpg", "kind": "file", "size": 10}])
    window._browser_entries = [{"path": "private.jpg", "kind": "file", "size": 10}]
    window.viewer_path = "private.jpg"
    window.viewer_image_paths = ["private.jpg"]
    window.viewer_source_pixmap = QPixmap(8, 8)
    (vault_path / "vault.json").unlink()

    window.check_auto_lock_and_storage()

    assert not window.service.unlocked
    assert window.grid.count() == 0
    assert window.viewer_path is None
    assert window.viewer_source_pixmap is None
    assert window.stack.currentWidget() is window.unlock_page
    window.close()


def test_search_results_remain_in_the_visual_grid(tmp_path):
    window = MainWindow()
    window.show()
    window.active_path = tmp_path / "Personal.pault"
    window.service.create(window.active_path, "StrongPass!123")
    window.service.create_folder("Family")
    window.service.session.put_file("Family/notes.txt", b"private note")
    window.show_browser()
    window.search.setText("Family")

    assert window.grid.count() == 2
    assert {window.grid.item(index).text() for index in range(window.grid.count())} == {"Family", "notes.txt"}
    window.lock_vault()
    window.close()
