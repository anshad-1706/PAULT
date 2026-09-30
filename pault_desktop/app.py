from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QSettings, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .gallery import IMAGE_SUFFIXES, VIDEO_SUFFIXES, MediaGrid
from .paths import default_vaults_directory, existing_picker_directory, logo_resource_path, recovered_export_directory, settings_file, vault_directory_path
from .service import VaultService


PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}


def add_brand_row(parent_layout, logo_path: Path, object_name: str, logo_size: int) -> None:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    if logo_path.is_file():
        logo = QLabel()
        logo.setPixmap(QPixmap(str(logo_path)).scaled(logo_size, logo_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setFixedSize(logo_size, logo_size)
        layout.addWidget(logo)
    wordmark = QLabel("PAULT")
    wordmark.setObjectName(object_name)
    layout.addWidget(wordmark)
    layout.addStretch()
    parent_layout.addWidget(row)


class CreateVaultDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Create your PAULT Vault")
        self.setMinimumWidth(460)
        logo_path = logo_resource_path()
        if logo_path.is_file():
            self.setWindowIcon(QIcon(str(logo_path)))
        layout = QVBoxLayout(self)
        add_brand_row(layout, logo_path, "welcomeBrand", 48)
        form = QFormLayout()
        self.name = QLineEdit("Personal")
        self.name.textChanged.connect(self.update_final_path)
        form.addRow("Vault name", self.name)
        self.location = QLineEdit()
        self.location.setText(str(default_vaults_directory()))
        self.location.textChanged.connect(self.update_final_path)
        self.location.setPlaceholderText("Choose a parent folder")
        browse = QPushButton("Browse")
        browse.clicked.connect(self.choose_location)
        location_row = QHBoxLayout()
        location_row.addWidget(self.location, 1)
        location_row.addWidget(browse)
        form.addRow("Location", location_row)
        layout.addLayout(form)
        self.final_path = QLabel()
        self.final_path.setWordWrap(True)
        self.final_path.setObjectName("statusText")
        layout.addWidget(QLabel("Vault will be created at:"))
        layout.addWidget(self.final_path)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.textChanged.connect(self.update_strength)
        form.addRow("Password", self.password)
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Confirm password", self.confirmation)
        self.strength = QLabel("Password strength: not set")
        layout.addWidget(self.strength)
        warning = QLabel("If you forget this password, PAULT cannot recover your encrypted data.")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.acknowledgement = QCheckBox("I understand that there is no password recovery.")
        layout.addWidget(self.acknowledgement)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create Vault")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_final_path()

    def choose_location(self) -> None:
        start = existing_picker_directory(self.location.text() or default_vaults_directory())
        path = QFileDialog.getExistingDirectory(self, "Choose vault parent folder", str(start), QFileDialog.Option.ShowDirsOnly)
        if path:
            self.location.setText(path)

    def update_final_path(self, *_args: object) -> None:
        try:
            self.final_path.setText(str(vault_directory_path(self.location.text(), self.name.text())))
        except ValueError:
            self.final_path.setText("Choose a valid vault name and an absolute parent folder.")

    @property
    def destination(self) -> Path:
        return vault_directory_path(self.location.text(), self.name.text())

    def update_strength(self, password: str) -> None:
        categories = sum((any(char.islower() for char in password), any(char.isupper() for char in password), any(char.isdigit() for char in password), any(not char.isalnum() for char in password)))
        strength = "Strong" if len(password) >= 14 and categories >= 3 else "Fair" if len(password) >= 10 and categories >= 2 else "Weak"
        self.strength.setText(f"Password strength: {strength}")

    def validate_and_accept(self) -> None:
        try:
            self.destination
        except ValueError as error:
            QMessageBox.warning(self, "Vault location", str(error))
            return
        if not self.location.text().strip():
            QMessageBox.warning(self, "Location required", "Choose where to create the vault.")
        elif len(self.password.text()) < 10:
            QMessageBox.warning(self, "Password too short", "Choose a password with at least 10 characters.")
        elif self.password.text() != self.confirmation.text():
            QMessageBox.warning(self, "Passwords do not match", "Enter the same password in both fields.")
        elif not self.acknowledgement.isChecked():
            QMessageBox.warning(self, "Acknowledgement required", "Confirm that there is no password recovery.")
        else:
            self.accept()


class PasswordChangeDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Change PAULT Password")
        logo_path = logo_resource_path()
        if logo_path.is_file():
            self.setWindowIcon(QIcon(str(logo_path)))
        form = QFormLayout(self)
        self.current = QLineEdit()
        self.current.setEchoMode(QLineEdit.EchoMode.Password)
        self.new = QLineEdit()
        self.new.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Current password", self.current)
        form.addRow("New password", self.new)
        form.addRow("Confirm new password", self.confirm)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Change Password")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def validate_and_accept(self) -> None:
        if not self.current.text():
            QMessageBox.warning(self, "Current password required", "Enter your current password.")
        elif len(self.new.text()) < 10:
            QMessageBox.warning(self, "Password too short", "Choose a password with at least 10 characters.")
        elif self.new.text() != self.confirm.text():
            QMessageBox.warning(self, "Passwords do not match", "Enter the same new password twice.")
        else:
            self.accept()


class TaskWorker(QObject):
    progress = Signal(int, int)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[Callable[[int, int], None]], object]) -> None:
        super().__init__()
        self.operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self.operation(lambda done, total: self.progress.emit(done, total)))
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PAULT | Portable Offline Encrypted USB Vault")
        self.logo_path = logo_resource_path()
        if self.logo_path.is_file():
            self.setWindowIcon(QIcon(str(self.logo_path)))
        self.resize(1080, 720)
        self.setMinimumSize(800, 560)
        self.setAcceptDrops(True)
        self.service = VaultService()
        portable_settings = settings_file()
        try:
            portable_settings.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        self.settings = QSettings(str(portable_settings), QSettings.Format.IniFormat)
        self.active_path: Path | None = None
        self.pending_drop: list[Path] = []
        self.current_folder = ""
        self.category = "all"
        self._busy = False
        self._thread: QThread | None = None
        self._worker: TaskWorker | None = None
        self._completion: Callable[[object], None] | None = None
        self._task_started_unlocked = False
        self._last_activity = time.monotonic()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self._build_welcome()
        self._build_unlock()
        self._build_browser()
        self._build_image_viewer()
        self.stack.setCurrentWidget(self.welcome_page)
        self.setStyleSheet(self._style_sheet())

        self.activity_timer = QTimer(self)
        self.activity_timer.setInterval(2000)
        self.activity_timer.timeout.connect(self.check_auto_lock_and_storage)
        self.activity_timer.start()
        QApplication.instance().installEventFilter(self)

    def add_brand(self, parent_layout: QVBoxLayout, object_name: str, logo_size: int) -> None:
        add_brand_row(parent_layout, self.logo_path, object_name, logo_size)

    def _build_welcome(self) -> None:
        self.welcome_page = QWidget()
        layout = QVBoxLayout(self.welcome_page)
        layout.setContentsMargins(72, 56, 72, 56)
        layout.addStretch(2)
        self.add_brand(layout, "welcomeBrand", 56)
        subtitle = QLabel("Portable Offline Encrypted USB Vault")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        headline = QLabel("Your private files.\nEncrypted. Offline. Yours.")
        headline.setObjectName("welcomeHeadline")
        layout.addWidget(headline)
        actions = QHBoxLayout()
        create = QPushButton("Create New Vault")
        create.setObjectName("primaryButton")
        create.clicked.connect(self.create_vault)
        open_existing = QPushButton("Open Existing Vault")
        open_existing.clicked.connect(self.choose_existing_vault)
        actions.addWidget(create)
        actions.addWidget(open_existing)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch(3)
        self.stack.addWidget(self.welcome_page)

    def _build_unlock(self) -> None:
        self.unlock_page = QWidget()
        layout = QVBoxLayout(self.unlock_page)
        layout.setContentsMargins(72, 48, 72, 48)
        layout.addStretch(2)
        self.add_brand(layout, "welcomeBrand", 56)
        title = QLabel("Vault Locked")
        title.setObjectName("welcomeHeadline")
        layout.addWidget(title)
        self.vault_label = QLabel()
        self.vault_label.setObjectName("subtitle")
        layout.addWidget(self.vault_label)
        self.unlock_password = QLineEdit()
        self.unlock_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.unlock_password.setPlaceholderText("Password")
        self.unlock_password.returnPressed.connect(self.unlock_vault)
        self.unlock_password.setMaximumWidth(440)
        layout.addWidget(self.unlock_password)
        actions = QHBoxLayout()
        self.unlock_button = QPushButton("Unlock")
        self.unlock_button.setObjectName("primaryButton")
        self.unlock_button.clicked.connect(self.unlock_vault)
        actions.addWidget(self.unlock_button)
        change_password = QPushButton("Change Password")
        change_password.clicked.connect(self.change_password)
        actions.addWidget(change_password)
        another = QPushButton("Open Another Vault")
        another.clicked.connect(self.choose_existing_vault)
        actions.addWidget(another)
        actions.addStretch()
        layout.addLayout(actions)
        self.unlock_status = QLabel("")
        self.unlock_status.setObjectName("statusText")
        layout.addWidget(self.unlock_status)
        layout.addStretch(3)
        self.stack.addWidget(self.unlock_page)

    def _build_browser(self) -> None:
        self.browser_page = QWidget()
        root = QHBoxLayout(self.browser_page)
        root.setContentsMargins(0, 0, 0, 0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(20, 24, 16, 20)
        self.add_brand(side_layout, "sideBrand", 38)
        self.vault_name = QLabel("Vault")
        self.vault_name.setObjectName("sideVault")
        side_layout.addWidget(self.vault_name)
        side_layout.addSpacing(24)
        self.sidebar_buttons = {}
        for label, category in (("Home", "all"), ("Photos", "photos"), ("Videos", "videos"), ("Folders", "folders"), ("Recent", "recent")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=category: self.set_category(value))
            side_layout.addWidget(button)
            self.sidebar_buttons[category] = button
        side_layout.addStretch()
        self.security_button = QPushButton("Security Settings")
        self.security_button.clicked.connect(self.open_security_settings)
        side_layout.addWidget(self.security_button)
        root.addWidget(sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(28, 22, 28, 24)
        top = QHBoxLayout()
        self.vault_title = QLabel("Vault")
        self.vault_title.setObjectName("pageTitle")
        top.addWidget(self.vault_title)
        top.addStretch()
        self.lock_button = QPushButton("Lock Vault")
        self.lock_button.clicked.connect(self.lock_vault)
        top.addWidget(self.lock_button)
        content.addLayout(top)
        security_state = QLabel("UNLOCKED")
        security_state.setObjectName("securityState")
        content.addWidget(security_state)

        toolbar = QHBoxLayout()
        add_files = QPushButton("+ Add Files")
        add_files.clicked.connect(self.add_files)
        toolbar.addWidget(add_files)
        new_folder = QPushButton("+ New Folder")
        new_folder.clicked.connect(self.create_folder)
        toolbar.addWidget(new_folder)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search photos, videos, folders")
        self.search.textChanged.connect(self.refresh_browser)
        toolbar.addWidget(self.search, 1)
        toolbar.addWidget(QLabel("Sort"))
        self.sort_control = QComboBox()
        for label, key in (("Name", "name"), ("Date added", "date"), ("Type", "type"), ("Size", "size")):
            self.sort_control.addItem(label, key)
        self.sort_control.currentIndexChanged.connect(self.refresh_browser)
        toolbar.addWidget(self.sort_control)
        toolbar.addWidget(QLabel("Grid"))
        self.grid_size_control = QComboBox()
        for label, key in (("Small", "small"), ("Medium", "medium"), ("Large", "large")):
            self.grid_size_control.addItem(label, key)
        self.grid_size_control.setCurrentIndex(1)
        self.grid_size_control.currentIndexChanged.connect(lambda: self.grid.set_density(self.grid_size_control.currentData()))
        toolbar.addWidget(self.grid_size_control)
        content.addLayout(toolbar)

        self.breadcrumb_layout = QHBoxLayout()
        self.breadcrumb_layout.setSpacing(6)
        content.addLayout(self.breadcrumb_layout)

        self.selection_toolbar = QWidget()
        selection_layout = QHBoxLayout(self.selection_toolbar)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        self.selection_count = QLabel("0 selected")
        selection_layout.addWidget(self.selection_count, 1)
        self.selection_export_button = QPushButton("Export")
        self.selection_export_button.setObjectName("primaryButton")
        self.selection_export_button.clicked.connect(self.export_selected)
        selection_layout.addWidget(self.selection_export_button)
        self.selection_delete_button = QPushButton("Delete")
        self.selection_delete_button.clicked.connect(self.delete_selected)
        selection_layout.addWidget(self.selection_delete_button)
        cancel_selection = QPushButton("Cancel Selection")
        cancel_selection.clicked.connect(lambda: self.grid.clearSelection())
        selection_layout.addWidget(cancel_selection)
        self.selection_toolbar.hide()
        content.addWidget(self.selection_toolbar)

        self.grid = MediaGrid(self.service.read_file, self.browser_page)
        self.grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self.open_context_menu)
        self.grid.itemDoubleClicked.connect(self.activate_item)
        self.grid.itemSelectionChanged.connect(self.update_selection_toolbar)
        content.addWidget(self.grid, 1)
        self.empty_state = QLabel("This folder is empty\n\nDrag photos and videos here, or use Add Files.")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setObjectName("emptyState")
        self.empty_state.hide()
        content.addWidget(self.empty_state, 1)
        self.load_more_button = QPushButton("Load more")
        self.load_more_button.clicked.connect(self.load_more_entries)
        self.load_more_button.hide()
        content.addWidget(self.load_more_button)
        self.status_label = QLabel("Vault unlocked")
        self.status_label.setObjectName("statusText")
        content.addWidget(self.status_label)
        root.addLayout(content, 1)
        self.stack.addWidget(self.browser_page)

    def _build_image_viewer(self) -> None:
        self.viewer_page = QWidget()
        layout = QVBoxLayout(self.viewer_page)
        layout.setContentsMargins(24, 18, 24, 20)
        toolbar = QHBoxLayout()
        back = QPushButton("Back")
        back.clicked.connect(self.return_to_grid)
        toolbar.addWidget(back)
        add_brand_row(toolbar, self.logo_path, "sideBrand", 30)
        self.viewer_title = QLabel()
        self.viewer_title.setObjectName("pageTitle")
        toolbar.addWidget(self.viewer_title, 1)
        self.viewer_previous = QPushButton("Previous")
        self.viewer_previous.clicked.connect(lambda: self.step_image(-1))
        toolbar.addWidget(self.viewer_previous)
        self.viewer_next = QPushButton("Next")
        self.viewer_next.clicked.connect(lambda: self.step_image(1))
        toolbar.addWidget(self.viewer_next)
        self.viewer_export_button = QPushButton("Export")
        self.viewer_export_button.setObjectName("primaryButton")
        self.viewer_export_button.clicked.connect(self.export_viewed_image)
        toolbar.addWidget(self.viewer_export_button)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete_viewed_image)
        toolbar.addWidget(delete)
        layout.addLayout(toolbar)
        self.viewer_image = QLabel()
        self.viewer_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_image.setObjectName("viewerImage")
        layout.addWidget(self.viewer_image, 1)
        self.viewer_path: str | None = None
        self.viewer_image_paths: list[str] = []
        self.viewer_source_pixmap: QPixmap | None = None
        self.stack.addWidget(self.viewer_page)

    def _style_sheet(self) -> str:
        return """
            QWidget { background: #22282b; color: #eceeeb; font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif; font-size: 10pt; }
            #sidebar { background: #191e21; color: #f1f2ef; }
            #sideBrand { color: #f2f3f0; font-size: 22pt; font-weight: 700; }
            #sideVault { color: #aeb8b9; }
            #settingsBrand { color: #c8a45f; font-size: 13pt; font-weight: 700; }
            #sidebar QPushButton { background: transparent; color: #d7dddc; border: 0; text-align: left; padding: 10px 12px; }
            #sidebar QPushButton:checked, #sidebar QPushButton:hover { background: #30383b; color: #ffffff; }
            QPushButton { background: #30383b; border: 1px solid #485256; border-radius: 5px; padding: 9px 14px; }
            QPushButton:hover { background: #394347; border-color: #a88b55; }
            QPushButton:disabled { color: #818b8d; }
            #primaryButton { background: #a4864f; border-color: #b99b61; color: #111619; font-weight: 650; padding: 11px 18px; }
            #primaryButton:hover { background: #c2a366; }
            QLineEdit { background: #2c3336; border: 1px solid #4a5458; border-radius: 4px; padding: 10px; color: #f0f1ee; }
            QComboBox { background: #2c3336; border: 1px solid #4a5458; border-radius: 4px; padding: 7px 10px; color: #f0f1ee; }
            QComboBox QAbstractItemView { background: #2c3336; selection-background-color: #4a4436; }
            QListWidget { background: #22282b; border: 0; outline: 0; }
            QListWidget::item { background: #2d3437; border: 1px solid #3e494d; border-radius: 8px; padding: 8px; color: #eceeeb; }
            QListWidget::item:hover { background: #343d40; border-color: #a88b55; }
            QListWidget::item:selected { background: #39362f; border: 2px solid #c0a064; color: #f3f1e9; }
            #welcomeBrand { color: #c8a45f; font-size: 19pt; font-weight: 700; }
            #welcomeHeadline { font-size: 26pt; font-weight: 600; margin-top: 24px; margin-bottom: 20px; }
            #subtitle, #breadcrumb { color: #aeb8b9; }
            #pageTitle { font-size: 18pt; font-weight: 600; }
            #securityState { color: #cbb078; font-size: 9pt; font-weight: 700; }
            #statusText { color: #aeb8b9; }
            #emptyState { color: #aeb8b9; font-size: 12pt; background: transparent; }
            #viewerImage { background: #151a1d; border-radius: 8px; }
            QProgressDialog { min-width: 380px; }
        """

    def create_vault(self) -> None:
        dialog = CreateVaultDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path = dialog.destination
        password = dialog.password.text()
        dialog.password.clear()
        dialog.confirmation.clear()
        self.active_path = path
        self._start_task("Creating encrypted vault", lambda _progress: self.service.create(path, password), self.show_browser)

    def choose_existing_vault(self) -> None:
        start = existing_picker_directory(default_vaults_directory())
        selected = QFileDialog.getExistingDirectory(self, "Open PAULT Vault", str(start), QFileDialog.Option.ShowDirsOnly)
        if not selected:
            return
        vault_path = Path(selected).expanduser().resolve()
        if not (vault_path / "vault.json").is_file():
            QMessageBox.warning(self, "Not a PAULT vault", "The selected folder does not contain a PAULT vault.")
            return
        self.active_path = vault_path
        self.show_unlock()

    def show_unlock(self, message: str = "") -> None:
        if self.active_path is None:
            self.stack.setCurrentWidget(self.welcome_page)
            return
        self.vault_label.setText(self.active_path.name)
        self.unlock_password.clear()
        self.unlock_status.setText(message)
        self.unlock_button.setText("Unlock & Import" if self.pending_drop else "Unlock")
        self.stack.setCurrentWidget(self.unlock_page)
        self.unlock_password.setFocus()

    def unlock_vault(self) -> None:
        if self.active_path is None:
            return
        password = self.unlock_password.text()
        self.unlock_password.clear()
        self.unlock_status.clear()
        path = self.active_path

        def unlocked(_result: object) -> None:
            self.show_browser()
            if self.pending_drop:
                sources = self.pending_drop
                self.pending_drop = []
                self.confirm_and_import(sources)

        self._start_task("Unlocking vault", lambda _progress: self.service.unlock(path, password), unlocked)

    def show_browser(self, _result: object = None) -> None:
        if not self.service.unlocked:
            return
        self.current_folder = ""
        self.category = "all"
        name = self.active_path.name if self.active_path else "Vault"
        self.vault_name.setText(name)
        self.vault_title.setText(name)
        self.stack.setCurrentWidget(self.browser_page)
        self.refresh_browser()

    def set_category(self, category: str) -> None:
        self.category = category
        if category != "all":
            self.current_folder = ""
        self.search.clear()
        for key, button in self.sidebar_buttons.items():
            button.setChecked(key == category)
        self.refresh_browser()

    def refresh_browser(self, *_args: object) -> None:
        if not self.service.unlocked:
            return
        query = self.search.text().strip()
        self.update_breadcrumbs()
        if self.category == "all" and not query:
            entries = self.service.list_entries(self.current_folder)
        else:
            entries = self.service.search_entries(query, self.category)
            if self.category == "all" and self.current_folder:
                entries = [item for item in entries if item["path"].startswith(self.current_folder + "/")]
        self._browser_entries = self._sort_entries(entries)
        self._shown_entry_count = min(120, len(self._browser_entries))
        self._populate_grid()

    def _sort_entries(self, entries: list[dict]) -> list[dict]:
        key = self.sort_control.currentData()
        if key == "date":
            return sorted(entries, key=lambda entry: entry.get("modified_at", ""), reverse=True)
        if key == "type":
            return sorted(entries, key=lambda entry: (entry.get("kind") != "folder", Path(entry["path"]).suffix.casefold(), entry["path"].casefold()))
        if key == "size":
            return sorted(entries, key=lambda entry: (entry.get("kind") != "folder", -int(entry.get("size", 0)), entry["path"].casefold()))
        return sorted(entries, key=lambda entry: (entry.get("kind") != "folder", Path(entry["path"]).name.casefold()))

    def _populate_grid(self) -> None:
        shown = self._browser_entries[:self._shown_entry_count]
        self.grid.set_entries(shown)
        self.grid.setVisible(bool(shown))
        self.empty_state.setVisible(not shown)
        self.load_more_button.setVisible(self._shown_entry_count < len(self._browser_entries))
        self.status_label.setText(f"{len(self._browser_entries)} items")
        self.update_selection_toolbar()

    def load_more_entries(self) -> None:
        self._shown_entry_count = min(len(self._browser_entries), self._shown_entry_count + 120)
        self._populate_grid()

    def update_breadcrumbs(self) -> None:
        while self.breadcrumb_layout.count():
            child = self.breadcrumb_layout.takeAt(0)
            if child.widget() is not None:
                child.widget().deleteLater()
        home = QPushButton("Home")
        home.setFlat(True)
        home.clicked.connect(lambda: self.navigate_to_folder(""))
        self.breadcrumb_layout.addWidget(home)
        accumulated = []
        for component in self.current_folder.split("/") if self.current_folder else []:
            accumulated.append(component)
            self.breadcrumb_layout.addWidget(QLabel("/"))
            path = "/".join(accumulated)
            crumb = QPushButton(component)
            crumb.setFlat(True)
            crumb.clicked.connect(lambda checked=False, target=path: self.navigate_to_folder(target))
            self.breadcrumb_layout.addWidget(crumb)
        self.breadcrumb_layout.addStretch()

    def navigate_to_folder(self, folder: str) -> None:
        self.current_folder = folder
        self.category = "all"
        self.sidebar_buttons["all"].setChecked(True)
        self.search.clear()
        self.refresh_browser()

    def update_selection_toolbar(self) -> None:
        selected_count = len(self.grid.selectedItems()) if hasattr(self, "grid") else 0
        self.selection_toolbar.setVisible(selected_count > 0)
        self.selection_count.setText(f"{selected_count} selected")

    def activate_item(self, item) -> None:
        path = str(item.data(Qt.ItemDataRole.UserRole))
        kind = item.data(Qt.ItemDataRole.UserRole + 1)
        if kind == "folder":
            self.navigate_to_folder(path)
        else:
            self.open_file(path)

    def navigate_up(self) -> None:
        if self.current_folder:
            self.navigate_to_folder(self.current_folder.rpartition("/")[0])

    def add_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(self, "Add files to PAULT", "", "All files (*)")
        if selected:
            self.confirm_and_import([Path(path) for path in selected])

    def confirm_and_import(self, sources: list[Path]) -> None:
        try:
            plan = self.service.plan_import(sources, self.current_folder if self.category == "all" else "")
        except Exception as error:
            QMessageBox.warning(self, "Import unavailable", str(error))
            return
        if not plan.files and not plan.folders:
            QMessageBox.information(self, "Nothing to import", "No files or folders were selected.")
            return
        destination = self.current_folder or "Home"
        details = f"Import {len(plan.files)} file(s), {self.format_size(plan.total_size)} total, to {destination}?\n\nOriginal files will remain unchanged."
        if QMessageBox.question(self, "Confirm import", details, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel) != QMessageBox.StandardButton.Yes:
            return
        self._start_task("Encrypting and verifying imported files", lambda progress: self.service.import_plan(plan, progress=progress), lambda _result: self.refresh_browser())

    def create_folder(self) -> None:
        name, accepted = self.get_text("New Folder", "Folder name")
        if not accepted:
            return
        if not name or "/" in name or "\\" in name:
            QMessageBox.warning(self, "Invalid folder name", "Enter a single folder name.")
            return
        path = f"{self.current_folder}/{name}" if self.current_folder else name
        try:
            self.service.create_folder(path)
            self.refresh_browser()
        except Exception as error:
            QMessageBox.warning(self, "Folder not created", str(error))

    def open_context_menu(self, position) -> None:
        item = self.grid.itemAt(position)
        if item is None:
            return
        if not item.isSelected():
            self.grid.clearSelection()
            item.setSelected(True)
        menu = QMenu(self)
        open_action = menu.addAction("Open")
        rename_action = menu.addAction("Rename")
        export_action = menu.addAction("Export")
        properties_action = menu.addAction("Properties")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.grid.viewport().mapToGlobal(position))
        path = str(item.data(Qt.ItemDataRole.UserRole))
        if action == open_action:
            self.activate_item(item)
        elif action == rename_action:
            self.rename_item(path)
        elif action == export_action:
            self.export_selected(path)
        elif action == properties_action:
            self.show_properties(path)
        elif action == delete_action:
            self.delete_item(path)

    def selected_path(self) -> str | None:
        item = self.grid.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def rename_item(self, path: str | None = None) -> None:
        path = path or self.selected_path()
        if not path:
            return
        name, accepted = self.get_text("Rename", "Name", Path(path).name)
        if not accepted:
            return
        if not name or "/" in name or "\\" in name:
            QMessageBox.warning(self, "Invalid name", "Enter a single file or folder name.")
            return
        parent = path.rpartition("/")[0]
        new_path = f"{parent}/{name}" if parent else name
        try:
            self.service.rename(path, new_path)
            self.refresh_browser()
        except Exception as error:
            QMessageBox.warning(self, "Rename failed", str(error))

    def delete_item(self, path: str | None = None) -> None:
        path = path or self.selected_path()
        if not path:
            return
        answer = QMessageBox.question(self, "Delete item", "Delete this item from the PAULT vault?", QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(path)
            self.refresh_browser()
        except Exception as error:
            QMessageBox.warning(self, "Delete failed", str(error))

    def delete_selected(self) -> None:
        paths = self.grid.selected_paths
        if not paths:
            return
        minimal_paths = [path for path in paths if not any(path.startswith(other + "/") for other in paths if other != path)]
        if QMessageBox.question(self, "Delete items", f"Delete {len(minimal_paths)} selected item(s) from the PAULT vault?", QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes) != QMessageBox.StandardButton.Yes:
            return
        try:
            for path in minimal_paths:
                self.service.delete(path)
            self.refresh_browser()
        except Exception as error:
            QMessageBox.warning(self, "Delete failed", str(error))

    def export_selected(self, path: str | None = None) -> None:
        paths = [path] if path else self.grid.selected_paths
        if not paths:
            return
        self.begin_export(paths)

    def begin_export(self, paths: list[str], destination: Path | None = None) -> None:
        if self.active_path is None:
            return
        destination = destination or recovered_export_directory(self.active_path)
        try:
            plan = self.service.plan_export(paths, destination)
        except Exception as error:
            QMessageBox.warning(self, "Export unavailable", str(error))
            return
        if not plan.files and not plan.directories:
            QMessageBox.information(self, "Export", "The selected items contain no files or folders to export.")
            return

        count = len(paths)
        if count == 1 and len(plan.files) == 1:
            prompt = f"Export this file?\n\n{Path(paths[0]).name}"
        else:
            prompt = f"Export {count} selected item(s)?"
        prompt += f"\n\nDestination:\n{destination}\n\nExported files will be outside PAULT and will no longer be protected by the vault."
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle("Confirm export")
        confirmation.setText(prompt)
        export_button = confirmation.addButton("Export", QMessageBox.ButtonRole.AcceptRole)
        choose_button = confirmation.addButton("Choose Folder...", QMessageBox.ButtonRole.ActionRole)
        confirmation.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        confirmation.exec()
        if confirmation.clickedButton() == choose_button:
            selected = QFileDialog.getExistingDirectory(self, "Choose export destination", str(existing_picker_directory(destination)))
            if selected:
                self.begin_export(paths, Path(selected))
            return
        if confirmation.clickedButton() != export_button:
            return

        policy = "cancel"
        target_counts: dict[str, int] = {}
        for item in plan.files:
            key = str(item.relative_path).casefold()
            target_counts[key] = target_counts.get(key, 0) + 1
        collisions = [item for item in plan.files if (destination / item.relative_path).exists() or target_counts[str(item.relative_path).casefold()] > 1]
        if collisions:
            collision_dialog = QMessageBox(self)
            collision_dialog.setWindowTitle("Export name already exists")
            collision_dialog.setText(f"{len(collisions)} file(s) already exist in the destination. Choose how to handle the batch.")
            replace_button = collision_dialog.addButton("Replace", QMessageBox.ButtonRole.DestructiveRole)
            keep_button = collision_dialog.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
            collision_dialog.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            collision_dialog.exec()
            if collision_dialog.clickedButton() == replace_button:
                policy = "replace"
            elif collision_dialog.clickedButton() == keep_button:
                policy = "keep-both"
            else:
                return

        self._start_task(
            "Exporting and verifying files",
            lambda progress: self.service.export_plan(plan, destination, conflict_policy=policy, progress=progress),
            lambda exported: QMessageBox.information(self, "Export complete", f"Exported {len(exported)} file(s) to:\n{destination}"),
        )

    def show_properties(self, path: str) -> None:
        entry = self.service.get_entry(path) or {}
        kind = entry.get("kind", "file").title()
        details = f"Name: {Path(path).name}\nType: {kind}\nSize: {self.format_size(entry.get('size', 0))}\nModified: {entry.get('modified_at', 'Unavailable')}"
        QMessageBox.information(self, "Properties", details)

    def _open_image_viewer(self, path: str) -> None:
        image_paths = [str(entry["path"]) for entry in getattr(self, "_browser_entries", []) if Path(entry["path"]).suffix.casefold() in IMAGE_SUFFIXES]
        self.viewer_image_paths = image_paths or [path]
        self.viewer_path = path
        self._load_viewer_image()
        self.stack.setCurrentWidget(self.viewer_page)
        QTimer.singleShot(0, self._fit_viewer_image)

    def _load_viewer_image(self) -> None:
        if self.viewer_path is None:
            return
        self.viewer_title.setText(Path(self.viewer_path).name)
        self.viewer_source_pixmap = QPixmap()
        self.viewer_source_pixmap.loadFromData(self.service.read_file(self.viewer_path))
        self._fit_viewer_image()
        index = self.viewer_image_paths.index(self.viewer_path) if self.viewer_path in self.viewer_image_paths else 0
        self.viewer_previous.setEnabled(index > 0)
        self.viewer_next.setEnabled(index + 1 < len(self.viewer_image_paths))

    def _fit_viewer_image(self) -> None:
        if self.viewer_source_pixmap is None or self.viewer_source_pixmap.isNull():
            return
        self.viewer_image.setPixmap(self.viewer_source_pixmap.scaled(self.viewer_image.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def return_to_grid(self) -> None:
        self.stack.setCurrentWidget(self.browser_page)
        self.viewer_source_pixmap = None
        self.viewer_image.clear()
        self.refresh_browser()

    def step_image(self, direction: int) -> None:
        if self.viewer_path not in self.viewer_image_paths:
            return
        index = self.viewer_image_paths.index(self.viewer_path) + direction
        if 0 <= index < len(self.viewer_image_paths):
            self.viewer_path = self.viewer_image_paths[index]
            self._load_viewer_image()

    def export_viewed_image(self) -> None:
        if self.viewer_path:
            self.begin_export([self.viewer_path])

    def delete_viewed_image(self) -> None:
        if not self.viewer_path:
            return
        path = self.viewer_path
        if QMessageBox.question(self, "Delete item", "Delete this item from the PAULT vault?", QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(path)
        except Exception as error:
            QMessageBox.warning(self, "Delete failed", str(error))
            return
        self.return_to_grid()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "viewer_page") and self.stack.currentWidget() is self.viewer_page:
            QTimer.singleShot(0, self._fit_viewer_image)

    def keyPressEvent(self, event) -> None:
        if self.stack.currentWidget() is self.viewer_page and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.step_image(-1 if event.key() == Qt.Key.Key_Left else 1)
            return
        super().keyPressEvent(event)

    def open_file(self, path: str) -> None:
        suffix = Path(path).suffix.casefold()
        if suffix in PHOTO_EXTENSIONS:
            self._open_image_viewer(path)
            if self.viewer_source_pixmap is None or self.viewer_source_pixmap.isNull():
                QMessageBox.information(self, "Preview unavailable", "This image format is not supported by the installed image plugins.")
                self.return_to_grid()
                return
        elif suffix in VIDEO_EXTENSIONS:
            QMessageBox.warning(self, "Temporary video file", "PAULT will create a temporary plaintext copy for your default video player. It is removed when you lock PAULT, but the operating system or player may retain traces.")
            try:
                temporary_path = self.service.temporary_video_path(path)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(temporary_path)))
            except Exception as error:
                QMessageBox.warning(self, "Video unavailable", str(error))
        else:
            self.export_selected(path)

    def open_security_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Security")
        dialog.setWindowIcon(QIcon(str(self.logo_path)))
        layout = QVBoxLayout(dialog)
        add_brand_row(layout, self.logo_path, "settingsBrand", 30)
        form = QFormLayout()
        auto_lock = QComboBox()
        options = (("Off", 0), ("5 minutes", 5), ("10 minutes", 10), ("15 minutes", 15), ("30 minutes", 30))
        for label, value in options:
            auto_lock.addItem(label, value)
        current = self.settings.value("auto_lock_minutes", 10, type=int)
        auto_lock.setCurrentIndex(max(0, auto_lock.findData(current)))
        form.addRow("Auto Lock", auto_lock)
        layout.addLayout(form)
        change = QPushButton("Change Password")
        change.clicked.connect(lambda: (dialog.accept(), self.change_password()))
        layout.addWidget(change)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.setValue("auto_lock_minutes", auto_lock.currentData())

    def change_password(self) -> None:
        dialog = PasswordChangeDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        current_password = dialog.current.text()
        new_password = dialog.new.text()
        dialog.current.clear()
        dialog.new.clear()
        dialog.confirm.clear()

        def changed(_result: object) -> None:
            self.service.lock()
            self.show_unlock("Password changed. Unlock with your new password.")

        self._start_task("Changing vault password", lambda _progress: self.service.change_password(current_password, new_password), changed)

    def lock_vault(self) -> None:
        if self._busy:
            return
        path = self.active_path
        self.service.lock()
        self.clear_ui_sensitive()
        self.show_unlock()
        if path is not None:
            self.unlock_status.setText("Vault locked. Your encrypted data remains on the selected storage.")

    def confirm_drop(self, sources: list[Path]) -> None:
        if not self.service.unlocked:
            self.pending_drop = sources
            if self.active_path is not None:
                self.show_unlock("Vault locked. Unlock to encrypt and import the dropped items.")
            else:
                self.stack.setCurrentWidget(self.welcome_page)
                QMessageBox.information(self, "PAULT Vault Locked", "Open a vault, then unlock it to import the dropped items.")
            return
        self.confirm_and_import(sources)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress, QEvent.Type.Wheel, QEvent.Type.MouseMove):
            self._last_activity = time.monotonic()
        if event.type() == QEvent.Type.DragEnter and event.mimeData().hasUrls():
            event.acceptProposedAction()
            return True
        if event.type() == QEvent.Type.Drop and event.mimeData().hasUrls():
            paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
            self.confirm_drop(paths)
            event.acceptProposedAction()
            return True
        return super().eventFilter(watched, event)

    def check_auto_lock_and_storage(self) -> None:
        if not self.service.unlocked or self._busy:
            return
        if not self.service.check_available():
            self.clear_ui_sensitive()
            self.show_unlock("Vault storage is unavailable. Reconnect it, then unlock again.")
            return
        minutes = self.settings.value("auto_lock_minutes", 10, type=int)
        if minutes and time.monotonic() - self._last_activity >= minutes * 60:
            self.lock_vault()

    def _start_task(self, title: str, operation: Callable[[Callable[[int, int], None]], object], completed: Callable[[object], None]) -> None:
        if self._busy:
            return
        self._busy = True
        self._task_started_unlocked = self.service.unlocked
        self.lock_button.setEnabled(False)
        self._completion = completed
        self.progress_dialog = QProgressDialog(title, "", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()
        self._thread = QThread(self)
        self._worker = TaskWorker(operation)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.update_progress)
        self._worker.completed.connect(self.task_completed)
        self._worker.failed.connect(self.task_failed)
        self._worker.completed.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    @Slot(int, int)
    def update_progress(self, completed: int, total: int) -> None:
        if total > 0:
            self.progress_dialog.setRange(0, total)
            self.progress_dialog.setValue(min(completed, total))
        else:
            self.progress_dialog.setRange(0, 0)

    @Slot(object)
    def task_completed(self, result: object) -> None:
        self.progress_dialog.close()
        self._busy = False
        self.lock_button.setEnabled(self.service.unlocked)
        self._last_activity = time.monotonic()
        callback, self._completion = self._completion, None
        if callback:
            callback(result)

    @Slot(str)
    def task_failed(self, message: str) -> None:
        self.progress_dialog.close()
        self._busy = False
        self.lock_button.setEnabled(self.service.unlocked)
        self._last_activity = time.monotonic()
        if self._task_started_unlocked and self.active_path is not None and not (self.active_path / "vault.json").is_file():
            self.service.lock()
            self.clear_ui_sensitive()
            self.show_unlock("Vault storage is unavailable. Reconnect it, then unlock again.")
        else:
            QMessageBox.warning(self, "Operation failed", message)

    @Slot()
    def _thread_finished(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
        self._worker = None
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None

    def clear_ui_sensitive(self) -> None:
        self.grid.clear_sensitive()
        self.viewer_source_pixmap = None
        self.viewer_path = None
        self.viewer_image_paths = []
        self._browser_entries = []
        self._shown_entry_count = 0
        self.viewer_image.clear()
        self.viewer_title.clear()
        self.search.clear()
        self.current_folder = ""
        self.selection_toolbar.hide()

    @staticmethod
    def get_text(title: str, label: str, default: str = "") -> tuple[str, bool]:
        from PySide6.QtWidgets import QInputDialog

        return QInputDialog.getText(None, title, label, QLineEdit.EchoMode.Normal, default)

    @staticmethod
    def format_size(size: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
            value /= 1024
        return f"{size} B"

    def closeEvent(self, event) -> None:
        if self._busy:
            QMessageBox.information(self, "Operation in progress", "Wait for the active vault operation to finish before closing PAULT.")
            event.ignore()
            return
        self.service.lock()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PAULT")
    if "--smoke-test" in sys.argv[1:]:
        from pault_core.vault import create_vault, unlock_vault

        with tempfile.TemporaryDirectory(prefix="pault-smoke-") as temporary_directory:
            password = "PortableSmokePass!123"
            payload = b"portable crypto runtime check"
            session = create_vault(Path(temporary_directory) / "smoke.pault", password)
            session.put_file("check.bin", payload)
            session.close()
            session = unlock_vault(Path(temporary_directory) / "smoke.pault", password)
            if session.read_file("check.bin") != payload:
                session.close()
                return 1
            session.close()
    window = MainWindow()
    window.show()
    if "--smoke-test" in sys.argv[1:]:
        QTimer.singleShot(0, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())