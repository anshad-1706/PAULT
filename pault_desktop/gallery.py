from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QByteArray, QBuffer, QPoint, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImageReader, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QStyle


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv"}
MAX_THUMBNAIL_SOURCE_BYTES = 32 * 1024 * 1024


class MediaGrid(QListWidget):
    def __init__(self, read_file: Callable[[str], bytes], parent=None) -> None:
        super().__init__(parent)
        self.read_file = read_file
        self._entry_by_path: dict[str, dict] = {}
        self._thumbnail_cache: dict[tuple[str, int, str], QIcon] = {}
        self._density = "medium"
        self._thumbnail_timer = QTimer(self)
        self._thumbnail_timer.setSingleShot(True)
        self._thumbnail_timer.setInterval(80)
        self._thumbnail_timer.timeout.connect(self._load_one_visible_thumbnail)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setMovement(QListWidget.Movement.Static)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setSelectionBehavior(QListWidget.SelectionBehavior.SelectItems)
        self.setDragEnabled(False)
        self.setWordWrap(True)
        self.setUniformItemSizes(True)
        self.setSpacing(12)
        self.setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(self.schedule_visible_thumbnails)
        self.set_density("medium")

    @property
    def selected_paths(self) -> list[str]:
        return [str(item.data(Qt.ItemDataRole.UserRole)) for item in self.selectedItems()]

    def set_density(self, density: str) -> None:
        dimensions = {
            "small": (QSize(164, 192), QSize(144, 122)),
            "medium": (QSize(194, 224), QSize(174, 154)),
            "large": (QSize(238, 270), QSize(218, 198)),
        }
        self._density = density if density in dimensions else "medium"
        grid_size, icon_size = dimensions[self._density]
        self.setGridSize(grid_size)
        self.setIconSize(icon_size)
        self.schedule_visible_thumbnails()

    def set_entries(self, entries: list[dict]) -> None:
        selected = set(self.selected_paths)
        self._entry_by_path = {str(entry["path"]): entry for entry in entries}
        self.clear()
        for entry in entries:
            path = str(entry["path"])
            kind = str(entry.get("kind", "file"))
            item = QListWidgetItem(self._placeholder_icon(path, kind), path.rsplit("/", 1)[-1])
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setData(Qt.ItemDataRole.UserRole + 1, kind)
            item.setData(Qt.ItemDataRole.UserRole + 2, entry)
            item.setToolTip(path)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            item.setSizeHint(self.gridSize())
            cached = self._thumbnail_cache.get(self._cache_key(path, entry))
            if cached is not None:
                item.setIcon(cached)
            if path in selected:
                item.setSelected(True)
            self.addItem(item)
        self.schedule_visible_thumbnails()

    def clear_sensitive(self) -> None:
        self._thumbnail_timer.stop()
        self._thumbnail_cache.clear()
        self._entry_by_path.clear()
        self.clear()

    def schedule_visible_thumbnails(self, *_args: object) -> None:
        if not self._thumbnail_timer.isActive():
            self._thumbnail_timer.start()

    def _load_one_visible_thumbnail(self) -> None:
        visible_rect = self.viewport().rect()
        for index in range(self.count()):
            item = self.item(index)
            path = str(item.data(Qt.ItemDataRole.UserRole))
            entry = self._entry_by_path.get(path, {})
            if item.data(Qt.ItemDataRole.UserRole + 1) != "file":
                continue
            suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            if f".{suffix}" not in IMAGE_SUFFIXES:
                continue
            key = self._cache_key(path, entry)
            if key in self._thumbnail_cache:
                continue
            if not self.visualItemRect(item).intersects(visible_rect):
                continue
            icon = self._make_thumbnail(path, entry)
            self._thumbnail_cache[key] = icon
            item.setIcon(icon)
            self._thumbnail_timer.start(15)
            return

    def _make_thumbnail(self, path: str, entry: dict) -> QIcon:
        if int(entry.get("size", 0)) > MAX_THUMBNAIL_SOURCE_BYTES:
            return self._placeholder_icon(path, "file")
        try:
            encoded = self.read_file(path)
            buffer = QBuffer()
            buffer.setData(QByteArray(encoded))
            if not buffer.open(QBuffer.OpenModeFlag.ReadOnly):
                return self._placeholder_icon(path, "file")
            reader = QImageReader(buffer)
            reader.setAutoTransform(True)
            source_size = reader.size()
            target_size = QSize(max(1, self.iconSize().width()), max(1, self.iconSize().height()))
            if source_size.isValid():
                reader.setScaledSize(source_size.scaled(target_size, Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            buffer.close()
            if image.isNull():
                return self._placeholder_icon(path, "file")
            pixmap = QPixmap(self.iconSize())
            pixmap.fill(QColor("#202a31"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scaled = QPixmap.fromImage(image).scaled(self.iconSize(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((pixmap.width() - scaled.width()) // 2, (pixmap.height() - scaled.height()) // 2, scaled)
            painter.end()
            return QIcon(pixmap)
        except (OSError, RuntimeError, ValueError):
            return self._placeholder_icon(path, "file")

    def _placeholder_icon(self, path: str, kind: str) -> QIcon:
        if kind == "folder":
            return self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if f".{suffix}" in VIDEO_SUFFIXES:
            pixmap = QPixmap(self.iconSize())
            pixmap.fill(QColor("#252e36"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#c49b55"))
            center = pixmap.rect().center()
            painter.drawEllipse(center, 25, 25)
            painter.setBrush(QColor("#1d252b"))
            painter.drawPolygon(QPolygon([center + QPoint(-7, -12), center + QPoint(-7, 12), center + QPoint(13, 0)]))
            painter.setPen(QPen(QColor("#d8dfe2")))
            painter.drawText(pixmap.rect().adjusted(0, 54, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, "VIDEO")
            painter.end()
            return QIcon(pixmap)
        return self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)

    @staticmethod
    def _cache_key(path: str, entry: dict) -> tuple[str, int, str]:
        return path, int(entry.get("size", 0)), str(entry.get("modified_at", ""))
