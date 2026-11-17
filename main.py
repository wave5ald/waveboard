"""Wave Board — an infinite visual canvas built with PyQt6."""

from __future__ import annotations

import base64
import copy
import ctypes
import json
import math
import os
import re
import sys
import time
import uuid
from collections import Counter
from typing import Optional

from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QLineF,
    QPoint,
    QPointF,
    QRectF,
    QSettings,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QIcon,
    QImageReader,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPalette,
    QPen,
    QPixmap,
    QTextCharFormat,
    QTextCursor,
    QTextOption,
    QTransform,
)
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSlider,
    QSpinBox,
    QStatusBar,
    QStyleOptionGraphicsItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


from updater import UpdateBanner, UpdateDialog, UpdateManager

APP_NAME = "Wave Board"
APP_VERSION = "1.2.0"
APP_ORG = "Wave Labs"

PORT_NAMES = ("top", "right", "bottom", "left")
PORT_DIRECTIONS = {
    "top": QPointF(0.0, -1.0),
    "right": QPointF(1.0, 0.0),
    "bottom": QPointF(0.0, 1.0),
    "left": QPointF(-1.0, 0.0),
}
HANDLE_NAMES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")

LINE_WEIGHTS = ("thin", "medium", "thick")
LINE_DASHES = ("solid", "dashed", "dotted")
LINE_ROUTES = ("curve", "elbow", "straight")
LINE_WIDTH_PX = {"thin": 1.65, "medium": 3.1, "thick": 5.0}
DEFAULT_LINE_COLOR = "#4B8DFF"

TEXT_ALIGNS = ("left", "center", "right")
TEXT_VALIGNS = ("top", "middle", "bottom")
BUNDLE_SPACING = 7.5
MAGNET_GRID = 24.0

THEME_PRESETS = ("blue", "graphite", "light")
THEME_LABELS = {"blue": "Blue", "graphite": "Dark Grey", "light": "Light"}
CURRENT_THEME = "blue"
CURRENT_THEME_MAP: dict[str, str] = {}

BG_COLOR = "#090D14"
CANVAS_GRID_MINOR = QColor(116, 139, 173, 38)
CANVAS_GRID_MAJOR = QColor(126, 154, 196, 74)
ACCENT = "#2D7DFF"
ACCENT_LIGHT = "#6FA8FF"
ACCENT_DIM = "#1E4E9E"
YELLOW = "#FFCA3F"
TEXT_MAIN = "#E8F0FB"
TEXT_MUTED = "#7D8CA3"
TEXT_FAINT = "#4F5D72"
CARD_BG = "#121B28"
CARD_BORDER = "#26344A"
TEXT_NODE_FILL = "#121A28"
TEXT_NODE_TEXT = "#EDF4FF"
SHAPE_FILL = "#172943"
SHAPE_TEXT = "#F2F7FF"
COMMENT_TEXT = "#B9C7D8"
IMAGE_FILL = "#111A26"
IMAGE_BORDER = "#2A3A50"
PORT_FILL = "#8FB8FF"
PORT_BORDER = "#070B11"
HANDLE_FILL = "#F8FCFF"
NODE_SHADOW_ALPHA = 56

ICON_COLOR = "#C9D5E7"
ICON_CACHE: dict[tuple[str, str], QIcon] = {}
SWATCH_CACHE: dict[tuple[str, str], QIcon] = {}


# ---------------------------------------------------------------------------
# Path / colour helpers
# ---------------------------------------------------------------------------


def resource_path(relative: str) -> str:
    """Resolve a bundled resource in both source and PyInstaller runs."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def color_from(value, fallback: str) -> QColor:
    try:
        color = QColor(value) if value is not None else QColor()
    except (TypeError, ValueError):
        color = QColor()
    return color if color.isValid() else QColor(fallback)


def color_name(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexArgb)


def with_alpha(color: QColor, alpha: int) -> QColor:
    result = QColor(color)
    result.setAlpha(max(0, min(255, int(alpha))))
    return result


def safe_float(value, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return number


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


# ---------------------------------------------------------------------------
# Vector UI icons (kept in code so the executable remains a single source file)
# ---------------------------------------------------------------------------


def _new_icon_pixmap() -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pixmap, painter


def ui_icon(name: str, color: Optional[str] = None) -> QIcon:
    color = color or ICON_COLOR
    key = (name, color)
    cached = ICON_CACHE.get(key)
    if cached is not None:
        return cached

    pixmap, p = _new_icon_pixmap()
    pen = QPen(QColor(color), 5.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if name == "text":
        p.drawLine(QPointF(17, 17), QPointF(47, 17))
        p.drawLine(QPointF(32, 17), QPointF(32, 49))
        p.drawLine(QPointF(24, 49), QPointF(40, 49))
    elif name == "image":
        p.drawRoundedRect(QRectF(10, 15, 44, 34), 6, 6)
        p.setBrush(QColor(color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(38, 21, 8, 8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(pen)
        path = QPainterPath(QPointF(16, 43))
        path.lineTo(27, 31)
        path.lineTo(35, 39)
        path.lineTo(41, 33)
        path.lineTo(48, 43)
        p.drawPath(path)
    elif name == "shape":
        p.drawRoundedRect(QRectF(11, 14, 42, 36), 9, 9)
    elif name == "rectangle":
        p.drawRect(QRectF(9, 17, 46, 30))
    elif name == "square":
        p.drawRect(QRectF(15, 15, 34, 34))
    elif name == "grid":
        p.setPen(QPen(QColor(color), 2.2))
        for x in (16, 32, 48):
            p.drawLine(QPointF(x, 14), QPointF(x, 50))
        for y in (16, 32, 48):
            p.drawLine(QPointF(14, y), QPointF(50, y))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(color))
        for x in (16, 32, 48):
            for y in (16, 32, 48):
                p.drawEllipse(QPointF(x, y), 1.7, 1.7)
    elif name == "delete":
        p.setPen(QPen(QColor(color), 4.5))
        p.drawLine(QPointF(14, 19), QPointF(50, 19))
        p.drawLine(QPointF(25, 13), QPointF(39, 13))
        p.drawRoundedRect(QRectF(17, 19, 30, 32), 4, 4)
        p.drawLine(QPointF(26, 27), QPointF(26, 43))
        p.drawLine(QPointF(38, 27), QPointF(38, 43))
    elif name == "save":
        p.setPen(QPen(QColor(color), 4.2))
        p.drawRoundedRect(QRectF(11, 9, 42, 46), 5, 5)
        p.drawRoundedRect(QRectF(21, 10, 22, 15), 2, 2)
        p.drawRoundedRect(QRectF(19, 34, 26, 18), 2, 2)
    elif name == "open":
        path = QPainterPath(QPointF(8, 20))
        path.lineTo(27, 20)
        path.lineTo(32, 26)
        path.lineTo(56, 26)
        path.lineTo(50, 49)
        path.lineTo(9, 49)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(8, 20), QPointF(8, 47))
    elif name == "new":
        p.drawRoundedRect(QRectF(13, 8, 31, 48), 4, 4)
        p.drawLine(QPointF(21, 20), QPointF(36, 20))
        p.drawLine(QPointF(21, 29), QPointF(36, 29))
        p.drawLine(QPointF(21, 38), QPointF(30, 38))
        p.drawLine(QPointF(46, 36), QPointF(46, 54))
        p.drawLine(QPointF(37, 45), QPointF(55, 45))
    elif name == "thick":
        p.setPen(QPen(QColor(color), 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(11, 23), QPointF(53, 23))
        p.drawLine(QPointF(11, 41), QPointF(41, 41))
    elif name == "thin":
        p.setPen(QPen(QColor(color), 2.2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(11, 21), QPointF(53, 21))
        p.drawLine(QPointF(11, 33), QPointF(53, 33))
        p.drawLine(QPointF(11, 45), QPointF(53, 45))
    elif name == "plus":
        p.setPen(QPen(QColor(color), 5.0))
        p.drawLine(QPointF(32, 15), QPointF(32, 49))
        p.drawLine(QPointF(15, 32), QPointF(49, 32))
    elif name == "minus":
        p.setPen(QPen(QColor(color), 5.0))
        p.drawLine(QPointF(15, 32), QPointF(49, 32))
    elif name == "fit":
        p.setPen(QPen(QColor(color), 4.2))
        p.drawLine(QPointF(12, 25), QPointF(12, 12))
        p.drawLine(QPointF(12, 12), QPointF(25, 12))
        p.drawLine(QPointF(39, 12), QPointF(52, 12))
        p.drawLine(QPointF(52, 12), QPointF(52, 25))
        p.drawLine(QPointF(52, 39), QPointF(52, 52))
        p.drawLine(QPointF(52, 52), QPointF(39, 52))
        p.drawLine(QPointF(25, 52), QPointF(12, 52))
        p.drawLine(QPointF(12, 52), QPointF(12, 39))
        p.drawRect(QRectF(25, 25, 14, 14))
    elif name == "check":
        p.setPen(QPen(QColor(color), 5.5))
        p.drawLine(QPointF(14, 33), QPointF(27, 46))
        p.drawLine(QPointF(27, 46), QPointF(51, 18))
    elif name == "download":
        p.drawLine(QPointF(32, 12), QPointF(32, 40))
        p.drawLine(QPointF(20, 30), QPointF(32, 42))
        p.drawLine(QPointF(44, 30), QPointF(32, 42))
        p.drawLine(QPointF(14, 52), QPointF(50, 52))
    elif name == "help":
        p.setPen(QPen(QColor(color), 3.0))
        p.drawEllipse(QRectF(15, 15, 34, 34))
        font = QFont("Segoe UI", 25)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(QRectF(15, 9, 34, 36), Qt.AlignmentFlag.AlignCenter, "?")
    elif name in ("align_left", "align_center", "align_right"):
        p.setPen(QPen(QColor(color), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if name == "align_left":
            xs = (12, 12, 12)
        elif name == "align_right":
            xs = (32, 22, 39)
        else:
            xs = (22, 12, 22)
        p.drawLine(QPointF(12, 13), QPointF(52, 13))
        p.drawLine(QPointF(xs[0], 26), QPointF(xs[0] + 28, 26))
        p.drawLine(QPointF(xs[1], 39), QPointF(xs[1] + 38, 39))
        p.drawLine(QPointF(xs[2], 51), QPointF(xs[2] + 17, 51))
    elif name in ("valign_top", "valign_middle", "valign_bottom"):
        p.setPen(QPen(QColor(color), 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(13, 12), QPointF(13, 52))
        if name == "valign_top":
            ys = (16, 16, 16)
        elif name == "valign_bottom":
            ys = (34, 22, 48)
        else:
            ys = (26, 14, 38)
        p.drawLine(QPointF(22, ys[0]), QPointF(52, ys[0]))
        p.drawLine(QPointF(22, ys[1]), QPointF(44, ys[1]))
        p.drawLine(QPointF(22, ys[2]), QPointF(49, ys[2]))
    elif name == "magnet":
        p.setPen(QPen(QColor(color), 5.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(18, 12), QPointF(18, 32))
        p.drawArc(QRectF(18, 18, 28, 28), 180 * 16, 180 * 16)
        p.drawLine(QPointF(46, 32), QPointF(46, 12))
        p.setPen(QPen(QColor(color), 7.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        p.drawLine(QPointF(18, 12), QPointF(18, 18))
        p.drawLine(QPointF(46, 12), QPointF(46, 18))
    elif name == "bundle":
        p.setPen(QPen(QColor(color), 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(10, 18), QPointF(24, 18))
        p.drawLine(QPointF(10, 32), QPointF(24, 32))
        p.drawLine(QPointF(10, 46), QPointF(24, 46))
        path = QPainterPath(QPointF(24, 18))
        path.cubicTo(QPointF(38, 18), QPointF(34, 32), QPointF(54, 32))
        p.drawPath(path)
        path = QPainterPath(QPointF(24, 32))
        path.lineTo(QPointF(54, 32))
        p.drawPath(path)
        path = QPainterPath(QPointF(24, 46))
        path.cubicTo(QPointF(38, 46), QPointF(34, 32), QPointF(54, 32))
        p.drawPath(path)
    elif name == "inherit":
        p.setPen(QPen(QColor(color), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawRoundedRect(QRectF(10, 12, 28, 22), 4, 4)
        p.drawRoundedRect(QRectF(26, 30, 28, 22), 4, 4)
        p.setPen(QPen(QColor(color), 3.0))
        p.drawLine(QPointF(24, 24), QPointF(40, 24))
        p.drawLine(QPointF(40, 24), QPointF(40, 30))
    elif name == "palette":
        p.setPen(QPen(QColor(color), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(11, 11, 42, 42))
        p.setPen(Qt.PenStyle.NoPen)
        for x, y, radius in ((25, 22, 4.6), (38, 22, 4.6), (20, 34, 4.6), (42, 33, 4.0)):
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(x - radius, y - radius, radius * 2.0, radius * 2.0))
        p.setBrush(QColor(color))
        p.drawEllipse(QRectF(26, 42, 12, 10))
    elif name == "comment":
        path = QPainterPath(QPointF(12, 13))
        path.lineTo(52, 13)
        path.lineTo(52, 41)
        path.lineTo(30, 41)
        path.lineTo(20, 51)
        path.lineTo(20, 41)
        path.lineTo(12, 41)
        path.closeSubpath()
        p.drawPath(path)
    else:
        p.drawEllipse(QRectF(20, 20, 24, 24))

    p.end()
    icon = QIcon(pixmap)
    ICON_CACHE[key] = icon
    return icon


def swatch_icon(kind: str, color: QColor) -> QIcon:
    key = (kind, color_name(color))
    cached = SWATCH_CACHE.get(key)
    if cached is not None:
        return cached

    pixmap, p = _new_icon_pixmap()
    # Checkerboard communicates transparent colours cleanly.
    for y in range(8):
        for x in range(8):
            shade = 232 if (x + y) % 2 == 0 else 194
            p.fillRect(QRectF(8 + x * 6, 8 + y * 6, 6, 6), QColor(shade, shade, shade, 255))

    if kind == "fill":
        p.setPen(QPen(QColor(255, 255, 255, 70), 2))
        p.setBrush(color)
        p.drawRoundedRect(QRectF(8, 8, 48, 48), 9, 9)
    elif kind == "border":
        p.setPen(QPen(color, 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QColor(11, 17, 25, 220))
        p.drawRoundedRect(QRectF(12, 12, 40, 40), 9, 9)
    elif kind == "text":
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(9, 13, 20, 235))
        p.drawRoundedRect(QRectF(8, 8, 48, 48), 9, 9)
        font = QFont("Segoe UI", 28)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(QPen(color))
        p.drawText(QRectF(8, 4, 48, 48), Qt.AlignmentFlag.AlignCenter, "A")
        p.setPen(QPen(color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(18, 52), QPointF(46, 52))
    elif kind == "line":
        p.setPen(QPen(QColor(255, 255, 255, 65), 2))
        p.setBrush(QColor(9, 13, 20, 235))
        p.drawRoundedRect(QRectF(8, 8, 48, 48), 9, 9)
        p.setPen(QPen(color, 9.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(14, 34), QPointF(31, 21))
        p.drawLine(QPointF(31, 21), QPointF(50, 41))
    p.end()
    icon = QIcon(pixmap)
    SWATCH_CACHE[key] = icon
    return icon


def brand_icon() -> QIcon:
    icon = QIcon(resource_path("icon.ico"))
    if not icon.isNull():
        return icon
    # Fallback mark, drawn in code if the packaged icon is unavailable.
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#05070C"))
    p.drawRoundedRect(QRectF(2, 2, 252, 252), 54, 54)
    p.setPen(QPen(QColor("#1370FF"), 22, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(43, 66, 158, 116), 26, 26)
    p.drawLine(QPointF(84, 128), QPointF(111, 104))
    p.drawLine(QPointF(111, 104), QPointF(137, 129))
    p.drawLine(QPointF(137, 129), QPointF(164, 108))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(YELLOW))
    p.drawEllipse(QRectF(166, 28, 58, 58))
    p.end()
    return QIcon(pixmap)


def brand_pixmap(size: int = 32) -> QPixmap:
    icon = brand_icon()
    pixmap = icon.pixmap(QSize(256, 256))
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(
        QSize(size, size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ---------------------------------------------------------------------------
# Canvas nodes
# ---------------------------------------------------------------------------


class NodeTextItem(QGraphicsTextItem):
    """A text renderer/editor child clipped to its parent node."""

    def __init__(self, node: "NodeItem"):
        super().__init__(node)
        self.node = node
        self.setAcceptHoverEvents(False)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setZValue(3)
        self.document().setDocumentMargin(0)
        option = self.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(option)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        node = self.node
        if node is None:
            return
        painter.save()
        clip = QPainterPath()
        radius = node.corner_radius()
        clip.addRoundedRect(node.text_clip_rect(), radius, radius)
        pos = self.pos()
        clip.translate(-pos.x(), -pos.y())
        painter.setClipPath(clip, Qt.ClipOperation.IntersectClip)
        super().paint(painter, option, widget)
        painter.restore()

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.node is not None and self.node.is_editing:
            super().mousePressEvent(event)
        else:
            event.ignore()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.node is not None:
            self.node.begin_editing(scene_pos=event.scenePos())
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.node is not None:
                self.node.end_editing()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if self.node is not None:
                self.node.end_editing()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Paste) or (
            event.key() == Qt.Key.Key_Insert
            and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        ):
            text = QApplication.clipboard().text()
            if text:
                cursor = self.textCursor()
                cursor.insertText(text)
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        if self.node is None or not self.node.is_editing:
            event.ignore()
            return
        menu = QMenu()
        cut_action = menu.addAction("Cut")
        copy_action = menu.addAction("Copy")
        paste_action = menu.addAction("Paste as plain text")
        chosen = menu.exec(event.screenPos())
        cursor = self.textCursor()
        if chosen is cut_action or chosen is copy_action:
            selected = cursor.selectedText()
            if selected:
                QApplication.clipboard().setText(selected)
            if chosen is cut_action and cursor.hasSelection():
                cursor.removeSelectedText()
        elif chosen is paste_action:
            text = QApplication.clipboard().text()
            if text:
                cursor.insertText(text)
        event.accept()

    def _focus_stays_in_editor(self) -> bool:
        app = QApplication.instance()
        widget = app.focusWidget() if app is not None else None
        if widget is None:
            return False
        window = widget.window()
        if window is not None and window.inherits("QDialog"):
            return True
        scene = self.scene()
        views = scene.views() if scene is not None else []
        main_window = views[0].window() if views else None
        return (
            main_window is not None
            and window is main_window
            and not isinstance(widget, QGraphicsView)
        )

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        if self.node is not None and self.node.is_editing:
            if self._focus_stays_in_editor():
                return
            self.node.end_editing(from_focus=True)


class NodeItem(QGraphicsObject):
    """Base class for every magnetic node type."""

    TYPE = "node"
    SUPPORTS_TEXT = True
    AUTO_HEIGHT = False
    TEXT_CENTER = False
    TEXT_VCENTER = False
    LINKABLE = True
    DEFAULT_W = 240.0
    DEFAULT_H = 120.0
    MIN_W = 70.0
    MIN_H = 44.0
    PADDING = 16.0

    HANDLE_CURSORS = {
        "nw": Qt.CursorShape.SizeFDiagCursor,
        "se": Qt.CursorShape.SizeFDiagCursor,
        "ne": Qt.CursorShape.SizeBDiagCursor,
        "sw": Qt.CursorShape.SizeBDiagCursor,
        "n": Qt.CursorShape.SizeVerCursor,
        "s": Qt.CursorShape.SizeVerCursor,
        "e": Qt.CursorShape.SizeHorCursor,
        "w": Qt.CursorShape.SizeHorCursor,
    }

    def __init__(self, node_id: Optional[str] = None, width: Optional[float] = None, height: Optional[float] = None):
        super().__init__()
        self.node_id = node_id or uuid.uuid4().hex
        self._width = float(width if width is not None else self.DEFAULT_W)
        self._height = float(height if height is not None else self.DEFAULT_H)
        self._ui_scale = 1.0
        self._hovered = False
        self._hover_port: Optional[str] = None
        self._target_port: Optional[str] = None
        self._ports_forced = False
        self._editing = False
        self._suppress_text_signal = False
        self._connections: set[ConnectionItem] = set()
        self._resize_handle: Optional[str] = None
        self._resize_start_scene: Optional[QPointF] = None
        self._resize_start_geom: Optional[tuple[QPointF, float, float]] = None
        self._drag_connection = False
        self._last_cursor: Optional[Qt.CursorShape] = None
        self._ready = False

        self.fill = QColor(CARD_BG)
        self.border = QColor(CARD_BORDER)
        self.radius = 14.0
        self.font_size = 16
        self.font_family = "Segoe UI"
        self.font_bold = False
        self.text_color = QColor(TEXT_MAIN)
        self.text_align = "center" if self.TEXT_CENTER else "left"
        self.text_valign = "middle" if self.TEXT_VCENTER else "top"
        self.text_fit = False

        self.text_item: Optional[NodeTextItem] = None
        if self.SUPPORTS_TEXT:
            self.text_item = NodeTextItem(self)
            self._apply_text_style()
            self.text_item.document().contentsChanged.connect(self._on_text_changed)

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setZValue(10)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setToolTip("Drag to move · drag a port to connect · double-click to edit")

    # ---- geometry ---------------------------------------------------------

    @property
    def is_editing(self) -> bool:
        return self._editing

    def body_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, self._width, self._height)

    def corner_radius(self) -> float:
        return clamp(float(self.radius), 0.0, min(self._width, self._height) / 2.0)

    def text_clip_rect(self) -> QRectF:
        return self.body_rect().adjusted(5.0, 5.0, -5.0, -5.0)

    def _ui_px(self, pixels: float) -> float:
        return pixels / max(0.08, self._ui_scale)

    def _port_offset(self) -> float:
        return self._ui_px(17.0)

    def _port_radius(self) -> float:
        return self._ui_px(5.4)

    def _handle_size(self) -> float:
        return self._ui_px(9.0)

    def port_center(self, port: str) -> QPointF:
        offset = self._port_offset()
        if port == "top":
            return QPointF(self._width / 2.0, -offset)
        if port == "right":
            return QPointF(self._width + offset, self._height / 2.0)
        if port == "bottom":
            return QPointF(self._width / 2.0, self._height + offset)
        return QPointF(-offset, self._height / 2.0)

    def port_scene_pos(self, port: str) -> QPointF:
        return self.mapToScene(self.port_center(port))

    def port_direction(self, port: str) -> QPointF:
        return PORT_DIRECTIONS.get(port, QPointF(0.0, 1.0))

    def port_at(self, pos: QPointF) -> Optional[str]:
        if not self.LINKABLE:
            return None
        hit_radius = self._ui_px(10.0)
        for port in PORT_NAMES:
            center = self.port_center(port)
            if QLineF(center, pos).length() <= hit_radius:
                return port
        return None

    def handle_centers(self) -> dict[str, QPointF]:
        w, h = self._width, self._height
        return {
            "nw": QPointF(0, 0),
            "n": QPointF(w / 2.0, 0),
            "ne": QPointF(w, 0),
            "e": QPointF(w, h / 2.0),
            "se": QPointF(w, h),
            "s": QPointF(w / 2.0, h),
            "sw": QPointF(0, h),
            "w": QPointF(0, h / 2.0),
        }

    def handle_at(self, pos: QPointF) -> Optional[str]:
        if not self.isSelected():
            return None
        size = self._handle_size()
        hit = size / 2.0 + self._ui_px(3.0)
        for name, center in self.handle_centers().items():
            rect = QRectF(center.x() - hit, center.y() - hit, hit * 2.0, hit * 2.0)
            if rect.contains(pos):
                return name
        return None

    def boundingRect(self) -> QRectF:
        margin = self._port_offset() + self._port_radius() + self._ui_px(10.0)
        return self.body_rect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        radius = self.corner_radius()
        path.addRoundedRect(self.body_rect(), radius, radius)
        # Port hit-zones are part of the shape even while hidden, which keeps
        # the node hovered while the pointer travels from the body to a port.
        pr = self._port_radius() + self._ui_px(3.0)
        if self.LINKABLE:
            for port in PORT_NAMES:
                path.addEllipse(self.port_center(port), pr, pr)
        # Corner handles sit outside rounded corners. They must still receive
        # the press, otherwise the bottom-right/top-left handles are dead.
        if self.isSelected():
            hr = self._handle_size() / 2.0 + self._ui_px(3.0)
            for center in self.handle_centers().values():
                path.addEllipse(center, hr, hr)
        return path

    # ---- rendering --------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_shadow(painter)
        self.paint_body(painter)
        self._paint_selection(painter)
        self._paint_handles(painter)
        self._paint_ports(painter)
        painter.restore()

    def _paint_shadow(self, painter: QPainter) -> None:
        if self.fill.alpha() <= 4 and self.TYPE != "image":
            return
        radius = self.corner_radius()
        offset = self._ui_px(3.0)
        shadow = self.body_rect().translated(0.0, offset).adjusted(-1.0, -1.0, 1.0, 1.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, NODE_SHADOW_ALPHA))
        painter.drawRoundedRect(shadow, radius, radius)

    def paint_body(self, painter: QPainter) -> None:
        painter.setPen(QPen(self.border, 1.2))
        painter.setBrush(self.fill)
        painter.drawRoundedRect(self.body_rect(), self.corner_radius(), self.corner_radius())

    def _paint_selection(self, painter: QPainter) -> None:
        if self._editing:
            pen = QPen(QColor(ACCENT), 2.2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.body_rect(), self.corner_radius(), self.corner_radius())
            return
        if self.isSelected():
            pen = QPen(QColor(ACCENT), 2.0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.body_rect(), self.corner_radius(), self.corner_radius())
        elif self._hovered:
            pen = QPen(with_alpha(QColor(ACCENT_LIGHT), 120), 1.2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.body_rect(), self.corner_radius(), self.corner_radius())

    def _paint_handles(self, painter: QPainter) -> None:
        if not self.isSelected() or self._editing:
            return
        size = self._handle_size()
        pen = QPen(QColor(ACCENT), 1.4)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QColor(HANDLE_FILL))
        radius = self._ui_px(2.0)
        for center in self.handle_centers().values():
            rect = QRectF(center.x() - size / 2.0, center.y() - size / 2.0, size, size)
            painter.drawRoundedRect(rect, radius, radius)

    def _ports_visible(self) -> bool:
        if not self.LINKABLE:
            return False
        return (
            not self._editing
            and (self._hovered or self.isSelected() or self._ports_forced or self._target_port is not None)
        )

    def _paint_ports(self, painter: QPainter) -> None:
        if not self.LINKABLE or not self._ports_visible():
            return
        for port in PORT_NAMES:
            center = self.port_center(port)
            active = port == self._hover_port
            target = port == self._target_port
            radius = self._port_radius()
            fill = QColor(PORT_FILL)
            if active:
                radius *= 1.28
                fill = QColor(ACCENT_LIGHT)
            if target:
                radius *= 1.45
                fill = QColor(YELLOW)
            pen = QPen(QColor(PORT_BORDER), 1.4)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(fill)
            painter.drawEllipse(center, radius, radius)
            if target:
                glow_pen = QPen(QColor(255, 202, 63, 75), 7.0)
                glow_pen.setCosmetic(True)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(center, radius + self._ui_px(2.0), radius + self._ui_px(2.0))

    def paint_placeholder(self, painter: QPainter, text: str, centered: bool = False) -> None:
        font = QFont("Segoe UI", 10)
        font.setItalic(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT_FAINT))
        flags = Qt.AlignmentFlag.AlignVCenter
        flags |= Qt.AlignmentFlag.AlignHCenter if centered else Qt.AlignmentFlag.AlignLeft
        painter.drawText(self.body_rect().adjusted(self.PADDING, self.PADDING, -self.PADDING, -self.PADDING), flags, text)

    # ---- text -------------------------------------------------------------

    def text(self) -> str:
        return self.text_item.toPlainText() if self.text_item is not None else ""

    def set_text(self, value: str, notify: bool = True) -> None:
        if self.text_item is None:
            return
        self._suppress_text_signal = True
        self.text_item.setPlainText(value)
        self._suppress_text_signal = False
        self.layout_text()
        if self.AUTO_HEIGHT:
            self._fit_height_to_text()
        self.update()
        if notify:
            self._notify_changed()

    def _font_for_size(self, size: int) -> QFont:
        family = self.font_family or "Segoe UI"
        font = QFont(family, max(6, int(size)))
        if font.family() != family:
            font.setFamily("Segoe UI")
        font.setWeight(QFont.Weight.Bold if self.font_bold else QFont.Weight.Normal)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font

    def _text_alignment(self) -> Qt.AlignmentFlag:
        return {
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(self.text_align, Qt.AlignmentFlag.AlignLeft)

    def _apply_text_style(self) -> None:
        if self.text_item is None:
            return
        base_size = max(6, int(self.font_size))
        font = self._font_for_size(base_size)
        if self.text_fit:
            available_w = max(8.0, self._width - self.PADDING * 2.0)
            available_h = max(8.0, self._height - self.PADDING * 2.0)
            document = self.text_item.document()
            document.setTextWidth(available_w)
            document.setDefaultFont(font)
            measured = document.size().height()
            size = base_size
            if measured > available_h + 0.4 and measured > 0.5:
                size = max(6, min(base_size, int(base_size * available_h / measured)))
                while size > 6:
                    font = self._font_for_size(size)
                    document.setDefaultFont(font)
                    if document.size().height() <= available_h + 0.4:
                        break
                    size -= 1
                font = self._font_for_size(max(6, size))
        self.text_item.setFont(font)
        self.text_item.setDefaultTextColor(self.text_color)
        option = self.text_item.document().defaultTextOption()
        option.setAlignment(self._text_alignment())
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.text_item.document().setDefaultTextOption(option)

    def layout_text(self) -> None:
        if self.text_item is None:
            return
        inner_width = max(16.0, self._width - self.PADDING * 2.0)
        self.text_item.setTextWidth(inner_width)
        doc_height = self.text_item.document().size().height()
        if self.text_valign == "middle":
            y = (self._height - doc_height) / 2.0
        elif self.text_valign == "bottom":
            y = self._height - self.PADDING - doc_height
        else:
            y = self.PADDING
        y = max(self.PADDING * 0.35, y)
        self.text_item.setPos(self.PADDING, y)

    def _fit_height_to_text(self) -> None:
        if self.text_item is None or not self.AUTO_HEIGHT:
            return
        self.layout_text()
        needed = math.ceil(self.text_item.document().size().height() + self.PADDING * 2.0 + 1.0)
        needed = max(self.MIN_H, needed)
        if needed > self._height + 0.5:
            self.prepareGeometryChange()
            self._height = needed
            self.layout_text()
            self.update()
            self.update_connections()
            self._notify_changed()

    def _on_text_changed(self) -> None:
        if self._suppress_text_signal:
            return
        if self.text_fit:
            self._apply_text_style()
        self.layout_text()
        self._fit_height_to_text()
        self.update()
        self._notify_changed()

    def _active_text_cursor(self) -> Optional[QTextCursor]:
        if self.text_item is None:
            return None
        cursor = self.text_item.textCursor()
        return cursor if cursor.hasSelection() else None

    def has_text_selection(self) -> bool:
        return self._active_text_cursor() is not None

    def selection_text_format(self) -> Optional[QTextCharFormat]:
        cursor = self._active_text_cursor()
        if cursor is None:
            return None
        return QTextCharFormat(cursor.charFormat())

    def _merge_text_format(self, fmt: QTextCharFormat, selection: bool) -> None:
        if self.text_item is None:
            return
        cursor = self.text_item.textCursor()
        if selection and cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        else:
            whole = QTextCursor(self.text_item.document())
            whole.select(QTextCursor.SelectionType.Document)
            whole.mergeCharFormat(fmt)
        self.text_item.setTextCursor(cursor)
        self.layout_text()
        self._fit_height_to_text()
        self.update()
        self._notify_changed()

    def apply_text_size(self, size: int) -> None:
        size = max(6, min(200, int(size)))
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        selection = self._active_text_cursor() is not None
        if not selection:
            self.font_size = size
            self._apply_text_style()
        self._merge_text_format(fmt, selection)

    def apply_text_bold(self, bold: bool) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
        selection = self._active_text_cursor() is not None
        if not selection:
            self.font_bold = bool(bold)
            self._apply_text_style()
        self._merge_text_format(fmt, selection)

    def apply_text_family(self, family: str) -> None:
        family = str(family or "").strip()
        if not family:
            return
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        selection = self._active_text_cursor() is not None
        if not selection:
            self.font_family = family
            self._apply_text_style()
        self._merge_text_format(fmt, selection)

    def apply_text_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        selection = self._active_text_cursor() is not None
        if not selection:
            self.text_color = QColor(color)
            self._apply_text_style()
        self._merge_text_format(fmt, selection)

    def remap_text_colors(self, lookup: dict[str, QColor]) -> None:
        if self.text_item is None or not lookup:
            return
        document = self.text_item.document()
        fragments: list[tuple[int, int, QColor]] = []
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    fmt = fragment.charFormat()
                    brush = fmt.foreground()
                    if brush.style() != Qt.BrushStyle.NoBrush:
                        color = brush.color()
                        if color.isValid() and color.name().lower() in lookup:
                            fragments.append(
                                (fragment.position(), fragment.length(), QColor(color))
                            )
                iterator += 1
            block = block.next()
        if not fragments:
            return
        edit = QTextCursor(document)
        edit.beginEditBlock()
        for position, length, color in fragments:
            replacement = lookup.get(color.name().lower())
            if replacement is None:
                continue
            cursor = QTextCursor(document)
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            new_color = QColor(replacement)
            new_color.setAlpha(color.alpha())
            fmt.setForeground(new_color)
            cursor.mergeCharFormat(fmt)
        edit.endEditBlock()
        self.update()

    def set_font_size(self, size: int) -> None:
        size = max(6, min(120, int(size)))
        self.apply_text_size(size)

    def set_text_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.apply_text_color(color)

    def set_text_align(self, align: str, notify: bool = True) -> None:
        if align not in TEXT_ALIGNS or align == self.text_align:
            return
        self.text_align = align
        self._apply_text_style()
        self.layout_text()
        self.update()
        if notify:
            self._notify_changed()

    def set_text_valign(self, valign: str, notify: bool = True) -> None:
        if valign not in TEXT_VALIGNS or valign == self.text_valign:
            return
        self.text_valign = valign
        self.layout_text()
        self.update()
        if notify:
            self._notify_changed()

    def set_text_fit(self, enabled: bool, notify: bool = True) -> None:
        enabled = bool(enabled)
        if enabled == self.text_fit:
            return
        self.text_fit = enabled
        self._apply_text_style()
        self.layout_text()
        self.update()
        if notify:
            self._notify_changed()

    def set_radius(self, radius: float) -> None:
        radius = clamp(float(radius), 0.0, 240.0)
        if abs(radius - self.radius) < 0.01:
            return
        self.radius = radius
        self.update()
        self._notify_changed()

    def set_fill(self, color: QColor) -> None:
        if not color.isValid() or color == self.fill:
            return
        self.fill = QColor(color)
        self.update()
        self._notify_changed()

    def set_border(self, color: QColor) -> None:
        if not color.isValid() or color == self.border:
            return
        self.border = QColor(color)
        self.update()
        self._notify_changed()

    # ---- editing ----------------------------------------------------------

    def begin_editing(self, select_all: bool = False, scene_pos: Optional[QPointF] = None) -> None:
        if self.text_item is None or self._editing:
            return
        scene = self.scene()
        if scene is not None and hasattr(scene, "register_editor"):
            scene.register_editor(self)
        self._editing = True
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.text_item.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setCursor(Qt.CursorShape.IBeamCursor)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self._last_cursor = Qt.CursorShape.IBeamCursor
        self.text_item.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.text_item.textCursor()
        if select_all:
            cursor.select(QTextCursor.SelectionType.Document)
        else:
            cursor.clearSelection()
            position = len(self.text_item.toPlainText())
            if scene_pos is not None:
                try:
                    local = self.text_item.mapFromScene(scene_pos)
                    position = self.text_item.document().documentLayout().hitTest(
                        local, Qt.HitTestAccuracy.FuzzyHit
                    )
                except (RuntimeError, TypeError, ValueError):
                    position = 0
            cursor.setPosition(max(0, position))
        self.text_item.setTextCursor(cursor)
        self.setSelected(True)
        self.update()

    def end_editing(self, from_focus: bool = False) -> None:
        if not self._editing or self.text_item is None:
            return
        self._editing = False
        cursor = self.text_item.textCursor()
        if cursor.hasSelection():
            cursor.clearSelection()
            self.text_item.setTextCursor(cursor)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.text_item.clearFocus()
        self.text_item.unsetCursor()
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._last_cursor = Qt.CursorShape.SizeAllCursor
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.layout_text()
        self.update()
        scene = self.scene()
        if scene is not None and hasattr(scene, "unregister_editor"):
            scene.unregister_editor(self)
        if not from_focus:
            self.setFocus(Qt.FocusReason.OtherFocusReason)

    # ---- interaction ------------------------------------------------------

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._editing:
            if self.text_item is not None:
                self.text_item.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            port = self.port_at(event.pos())
            if port is not None:
                scene = self.scene()
                if scene is not None and hasattr(scene, "begin_connection"):
                    self.setSelected(True)
                    self._drag_connection = True
                    scene.begin_connection(self, port, event.scenePos())
                    event.accept()
                    return
            if self.isSelected():
                handle = self.handle_at(event.pos())
                if handle is not None:
                    self._begin_resize(handle, event.scenePos())
                    event.accept()
                    return
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._drag_connection:
            scene = self.scene()
            if scene is not None and hasattr(scene, "update_connection_drag"):
                scene.update_connection_drag(event.scenePos())
            event.accept()
            return
        if self._resize_handle is not None:
            self._resize_to(
                event.scenePos(),
                lock_aspect=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier),
            )
            event.accept()
            return
        super().mouseMoveEvent(event)
        scene = self.scene()
        if isinstance(scene, BoardScene):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                scene.clear_guides()
                scene.preview_line_attach(self)
            else:
                scene.clear_line_attach_preview()
                delta = scene.apply_magnet(
                    self, ctrl=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                )
                if delta is not None:
                    for other in scene.selected_nodes():
                        if other is not self:
                            other.setPos(other.pos() + delta)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._drag_connection:
            self._drag_connection = False
            scene = self.scene()
            if scene is not None and hasattr(scene, "finish_connection"):
                scene.finish_connection(event.scenePos())
            event.accept()
            return
        if self._resize_handle is not None:
            self._resize_handle = None
            self._resize_start_scene = None
            self._resize_start_geom = None
            self.unsetCursor()
            self._last_cursor = None
            event.accept()
            return
        scene = self.scene()
        if isinstance(scene, BoardScene):
            scene.clear_guides()
            if scene.line_attach_preview(self) is not None:
                scene.commit_line_attach(self)
            scene.clear_line_attach_preview()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self.SUPPORTS_TEXT and not self._editing:
            if self.port_at(event.pos()) is None and self.handle_at(event.pos()) is None:
                self.begin_editing(scene_pos=event.scenePos())
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def _begin_resize(self, handle: str, scene_pos: QPointF) -> None:
        self._resize_handle = handle
        self._resize_start_scene = QPointF(scene_pos)
        self._resize_start_geom = (QPointF(self.pos()), self._width, self._height)
        self.setCursor(self.HANDLE_CURSORS[handle])
        self._last_cursor = self.HANDLE_CURSORS[handle]

    def _resize_to(self, scene_pos: QPointF, lock_aspect: bool = False) -> None:
        if self._resize_start_geom is None or self._resize_start_scene is None:
            return
        start_pos, start_w, start_h = self._resize_start_geom
        dx = scene_pos.x() - self._resize_start_scene.x()
        dy = scene_pos.y() - self._resize_start_scene.y()
        left, top = start_pos.x(), start_pos.y()
        right, bottom = left + start_w, top + start_h
        handle = self._resize_handle or ""

        if "w" in handle:
            left = min(left + dx, right - self.MIN_W)
        if "e" in handle:
            right = max(right + dx, left + self.MIN_W)
        if "n" in handle:
            top = min(top + dy, bottom - self.MIN_H)
        if "s" in handle:
            bottom = max(bottom + dy, top + self.MIN_H)

        new_w = max(self.MIN_W, right - left)
        new_h = max(self.MIN_H, bottom - top)

        if lock_aspect and len(handle) == 2 and start_w > 0.001 and start_h > 0.001:
            ratio = start_w / start_h
            scale_x = new_w / start_w
            scale_y = new_h / start_h
            scale = scale_x if abs(scale_x - 1.0) >= abs(scale_y - 1.0) else scale_y
            new_w = max(self.MIN_W, start_w * max(0.01, scale))
            new_h = new_w / ratio
            if new_h < self.MIN_H:
                new_h = self.MIN_H
                new_w = new_h * ratio
            if "w" in handle:
                right = start_pos.x() + start_w
                left = right - new_w
            else:
                left = start_pos.x()
                right = left + new_w
            if "n" in handle:
                bottom = start_pos.y() + start_h
                top = bottom - new_h
            else:
                top = start_pos.y()
                bottom = top + new_h

        if (
            abs(new_w - self._width) < 0.01
            and abs(new_h - self._height) < 0.01
            and abs(left - self.pos().x()) < 0.01
            and abs(top - self.pos().y()) < 0.01
        ):
            return

        self.prepareGeometryChange()
        self._width = new_w
        self._height = new_h
        self.setPos(left, top)
        if self.text_fit:
            self._apply_text_style()
        self.layout_text()
        self.update()
        self.update_connections()
        self._notify_changed()

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._hovered = True
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._last_cursor = Qt.CursorShape.SizeAllCursor
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._hovered = False
        self._hover_port = None
        self.unsetCursor()
        self._last_cursor = None
        self.update()
        super().hoverLeaveEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        if self._editing:
            cursor = Qt.CursorShape.IBeamCursor
            handle = None
            port = None
        else:
            cursor = Qt.CursorShape.SizeAllCursor
            handle = self.handle_at(event.pos()) if self.isSelected() else None
            port = self.port_at(event.pos()) if self._ports_visible() else None
            if handle is not None:
                cursor = self.HANDLE_CURSORS[handle]
            elif port is not None:
                cursor = Qt.CursorShape.PointingHandCursor
        if port != self._hover_port:
            self._hover_port = port
            self.update()
        if cursor != self._last_cursor:
            self.setCursor(cursor)
            self._last_cursor = cursor
        super().hoverMoveEvent(event)

    # ---- scene integration ------------------------------------------------

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.update_connections()
            self._notify_changed()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self._hover_port = None
            self.update()
        return super().itemChange(change, value)

    def update_connections(self) -> None:
        for connection in list(self._connections):
            connection.update_path()
        scene = self.scene()
        if isinstance(scene, BoardScene) and scene.bundle_enabled:
            scene.refresh_connections()

    def set_ui_scale(self, scale: float) -> None:
        scale = max(0.05, float(scale))
        if abs(scale - self._ui_scale) < 1e-5:
            return
        if self.scene() is not None:
            self.prepareGeometryChange()
        self._ui_scale = scale
        self.update()

    def _notify_changed(self) -> None:
        scene = self.scene()
        if scene is not None and hasattr(scene, "notify_changed"):
            scene.notify_changed()

    # ---- serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        data = {
            "id": self.node_id,
            "type": self.TYPE,
            "x": round(float(self.pos().x()), 3),
            "y": round(float(self.pos().y()), 3),
            "w": round(float(self._width), 3),
            "h": round(float(self._height), 3),
            "z": float(self.zValue()),
            "radius": float(self.radius),
            "fill": color_name(self.fill),
            "border": color_name(self.border),
            "font_size": int(self.font_size),
            "font_family": self.font_family,
            "font_bold": bool(self.font_bold),
            "text_color": color_name(self.text_color),
            "text_align": self.text_align,
            "text_valign": self.text_valign,
            "text_fit": bool(self.text_fit),
        }
        if self.text_item is not None:
            data["text"] = self.text_item.toPlainText()
            data["html"] = self.text_item.toHtml()
        return data

    def apply_dict(self, data: dict) -> None:
        self.prepareGeometryChange()
        self._width = max(self.MIN_W, safe_float(data.get("w"), self._width))
        self._height = max(self.MIN_H, safe_float(data.get("h"), self._height))
        self.setPos(safe_float(data.get("x"), 0.0), safe_float(data.get("y"), 0.0))
        self.setZValue(safe_float(data.get("z"), self.zValue()))
        self.radius = clamp(safe_float(data.get("radius"), self.radius), 0.0, 240.0)
        self.fill = color_from(data.get("fill"), color_name(self.fill))
        self.border = color_from(data.get("border"), color_name(self.border))
        self.font_size = int(clamp(safe_float(data.get("font_size"), self.font_size), 6, 120))
        family = str(data.get("font_family") or self.font_family)
        if family:
            self.font_family = family
        self.font_bold = bool(data.get("font_bold", self.font_bold))
        self.text_color = color_from(data.get("text_color"), color_name(self.text_color))
        align = str(data.get("text_align", self.text_align))
        valign = str(data.get("text_valign", self.text_valign))
        self.text_align = align if align in TEXT_ALIGNS else self.text_align
        self.text_valign = valign if valign in TEXT_VALIGNS else self.text_valign
        self.text_fit = bool(data.get("text_fit", self.text_fit))
        if self.text_item is not None:
            self._suppress_text_signal = True
            html = data.get("html")
            if isinstance(html, str) and html.strip():
                self.text_item.setHtml(html)
            else:
                self.text_item.setPlainText(str(data.get("text", "")))
            self._suppress_text_signal = False
        self._apply_text_style()
        self.layout_text()
        self.update()


class TextNode(NodeItem):
    TYPE = "text"
    SUPPORTS_TEXT = True
    AUTO_HEIGHT = True
    DEFAULT_W = 280.0
    DEFAULT_H = 78.0
    MIN_W = 120.0
    MIN_H = 54.0
    PADDING = 17.0

    def __init__(self, node_id: Optional[str] = None, width: Optional[float] = None, height: Optional[float] = None):
        super().__init__(node_id=node_id, width=width, height=height)
        self.radius = 13.0
        self.fill = with_alpha(QColor(TEXT_NODE_FILL), 224)
        self.border = QColor(CARD_BORDER)
        self.font_size = 18
        self.text_color = QColor(TEXT_NODE_TEXT)
        self._apply_text_style()
        self.layout_text()
        self.set_text("New text", notify=False)

    def apply_dict(self, data: dict) -> None:
        super().apply_dict(data)
        self._fit_height_to_text()

    def paint_body(self, painter: QPainter) -> None:
        radius = self.corner_radius()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.fill)
        painter.drawRoundedRect(self.body_rect(), radius, radius)
        pen = QPen(self.border, 1.2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.body_rect().adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        if not self.text().strip() and not self._editing:
            self.paint_placeholder(painter, "Double-click to write", centered=False)


class CommentNode(TextNode):
    """A colorless comment/caption. It can never be linked to anything."""

    TYPE = "comment"
    LINKABLE = False
    SUPPORTS_TEXT = True
    AUTO_HEIGHT = True
    DEFAULT_W = 300.0
    DEFAULT_H = 58.0
    MIN_W = 90.0
    MIN_H = 38.0
    PADDING = 7.0

    def __init__(self, node_id: Optional[str] = None, width: Optional[float] = None, height: Optional[float] = None):
        super().__init__(node_id=node_id, width=width, height=height)
        self.radius = 0.0
        self.fill = QColor(0, 0, 0, 0)
        self.border = QColor(0, 0, 0, 0)
        self.font_size = 16
        self.text_color = QColor(COMMENT_TEXT)
        self._apply_text_style()
        self.layout_text()
        self.set_text("Comment", notify=False)
        self.setToolTip("Comment · drag to move · double-click to edit")
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def text_clip_rect(self) -> QRectF:
        return self.body_rect().adjusted(1.0, 1.0, -1.0, -1.0)

    def _paint_shadow(self, painter: QPainter) -> None:
        return

    def paint_body(self, painter: QPainter) -> None:
        if not self.text().strip() and not self._editing:
            self.paint_placeholder(painter, "Comment or caption", centered=False)


class ShapeNode(NodeItem):
    TYPE = "shape"
    SUPPORTS_TEXT = True
    TEXT_CENTER = True
    TEXT_VCENTER = True
    DEFAULT_W = 280.0
    DEFAULT_H = 170.0
    MIN_W = 64.0
    MIN_H = 54.0
    PADDING = 18.0

    def __init__(self, node_id: Optional[str] = None, width: Optional[float] = None, height: Optional[float] = None):
        super().__init__(node_id=node_id, width=width, height=height)
        self.shape_kind = "rectangle"
        self.radius = 22.0
        self.fill = QColor(SHAPE_FILL)
        self.border = QColor(ACCENT)
        self.font_size = 18
        self.font_bold = True
        self.text_color = QColor(SHAPE_TEXT)
        self._apply_text_style()
        self.layout_text()

    def paint_body(self, painter: QPainter) -> None:
        radius = self.corner_radius()
        rect = self.body_rect()
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        top = self.fill.lighter(113)
        top.setAlpha(self.fill.alpha())
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, self.fill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, radius, radius)
        pen = QPen(self.border, 1.6)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        if not self.text().strip() and not self._editing:
            self.paint_placeholder(painter, "Double-click to add text", centered=True)

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["shape_kind"] = self.shape_kind
        return data

    def apply_dict(self, data: dict) -> None:
        super().apply_dict(data)
        self.shape_kind = str(data.get("shape_kind", "rectangle"))


def pixmap_from_image_bytes(data: bytes, max_dimension: int = 5000) -> QPixmap:
    """Decode image bytes with EXIF rotation and a sane memory ceiling."""
    if not data:
        return QPixmap()
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    if not buffer.open(QIODevice.OpenModeFlag.ReadOnly):
        return QPixmap()
    reader = QImageReader(buffer)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > max_dimension:
        scale = max_dimension / float(max(size.width(), size.height()))
        reader.setScaledSize(QSize(max(1, int(size.width() * scale)), max(1, int(size.height() * scale))))
    image = reader.read()
    if image.isNull():
        return QPixmap()
    return QPixmap.fromImage(image)


class ImageNode(NodeItem):
    TYPE = "image"
    SUPPORTS_TEXT = False
    DEFAULT_W = 340.0
    DEFAULT_H = 240.0
    MIN_W = 64.0
    MIN_H = 54.0
    PADDING = 0.0

    def __init__(self, node_id: Optional[str] = None, width: Optional[float] = None, height: Optional[float] = None):
        super().__init__(node_id=node_id, width=width, height=height)
        self.radius = 15.0
        self.fill = QColor(IMAGE_FILL)
        self.border = QColor(IMAGE_BORDER)
        self._pixmap: Optional[QPixmap] = None
        self._image_bytes: Optional[bytes] = None
        self._image_name = ""

    def set_image_data(self, data: bytes, name: str = "", path: str = "") -> bool:
        pixmap = pixmap_from_image_bytes(data)
        if pixmap.isNull():
            return False
        self._image_bytes = bytes(data)
        self._pixmap = pixmap
        self._image_name = name or "image"
        self.setToolTip(f"{self._image_name} · drag to move · drag a port to connect")
        self.update()
        return True

    def image_size(self) -> QSize:
        return self._pixmap.size() if self._pixmap is not None else QSize(0, 0)

    def paint_body(self, painter: QPainter) -> None:
        rect = self.body_rect()
        radius = self.corner_radius()
        clip = QPainterPath()
        clip.addRoundedRect(rect, radius, radius)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(rect, self.fill)
        if self._pixmap is not None and not self._pixmap.isNull():
            iw = max(1.0, float(self._pixmap.width()))
            ih = max(1.0, float(self._pixmap.height()))
            scale = max(rect.width() / iw, rect.height() / ih)
            dw, dh = iw * scale, ih * scale
            target = QRectF((rect.width() - dw) / 2.0, (rect.height() - dh) / 2.0, dw, dh)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        else:
            painter.setPen(QPen(with_alpha(QColor(TEXT_MUTED), 140), 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            icon_rect = QRectF(rect.center().x() - 24, rect.center().y() - 34, 48, 40)
            painter.drawRoundedRect(icon_rect, 7, 7)
            path = QPainterPath(QPointF(icon_rect.left() + 6, icon_rect.bottom() - 7))
            path.lineTo(icon_rect.left() + 18, icon_rect.top() + 17)
            path.lineTo(icon_rect.left() + 28, icon_rect.top() + 27)
            path.lineTo(icon_rect.left() + 37, icon_rect.top() + 19)
            path.lineTo(icon_rect.right() - 5, icon_rect.bottom() - 7)
            painter.drawPath(path)
            painter.setPen(QColor(TEXT_FAINT))
            font = QFont("Segoe UI", 9)
            painter.setFont(font)
            painter.drawText(
                QRectF(rect.left(), rect.center().y() + 12, rect.width(), 24),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                "Image unavailable",
            )
        painter.restore()
        pen = QPen(self.border, 1.2)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)

    def to_dict(self) -> dict:
        data = super().to_dict()
        if self._image_bytes:
            data["image_data"] = base64.b64encode(self._image_bytes).decode("ascii")
        data["image_name"] = self._image_name
        return data

    def apply_dict(self, data: dict) -> None:
        super().apply_dict(data)
        self._image_name = str(data.get("image_name", "image"))
        encoded = data.get("image_data")
        if encoded:
            try:
                raw = base64.b64decode(str(encoded))
            except (ValueError, TypeError):
                raw = b""
            if raw:
                self.set_image_data(raw, self._image_name)
        self.setToolTip(f"{self._image_name} · drag to move · drag a port to connect")


def node_from_dict(data: dict) -> Optional[NodeItem]:
    if not isinstance(data, dict):
        return None
    kind = str(data.get("type", "")).lower()
    node_id = str(data.get("id") or uuid.uuid4().hex)
    width = max(10.0, safe_float(data.get("w"), 200.0))
    height = max(10.0, safe_float(data.get("h"), 100.0))
    if kind == "text":
        node: NodeItem = TextNode(node_id=node_id, width=width, height=height)
    elif kind == "comment":
        node = CommentNode(node_id=node_id, width=width, height=height)
    elif kind == "shape":
        node = ShapeNode(node_id=node_id, width=width, height=height)
    elif kind == "image":
        node = ImageNode(node_id=node_id, width=width, height=height)
    else:
        return None
    node.apply_dict(data)
    return node


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


class ConnectionItem(QGraphicsObject):
    """A live connection between two node ports."""

    def __init__(
        self,
        source: NodeItem,
        source_port: str,
        target: NodeItem,
        target_port: str,
        style: str = "thick",
        weight: Optional[str] = None,
        dash: Optional[str] = None,
        route: Optional[str] = None,
        color: Optional[QColor] = None,
    ):
        super().__init__()
        self.source = source
        self.source_port = source_port
        self.target = target
        self.target_port = target_port
        legacy = style if style in ("thick", "thin") else "thick"
        self.line_weight = weight if weight in LINE_WEIGHTS else ("thin" if legacy == "thin" else "thick")
        self.dash_style = dash if dash in LINE_DASHES else ("dashed" if legacy == "thin" else "solid")
        self.route = route if route in LINE_ROUTES else "curve"
        if color is None:
            self.line_color = QColor("#8298B8" if legacy == "thin" else ACCENT)
        else:
            chosen = QColor(color) if isinstance(color, QColor) else QColor(str(color))
            self.line_color = chosen if chosen.isValid() else QColor(ACCENT)
        self._path = QPainterPath()
        self._ui_scale = 1.0
        self._attach_preview = False
        self._press_scene: Optional[QPointF] = None
        self._press_time = 0.0
        self._moved = False
        self._relinking = False
        self._relink_end = "source"
        self._relink_target: Optional[tuple[NodeItem, str]] = None
        self._relink_temp: Optional[QGraphicsPathItem] = None
        self._long_press = QTimer(self)
        self._long_press.setSingleShot(True)
        self._long_press.timeout.connect(self._on_long_press)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton)
        self.setAcceptHoverEvents(True)
        self.setZValue(-10.0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(
            "Click to select · double-click to remove · drag an end to relink · "
            "scroll to change style · middle-click to change thickness"
        )
        source._connections.add(self)
        target._connections.add(self)
        self.update_path()

    # ---- geometry ---------------------------------------------------------

    def _line_width_px(self) -> float:
        return LINE_WIDTH_PX.get(self.line_weight, LINE_WIDTH_PX["thick"])

    def update_path(self) -> None:
        if self.source is None or self.target is None:
            return
        try:
            start = self.source.port_scene_pos(self.source_port)
            end = self.target.port_scene_pos(self.target_port)
        except RuntimeError:
            return
        d1 = self.source.port_direction(self.source_port)
        d2 = self.target.port_direction(self.target_port)
        extra_start = self._bundle_extension("source")
        extra_end = self._bundle_extension("target")
        if self.route == "straight":
            path = QPainterPath(start)
            path.lineTo(end)
        elif self.route == "elbow":
            path = self._elbow_path(start, d1, end, d2, extra_start, extra_end)
        else:
            distance = QLineF(start, end).length()
            strength = clamp(distance * 0.44, 14.0, 240.0)
            c1 = QPointF(
                start.x() + d1.x() * (strength + extra_start),
                start.y() + d1.y() * (strength + extra_start),
            )
            c2 = QPointF(
                end.x() + d2.x() * (strength + extra_end),
                end.y() + d2.y() * (strength + extra_end),
            )
            path = QPainterPath(start)
            path.cubicTo(c1, c2, end)
        self.prepareGeometryChange()
        self._path = path
        self.update()

    def _port_group(self, end: str) -> list["ConnectionItem"]:
        scene = self.scene()
        if not isinstance(scene, BoardScene) or not scene.bundle_enabled:
            return [self]
        node = self.source if end == "source" else self.target
        port = self.source_port if end == "source" else self.target_port
        if node is None or port is None:
            return [self]
        members: list[ConnectionItem] = []
        for connection in scene.connections:
            try:
                if end == "source":
                    if connection.source is node and connection.source_port == port:
                        members.append(connection)
                else:
                    if connection.target is node and connection.target_port == port:
                        members.append(connection)
            except RuntimeError:
                continue
        return members or [self]

    def _anchor_points(self, connection: "ConnectionItem"):
        try:
            start = connection.source.port_scene_pos(connection.source_port)
            finish = connection.target.port_scene_pos(connection.target_port)
            d1 = connection.source.port_direction(connection.source_port)
            d2 = connection.target.port_direction(connection.target_port)
        except (RuntimeError, AttributeError):
            return None
        return start, d1, finish, d2

    def _bundle_extension(self, end: str) -> float:
        """Distance shared by every link in one port group so bundles stay aligned."""
        members = self._port_group(end)
        if len(members) <= 1:
            return 0.0
        return clamp(BUNDLE_SPACING * 2.4 * (len(members) - 1), 0.0, 90.0)

    def _shared_lead(self, end: str) -> float:
        """Stub length that every link on this port leaves with, so trunks line up."""
        members = self._port_group(end)
        lengths: list[float] = []
        for connection in members:
            anchors = self._anchor_points(connection)
            if anchors is None:
                continue
            start, _d1, finish, _d2 = anchors
            lengths.append(QLineF(start, finish).length())
        lengths.sort()
        reference = lengths[len(lengths) // 2] if lengths else 120.0
        lead = clamp(reference * 0.22, 24.0, 90.0)
        limit = max(18.0, lengths[0] * 0.42) if lengths else 60.0
        return min(lead + self._bundle_extension(end), limit)

    @staticmethod
    def _axis_sign(value: float) -> float:
        return 1.0 if value > 0.0 else -1.0 if value < 0.0 else 0.0

    @staticmethod
    def _fit_lane(value: float, first: float, second: float, direction: float, approach: float) -> float:
        """Keep a shared lane usable for this link; short links fall back to a midpoint."""
        if direction * approach <= 0:
            return value
        low, high = (first, second) if first <= second else (second, first)
        if high - low < 0.6:
            return (low + high) / 2.0
        margin = min(8.0, (high - low) * 0.35)
        return clamp(value, low + margin, high - margin)

    def _lane(self, axis: str, a: QPointF, b: QPointF, u: QPointF, v: QPointF) -> float:
        """Return one lane coordinate shared by the whole bundle on the driving side."""
        if axis == "x":
            first, second = a.x(), b.x()
            direction = self._axis_sign(u.x())
            approach = self._axis_sign(v.x())
        else:
            first, second = a.y(), b.y()
            direction = self._axis_sign(u.y())
            approach = self._axis_sign(v.y())

        source_group = self._port_group("source")
        target_group = self._port_group("target")
        driver = "source" if len(source_group) >= len(target_group) else "target"
        members = source_group if driver == "source" else target_group

        spans: list[tuple[float, float]] = []
        for connection in members:
            anchors = self._anchor_points(connection)
            if anchors is None:
                continue
            start, d1, finish, d2 = anchors
            lead_start = connection._shared_lead("source")
            lead_end = connection._shared_lead("target")
            if axis == "x":
                spans.append(
                    (
                        start.x() + d1.x() * lead_start,
                        finish.x() + d2.x() * lead_end,
                    )
                )
            else:
                spans.append(
                    (
                        start.y() + d1.y() * lead_start,
                        finish.y() + d2.y() * lead_end,
                    )
                )
        if not spans:
            spans = [(first, second)]

        if direction * approach > 0:
            gaps = [
                (anchor_end - anchor_start) * direction
                for anchor_start, anchor_end in spans
                if (anchor_end - anchor_start) * direction > 0.5
            ]
            if gaps:
                span = max(1.0, min(gaps))
                offset = max(16.0, span * 0.5)
                if driver == "source":
                    return first + direction * offset
                return second - approach * offset

        values = [first, second]
        for anchor_start, anchor_end in spans:
            values.extend((anchor_start, anchor_end))
        if direction > 0:
            return max(values) + 18.0
        return min(values) - 18.0

    def _channel_y(self, a: QPointF, b: QPointF, lead: float) -> float:
        tops: list[float] = []
        bottoms: list[float] = []
        for node in (self.source, self.target):
            try:
                rect = node.sceneBoundingRect()
            except (RuntimeError, AttributeError):
                continue
            tops.append(rect.top())
            bottoms.append(rect.bottom())
        top = min(tops + [a.y(), b.y()]) - lead
        bottom = max(bottoms + [a.y(), b.y()]) + lead
        if abs(a.y() - top) + abs(b.y() - top) <= abs(a.y() - bottom) + abs(b.y() - bottom):
            return top
        return bottom

    def _channel_x(self, a: QPointF, b: QPointF, lead: float) -> float:
        lefts: list[float] = []
        rights: list[float] = []
        for node in (self.source, self.target):
            try:
                rect = node.sceneBoundingRect()
            except (RuntimeError, AttributeError):
                continue
            lefts.append(rect.left())
            rights.append(rect.right())
        left = min(lefts + [a.x(), b.x()]) - lead
        right = max(rights + [a.x(), b.x()]) + lead
        if abs(a.x() - left) + abs(b.x() - left) <= abs(a.x() - right) + abs(b.x() - right):
            return left
        return right

    def _elbow_path(
        self,
        start: QPointF,
        d1: QPointF,
        end: QPointF,
        d2: QPointF,
        extra_start: float = 0.0,
        extra_end: float = 0.0,
    ) -> QPainterPath:
        lead_start = self._shared_lead("source")
        lead_end = self._shared_lead("target")
        a = QPointF(start.x() + d1.x() * lead_start, start.y() + d1.y() * lead_start)
        b = QPointF(end.x() + d2.x() * lead_end, end.y() + d2.y() * lead_end)
        u = QPointF(d1.x(), d1.y())
        v = QPointF(-d2.x(), -d2.y())
        horizontal_start = abs(u.x()) >= abs(u.y())
        horizontal_end = abs(v.x()) >= abs(v.y())
        if horizontal_start == horizontal_end:
            axis_x = horizontal_start
            direction = self._axis_sign(u.x() if axis_x else u.y())
            start_axis = start.x() if axis_x else start.y()
            end_axis = end.x() if axis_x else end.y()
            anchor_a = a.x() if axis_x else a.y()
            anchor_b = b.x() if axis_x else b.y()
            if (anchor_b - anchor_a) * direction <= 0.2:
                gap_axis = (end_axis - start_axis) * direction
                if gap_axis > 8.0:
                    first_len = gap_axis * 0.5
                    second_len = gap_axis - first_len
                    a = QPointF(
                        start.x() + d1.x() * first_len,
                        start.y() + d1.y() * first_len,
                    )
                    b = QPointF(
                        end.x() + d2.x() * second_len,
                        end.y() + d2.y() * second_len,
                    )
        lead = max(18.0, min(lead_start, lead_end))

        points: list[QPointF] = [a]
        if horizontal_start and horizontal_end:
            lane = self._lane("x", a, b, u, v)
            direction = self._axis_sign(u.x())
            approach = self._axis_sign(v.x())
            lane = self._fit_lane(lane, a.x(), b.x(), direction, approach)
            first_ok = (lane - a.x()) * direction >= -0.2
            second_ok = (b.x() - lane) * approach >= -0.2
            flat = direction * approach < 0 and abs(b.y() - a.y()) < 3.0
            if first_ok and second_ok and not flat:
                points.extend([QPointF(lane, a.y()), QPointF(lane, b.y())])
            else:
                channel = self._channel_y(a, b, lead)
                x1 = a.x() + u.x() * lead
                x2 = b.x() - v.x() * lead
                points.extend(
                    [
                        QPointF(x1, a.y()),
                        QPointF(x1, channel),
                        QPointF(x2, channel),
                        QPointF(x2, b.y()),
                    ]
                )
        elif (not horizontal_start) and (not horizontal_end):
            lane = self._lane("y", a, b, u, v)
            direction = self._axis_sign(u.y())
            approach = self._axis_sign(v.y())
            lane = self._fit_lane(lane, a.y(), b.y(), direction, approach)
            first_ok = (lane - a.y()) * direction >= -0.2
            second_ok = (b.y() - lane) * approach >= -0.2
            flat = direction * approach < 0 and abs(b.x() - a.x()) < 3.0
            if first_ok and second_ok and not flat:
                points.extend([QPointF(a.x(), lane), QPointF(b.x(), lane)])
            else:
                channel = self._channel_x(a, b, lead)
                y1 = a.y() + u.y() * lead
                y2 = b.y() - v.y() * lead
                points.extend(
                    [
                        QPointF(a.x(), y1),
                        QPointF(channel, y1),
                        QPointF(channel, y2),
                        QPointF(b.x(), y2),
                    ]
                )
        else:
            if horizontal_start:
                corner = QPointF(b.x(), a.y())
                valid = (
                    (b.x() - a.x()) * u.x() >= -0.2
                    and (b.y() - a.y()) * v.y() >= -0.2
                )
            else:
                corner = QPointF(a.x(), b.y())
                valid = (
                    (b.y() - a.y()) * u.y() >= -0.2
                    and (b.x() - a.x()) * v.x() >= -0.2
                )
            if valid:
                points.append(corner)
            elif horizontal_start:
                x1 = a.x() + u.x() * lead
                y2 = b.y() - v.y() * lead
                points.extend(
                    [
                        QPointF(x1, a.y()),
                        QPointF(x1, y2),
                        QPointF(b.x(), y2),
                    ]
                )
            else:
                y1 = a.y() + u.y() * lead
                x2 = b.x() - v.x() * lead
                points.extend(
                    [
                        QPointF(a.x(), y1),
                        QPointF(x2, y1),
                        QPointF(x2, b.y()),
                    ]
                )
        points.append(b)
        points.append(end)

        cleaned: list[QPointF] = []
        for point in points:
            if (
                not cleaned
                or abs(point.x() - cleaned[-1].x()) > 0.2
                or abs(point.y() - cleaned[-1].y()) > 0.2
            ):
                cleaned.append(point)
        simplified: list[QPointF] = []
        for point in cleaned:
            if len(simplified) >= 2:
                previous = simplified[-2]
                last = simplified[-1]
                same_x = abs(previous.x() - last.x()) < 0.2 and abs(last.x() - point.x()) < 0.2
                same_y = abs(previous.y() - last.y()) < 0.2 and abs(last.y() - point.y()) < 0.2
                if same_x or same_y:
                    forward = (last.x() - previous.x()) * (point.x() - last.x()) + (
                        last.y() - previous.y()
                    ) * (point.y() - last.y())
                    if forward > 0.0:
                        simplified[-1] = point
                        continue
            simplified.append(point)
        if not simplified:
            return QPainterPath(start)
        path = QPainterPath(simplified[0])
        for point in simplified[1:]:
            path.lineTo(point)
        return path

    def set_ui_scale(self, scale: float) -> None:
        scale = max(0.05, float(scale))
        if abs(scale - self._ui_scale) < 1e-5:
            return
        self.prepareGeometryChange()
        self._ui_scale = scale
        self.update()

    def boundingRect(self) -> QRectF:
        if self._path.isEmpty():
            return QRectF()
        margin = self._ui_px(20.0)
        return self._path.boundingRect().adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        if self._path.isEmpty():
            return QPainterPath()
        stroker = QPainterPathStroker()
        stroker.setWidth(self._ui_px(max(16.0, self._line_width_px() + 8.0)))
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return stroker.createStroke(self._path)

    def _ui_px(self, pixels: float) -> float:
        return pixels / max(0.08, self._ui_scale)

    # ---- rendering --------------------------------------------------------

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:
        if self._path.isEmpty():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        highlighted = self.isSelected() or self.isUnderMouse()
        width_px = self._line_width_px()
        if self._attach_preview:
            attach_glow = QPen(QColor(255, 202, 63, 150), max(13.0, width_px + 10.0))
            attach_glow.setCosmetic(True)
            attach_glow.setCapStyle(Qt.PenCapStyle.RoundCap)
            attach_glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(attach_glow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._path)
        if highlighted:
            glow = QPen(
                with_alpha(QColor(ACCENT_LIGHT), 62 if self.isSelected() else 28),
                max(12.0, width_px + 8.0),
            )
            glow.setCosmetic(True)
            glow.setCapStyle(Qt.PenCapStyle.RoundCap)
            glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(glow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self._path)

        color = QColor(self.line_color)
        if highlighted:
            color = color.lighter(135)
        pen = QPen(color, width_px)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if self.dash_style == "dashed":
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern(
                [max(0.7, 6.0 / max(0.5, width_px)), max(0.5, 4.0 / max(0.5, width_px))]
            )
        elif self.dash_style == "dotted":
            pen.setStyle(Qt.PenStyle.CustomDashLine)
            pen.setDashPattern([0.01, max(2.0, 7.0 / max(0.5, width_px))])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)

        dot_radius = self._ui_px(3.2 if width_px >= 4.0 else 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#DCEBFF") if highlighted else QColor(color))
        painter.drawEllipse(self._path.pointAtPercent(0.0), dot_radius, dot_radius)
        painter.drawEllipse(self._path.pointAtPercent(1.0), dot_radius, dot_radius)

    # ---- interaction ------------------------------------------------------

    def set_style(self, style: str, notify: bool = True) -> None:
        style = style if style in ("thick", "thin") else "thick"
        weight = "thin" if style == "thin" else "thick"
        dash = "dashed" if style == "thin" else "solid"
        if weight == self.line_weight and dash == self.dash_style:
            return
        self.line_weight = weight
        self.dash_style = dash
        self.update()
        if notify:
            self._notify_changed()

    def set_weight(self, weight: str, notify: bool = True) -> None:
        if weight not in LINE_WEIGHTS or weight == self.line_weight:
            return
        self.line_weight = weight
        self.update()
        if notify:
            self._notify_changed()

    def set_dash_style(self, dash: str, notify: bool = True) -> None:
        if dash not in LINE_DASHES or dash == self.dash_style:
            return
        self.dash_style = dash
        self.update()
        if notify:
            self._notify_changed()

    def set_route(self, route: str, notify: bool = True) -> None:
        if route not in LINE_ROUTES or route == self.route:
            return
        self.route = route
        self.update_path()
        if notify:
            self._notify_changed()

    def set_line_color(self, color: QColor, notify: bool = True) -> None:
        if not color.isValid() or color == self.line_color:
            return
        self.line_color = QColor(color)
        self.update()
        if notify:
            self._notify_changed()

    def _notify_changed(self) -> None:
        scene = self.scene()
        if scene is not None and hasattr(scene, "notify_changed"):
            scene.notify_changed()

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self.update()
        super().hoverLeaveEvent(event)

    # ---- click/release, drag to relink, wheel to restyle ------------------

    def _nearest_end(self, scene_pos: QPointF) -> str:
        if self._path.isEmpty():
            return "source"
        start = self._path.pointAtPercent(0.0)
        finish = self._path.pointAtPercent(1.0)
        return "source" if QLineF(start, scene_pos).length() <= QLineF(finish, scene_pos).length() else "target"

    def _style_changed_hint(self, text: str) -> None:
        scene = self.scene()
        if scene is None:
            return
        views = scene.views()
        window = views[0].window() if views else None
        if window is not None and hasattr(window, "_sync_properties"):
            window._sync_properties()
        if window is not None and hasattr(window, "_flash_hint"):
            window._flash_hint(text)

    def cycle_dash_style(self, direction: int = 1) -> None:
        sequence = ("solid", "dashed", "dotted")
        index = sequence.index(self.dash_style) if self.dash_style in sequence else 0
        self.set_dash_style(sequence[(index + (1 if direction >= 0 else -1)) % len(sequence)])
        self.setSelected(True)
        labels = {"solid": "Solid", "dashed": "Dashed", "dotted": "Dotted"}
        self._style_changed_hint(f"Line type: {labels.get(self.dash_style, self.dash_style)}")

    def cycle_weight(self) -> None:
        sequence = ("thin", "medium", "thick")
        index = sequence.index(self.line_weight) if self.line_weight in sequence else 0
        self.set_weight(sequence[(index + 1) % len(sequence)])
        self.setSelected(True)
        self._style_changed_hint(f"Line thickness: {self.line_weight.capitalize()}")

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self.cycle_weight()
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton or self._path.isEmpty():
            super().mousePressEvent(event)
            return
        self._relink_end = self._nearest_end(event.scenePos())
        self._press_scene = QPointF(event.scenePos())
        self._press_time = time.monotonic()
        self._moved = False
        self._long_press.start(430)
        scene = self.scene()
        if scene is not None and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            scene.clearSelection()
        self.setSelected(True)
        event.accept()

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._relinking:
            self._update_relink(event.scenePos())
            event.accept()
            return
        if self._press_scene is None:
            super().mouseMoveEvent(event)
            return
        if QLineF(self._press_scene, event.scenePos()).length() > self._ui_px(5.0):
            self._long_press.stop()
            if not self._moved:
                self._moved = True
                self._begin_relink()
        if self._relinking:
            self._update_relink(event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._long_press.stop()
        if self._relinking:
            self._finish_relink(event.scenePos())
            self._press_scene = None
            event.accept()
            return
        self._press_scene = None
        event.accept()

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        self._long_press.stop()
        self._press_scene = None
        self._cleanup_relink()
        QTimer.singleShot(0, self._remove_self)
        event.accept()

    def _remove_self(self) -> None:
        try:
            scene = self.scene()
        except RuntimeError:
            return
        if scene is not None:
            scene.remove_connection(self)

    def wheelEvent(self, event) -> None:
        if self._path.isEmpty():
            event.ignore()
            return
        self.cycle_dash_style(1 if event.angleDelta().y() < 0 else -1)
        event.accept()

    def _on_long_press(self) -> None:
        if self._press_scene is None or self._moved or self._relinking:
            return
        self._begin_relink()

    def _begin_relink(self) -> None:
        scene = self.scene()
        if scene is None or self.source is None or self.target is None:
            return
        self._relinking = True
        self.setSelected(True)
        pen = QPen(QColor(255, 202, 63, 230), 2.4)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setDashPattern([5.0, 4.0])
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        temp = QGraphicsPathItem()
        temp.setPen(pen)
        temp.setZValue(10001.0)
        scene.addItem(temp)
        self._relink_temp = temp
        scene._set_view_cursor(Qt.CursorShape.CrossCursor)
        self._update_relink(self._press_scene or self._path.pointAtPercent(0.5))

    def _fixed_relink_end(self) -> tuple[Optional[NodeItem], Optional[str]]:
        if self._relink_end == "source":
            return self.target, self.target_port
        return self.source, self.source_port

    def _clear_relink_target(self) -> None:
        if self._relink_target is not None:
            node = self._relink_target[0]
            try:
                node._target_port = None
                node.update()
            except RuntimeError:
                pass
        self._relink_target = None

    def _update_relink(self, scene_pos: QPointF) -> None:
        scene = self.scene()
        fixed_node, fixed_port = self._fixed_relink_end()
        if scene is None or fixed_node is None or fixed_port is None:
            return
        target = scene.find_port_target(scene_pos, exclude=fixed_node)
        self._clear_relink_target()
        if target is not None:
            node, port = target
            self._relink_target = target
            node._target_port = port
            node.update()
            end = node.port_scene_pos(port)
            end_direction = node.port_direction(port)
        else:
            end = scene_pos
            end_direction = None
        try:
            start = fixed_node.port_scene_pos(fixed_port)
            direction = fixed_node.port_direction(fixed_port)
        except RuntimeError:
            return
        if self._relink_temp is not None:
            self._relink_temp.setPath(self._connection_curve(start, direction, end, end_direction))

    def _connection_curve(
        self, start: QPointF, direction: QPointF, end: QPointF, end_direction: Optional[QPointF]
    ) -> QPainterPath:
        distance = QLineF(start, end).length()
        strength = clamp(distance * 0.44, 14.0, 240.0)
        c1 = QPointF(start.x() + direction.x() * strength, start.y() + direction.y() * strength)
        if end_direction is None:
            c2 = QPointF(end.x(), end.y())
        else:
            c2 = QPointF(
                end.x() + end_direction.x() * strength,
                end.y() + end_direction.y() * strength,
            )
        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)
        return path

    def _finish_relink(self, scene_pos: QPointF) -> None:
        scene = self.scene()
        fixed_node, fixed_port = self._fixed_relink_end()
        target = scene.find_port_target(scene_pos, exclude=fixed_node) if scene is not None else None
        moving = self.source if self._relink_end == "source" else self.target
        if (
            scene is not None
            and target is not None
            and moving is not None
            and fixed_node is not None
            and fixed_port is not None
            and target[0] is not moving
        ):
            node, port = target
            if self._relink_end == "source":
                duplicate = scene.connection_exists_excluding(
                    self, node, port, fixed_node, fixed_port
                )
            else:
                duplicate = scene.connection_exists_excluding(
                    self, fixed_node, fixed_port, node, port
                )
            if not duplicate:
                if self._relink_end == "source":
                    if self.source is not None:
                        self.source._connections.discard(self)
                    self.source = node
                    self.source_port = port
                else:
                    if self.target is not None:
                        self.target._connections.discard(self)
                    self.target = node
                    self.target_port = port
                node._connections.add(self)
                self.update_path()
                scene.notify_changed()
        self._cleanup_relink()

    def _cleanup_relink(self) -> None:
        self._clear_relink_target()
        if self._relink_temp is not None:
            scene = self.scene()
            try:
                if scene is not None and self._relink_temp.scene() is scene:
                    scene.removeItem(self._relink_temp)
            except RuntimeError:
                pass
            self._relink_temp = None
        self._relinking = False
        self._press_scene = None
        scene = self.scene()
        if isinstance(scene, BoardScene) and scene._connection_source is None:
            scene._set_view_cursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

    def detach(self) -> None:
        self._cleanup_relink()
        self._long_press.stop()
        if self.source is not None:
            self.source._connections.discard(self)
        if self.target is not None:
            self.target._connections.discard(self)
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)

    def to_dict(self) -> dict:
        return {
            "source": self.source.node_id if self.source is not None else "",
            "source_port": self.source_port,
            "target": self.target.node_id if self.target is not None else "",
            "target_port": self.target_port,
            "style": "thin" if self.line_weight == "thin" else "thick",
            "weight": self.line_weight,
            "dash": self.dash_style,
            "route": self.route,
            "color": color_name(self.line_color),
        }


# ---------------------------------------------------------------------------
# Board scene
# ---------------------------------------------------------------------------


class BoardScene(QGraphicsScene):
    content_changed = pyqtSignal()
    editing_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-250000.0, -250000.0, 500000.0, 500000.0)
        self.nodes: list[NodeItem] = []
        self.connections: list[ConnectionItem] = []
        self.grid_enabled = True
        self.magnet_enabled = True
        self.inherit_enabled = True
        self.bundle_enabled = True
        self.default_line_style = "thick"
        self.default_line_weight = "thick"
        self.default_line_dash = "solid"
        self.default_line_route = "curve"
        self.default_line_color = QColor(ACCENT)
        self.default_shape_fill = QColor(SHAPE_FILL)
        self.default_shape_border = QColor(ACCENT)
        self.default_shape_radius = 22.0
        self.default_font_size = 18
        self.default_font_family = "Segoe UI"
        self.default_text_color = QColor(TEXT_NODE_TEXT)
        self.default_text_align: Optional[str] = None
        self.default_text_valign: Optional[str] = None
        self.default_text_fit = False
        self._next_z = 20.0
        self._loading = False
        self._editing_node: Optional[NodeItem] = None
        self._connection_source: Optional[NodeItem] = None
        self._connection_source_port: Optional[str] = None
        self._temp_connection: Optional[QGraphicsPathItem] = None
        self._target_node: Optional[NodeItem] = None
        self._target_port: Optional[str] = None
        self._guide_items: list[QGraphicsLineItem] = []
        self._line_attach_preview: Optional[ConnectionItem] = None
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)

    # ---- background -------------------------------------------------------

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor(BG_COLOR))
        if not self.grid_enabled:
            return

        scale = self.view_scale()
        spacing = 24.0
        while spacing * scale < 16.0:
            spacing *= 2.0
        while spacing * scale > 46.0:
            spacing /= 2.0

        left = math.floor(rect.left() / spacing) * spacing
        top = math.floor(rect.top() / spacing) * spacing
        right = rect.right()
        bottom = rect.bottom()
        major = spacing * 4.0

        minor_pen = QPen(CANVAS_GRID_MINOR, 1.15)
        minor_pen.setCosmetic(True)
        major_pen = QPen(CANVAS_GRID_MAJOR, 2.15)
        major_pen.setCosmetic(True)

        painter.setPen(minor_pen)
        y = top
        major_y = round(top / major) * major
        while y <= bottom:
            x = left
            while x <= right:
                painter.drawPoint(QPointF(x, y))
                x += spacing
            y += spacing

        painter.setPen(major_pen)
        y = major_y
        while y <= bottom:
            x = round(left / major) * major
            while x <= right:
                painter.drawPoint(QPointF(x, y))
                x += major
            y += major

    def view_scale(self) -> float:
        views = self.views()
        if not views:
            return 1.0
        return max(0.02, views[0].transform().m11())

    def refresh_ui_scale(self, scale: Optional[float] = None) -> None:
        scale = scale if scale is not None else self.view_scale()
        for node in list(self.nodes):
            try:
                node.set_ui_scale(scale)
            except RuntimeError:
                continue
        for connection in list(self.connections):
            try:
                connection.set_ui_scale(scale)
                connection.update_path()
            except RuntimeError:
                continue
        self.update()

    def refresh_connections(self, exclude: Optional[ConnectionItem] = None) -> None:
        for connection in list(self.connections):
            if connection is exclude:
                continue
            try:
                connection.update_path()
            except RuntimeError:
                continue

    def set_grid_enabled(self, enabled: bool, notify: bool = True) -> None:
        enabled = bool(enabled)
        if self.grid_enabled == enabled:
            return
        self.grid_enabled = enabled
        self.update()
        if notify:
            self.notify_changed()

    def set_magnet_enabled(self, enabled: bool, notify: bool = True) -> None:
        enabled = bool(enabled)
        if self.magnet_enabled == enabled:
            return
        self.magnet_enabled = enabled
        self.clear_guides()
        if notify:
            self.notify_changed()

    def set_inherit_enabled(self, enabled: bool, notify: bool = True) -> None:
        enabled = bool(enabled)
        if self.inherit_enabled == enabled:
            return
        self.inherit_enabled = enabled
        if notify:
            self.notify_changed()

    def set_bundle_enabled(self, enabled: bool, notify: bool = True) -> None:
        enabled = bool(enabled)
        if self.bundle_enabled == enabled:
            return
        self.bundle_enabled = enabled
        for connection in list(self.connections):
            try:
                connection.update_path()
            except RuntimeError:
                continue
        if notify:
            self.notify_changed()

    # ---- magnet alignment -------------------------------------------------

    def clear_guides(self) -> None:
        for item in self._guide_items:
            try:
                if item.scene() is self:
                    self.removeItem(item)
            except RuntimeError:
                continue
        self._guide_items.clear()

    def _add_guide(self, vertical: bool, coordinate: float, low: float, high: float) -> None:
        line = QGraphicsLineItem()
        pen = QPen(QColor(ACCENT_LIGHT), 1.1, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        pen.setDashPattern([4.0, 3.0])
        line.setPen(pen)
        line.setZValue(9998.0)
        line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        if vertical:
            line.setLine(coordinate, low, coordinate, high)
        else:
            line.setLine(low, coordinate, high, coordinate)
        self.addItem(line)
        self._guide_items.append(line)

    def apply_magnet(self, node: NodeItem, ctrl: bool = False) -> Optional[QPointF]:
        if not isinstance(node, NodeItem) or not node._ready or node._editing:
            return None
        if not (self.magnet_enabled or ctrl):
            self.clear_guides()
            return None
        if not self.nodes:
            return None
        scale = self.view_scale()
        threshold = 8.0 / max(0.08, scale)
        width = node._width
        height = node._height
        left = node.pos().x()
        top = node.pos().y()
        others = [item for item in self.nodes if item is not node and item is not None and not item.isSelected()]

        best_x: Optional[tuple[float, float, Optional[QRectF], float]] = None
        best_y: Optional[tuple[float, float, Optional[QRectF], float]] = None

        for other in others:
            try:
                other_rect = QRectF(other.pos().x(), other.pos().y(), other._width, other._height)
            except RuntimeError:
                continue
            for own_offset in (0.0, width / 2.0, width):
                own_x = left + own_offset
                for target_x in (other_rect.left(), other_rect.center().x(), other_rect.right()):
                    delta = target_x - own_x
                    if abs(delta) <= threshold and (best_x is None or abs(delta) < abs(best_x[0])):
                        best_x = (abs(delta), delta, other_rect, target_x)
            for own_offset in (0.0, height / 2.0, height):
                own_y = top + own_offset
                for target_y in (other_rect.top(), other_rect.center().y(), other_rect.bottom()):
                    delta = target_y - own_y
                    if abs(delta) <= threshold and (best_y is None or abs(delta) < abs(best_y[0])):
                        best_y = (abs(delta), delta, other_rect, target_y)

        if self.grid_enabled:
            for own_offset in (0.0, width / 2.0, width):
                own_x = left + own_offset
                target_x = round(own_x / MAGNET_GRID) * MAGNET_GRID
                delta = target_x - own_x
                if abs(delta) <= threshold and (best_x is None or abs(delta) < abs(best_x[0])):
                    best_x = (abs(delta), delta, None, target_x)
            for own_offset in (0.0, height / 2.0, height):
                own_y = top + own_offset
                target_y = round(own_y / MAGNET_GRID) * MAGNET_GRID
                delta = target_y - own_y
                if abs(delta) <= threshold and (best_y is None or abs(delta) < abs(best_y[0])):
                    best_y = (abs(delta), delta, None, target_y)

        dx = best_x[1] if best_x is not None else 0.0
        dy = best_y[1] if best_y is not None else 0.0
        if abs(dx) > 0.001 or abs(dy) > 0.001:
            node.setPos(left + dx, top + dy)

        self.clear_guides()
        new_left = left + dx
        new_top = top + dy
        if best_x is not None:
            other_rect = best_x[2]
            coordinate = best_x[3]
            low = new_top
            high = new_top + height
            if other_rect is not None:
                low = min(low, other_rect.top())
                high = max(high, other_rect.bottom())
            self._add_guide(True, coordinate, low - 14.0, high + 14.0)
        if best_y is not None:
            other_rect = best_y[2]
            coordinate = best_y[3]
            low = new_left
            high = new_left + width
            if other_rect is not None:
                low = min(low, other_rect.left())
                high = max(high, other_rect.right())
            self._add_guide(False, coordinate, low - 14.0, high + 14.0)
        if abs(dx) > 0.001 or abs(dy) > 0.001:
            return QPointF(dx, dy)
        return None

    # ---- node-to-line attachment -----------------------------------------

    def line_attach_preview(self, node: NodeItem) -> Optional["ConnectionItem"]:
        preview = self._line_attach_preview
        if preview is None:
            return None
        if preview.source is node or preview.target is node:
            return None
        return preview

    def clear_line_attach_preview(self) -> None:
        preview = self._line_attach_preview
        if preview is not None:
            try:
                preview._attach_preview = False
                preview.update()
            except RuntimeError:
                pass
        self._line_attach_preview = None

    def _line_attach_candidate(self, node: NodeItem) -> Optional["ConnectionItem"]:
        if not node.LINKABLE or node._editing:
            return None
        try:
            center = node.mapToScene(node.body_rect().center())
        except RuntimeError:
            return None
        needed = max(node._width, node._height) * 1.05
        limit = max(150.0, max(node._width, node._height) * 0.95)
        best: Optional[tuple[float, ConnectionItem]] = None
        for connection in self.connections:
            if connection.source is node or connection.target is node:
                continue
            if connection._path.isEmpty():
                continue
            if connection._path.length() < needed:
                continue
            try:
                middle = connection._path.pointAtPercent(0.5)
            except (RuntimeError, ValueError):
                continue
            distance = QLineF(center, middle).length()
            if distance <= limit and (best is None or distance < best[0]):
                best = (distance, connection)
        return best[1] if best is not None else None

    def preview_line_attach(self, node: NodeItem) -> None:
        candidate = self._line_attach_candidate(node)
        if candidate is None:
            self.clear_line_attach_preview()
            return
        if self._line_attach_preview is not candidate:
            self.clear_line_attach_preview()
            self._line_attach_preview = candidate
            candidate._attach_preview = True
            candidate.update()
        try:
            middle = candidate._path.pointAtPercent(0.5)
        except (RuntimeError, ValueError):
            return
        node.setPos(middle.x() - node._width / 2.0, middle.y() - node._height / 2.0)

    def commit_line_attach(self, node: NodeItem) -> bool:
        connection = self.line_attach_preview(node)
        if connection is None:
            self.clear_line_attach_preview()
            return False
        if connection.source is None or connection.target is None:
            self.clear_line_attach_preview()
            return False
        self.clear_line_attach_preview()
        try:
            middle = connection._path.pointAtPercent(0.5)
            start = connection.source.port_scene_pos(connection.source_port)
            end = connection.target.port_scene_pos(connection.target_port)
        except (RuntimeError, ValueError):
            return False
        node.setPos(middle.x() - node._width / 2.0, middle.y() - node._height / 2.0)
        source = connection.source
        source_port = connection.source_port
        target = connection.target
        target_port = connection.target_port
        weight = connection.line_weight
        dash = connection.dash_style
        route = connection.route
        color = QColor(connection.line_color)
        in_order = sorted(
            PORT_NAMES, key=lambda port: QLineF(node.port_scene_pos(port), start).length()
        )
        out_order = sorted(
            PORT_NAMES, key=lambda port: QLineF(node.port_scene_pos(port), end).length()
        )
        chosen: Optional[tuple[str, str]] = None
        for in_port in in_order:
            for out_port in out_order:
                if in_port == out_port:
                    continue
                if self.connection_exists(source, source_port, node, in_port):
                    continue
                if self.connection_exists(node, out_port, target, target_port):
                    continue
                chosen = (in_port, out_port)
                break
            if chosen is not None:
                break
        if chosen is None:
            return False
        in_port, out_port = chosen
        previous_loading = self._loading
        self._loading = True
        try:
            self._discard_connection(connection)
            self.add_connection(
                source,
                source_port,
                node,
                in_port,
                style="thin" if weight == "thin" else "thick",
                select=False,
                weight=weight,
                dash=dash,
                route=route,
                color=color,
            )
            self.add_connection(
                node,
                out_port,
                target,
                target_port,
                style="thin" if weight == "thin" else "thick",
                select=False,
                weight=weight,
                dash=dash,
                route=route,
                color=color,
            )
            self.clearSelection()
            node.setSelected(True)
        finally:
            self._loading = previous_loading
        self.refresh_connections()
        self.notify_changed()
        return True

    # ---- change tracking --------------------------------------------------

    def notify_changed(self) -> None:
        if self._loading:
            return
        self.content_changed.emit()

    def register_editor(self, node: NodeItem) -> None:
        previous = self._editing_node
        if previous is not None and previous is not node:
            previous.end_editing()
        self._editing_node = node
        self.editing_changed.emit(True)

    def unregister_editor(self, node: NodeItem) -> None:
        if self._editing_node is node:
            self._editing_node = None
            self.editing_changed.emit(False)

    def is_editing_text(self) -> bool:
        return self._editing_node is not None

    # ---- node management --------------------------------------------------

    def add_node(
        self,
        node: NodeItem,
        pos: Optional[QPointF] = None,
        select: bool = True,
        z: Optional[float] = None,
    ) -> NodeItem:
        if pos is not None:
            node.setPos(pos)
        if z is not None:
            node.setZValue(z)
            self._next_z = max(self._next_z, z + 1.0)
        else:
            node.setZValue(self._next_z)
            self._next_z += 1.0
        node.set_ui_scale(self.view_scale())
        self.addItem(node)
        self.nodes.append(node)
        node._ready = True
        if select and not self._loading:
            self.clearSelection()
            node.setSelected(True)
        if not self._loading:
            self.notify_changed()
        return node

    def _discard_connection(self, connection: ConnectionItem) -> None:
        if self._line_attach_preview is connection:
            self._line_attach_preview = None
        try:
            connection._long_press.stop()
            if connection._relinking:
                connection._cleanup_relink()
        except (RuntimeError, AttributeError):
            pass
        if connection in self.connections:
            self.connections.remove(connection)
        if connection.source is not None:
            connection.source._connections.discard(connection)
        if connection.target is not None:
            connection.target._connections.discard(connection)
        try:
            if connection.scene() is self:
                self.removeItem(connection)
        except RuntimeError:
            pass
        if not self._loading:
            self.refresh_connections()

    def remove_connection(self, connection: ConnectionItem) -> None:
        self._discard_connection(connection)
        self.notify_changed()

    def _discard_node(self, node: NodeItem) -> None:
        if node._editing:
            node.end_editing(from_focus=True)
        if self._line_attach_preview is not None and (
            self._line_attach_preview.source is node or self._line_attach_preview.target is node
        ):
            self._line_attach_preview = None
        self.clear_guides()
        for connection in list(node._connections):
            self._discard_connection(connection)
        if node in self.nodes:
            self.nodes.remove(node)
        try:
            if node.scene() is self:
                self.removeItem(node)
        except RuntimeError:
            pass

    def remove_node(self, node: NodeItem) -> None:
        self._discard_node(node)
        self.notify_changed()

    def add_connection(
        self,
        source: NodeItem,
        source_port: str,
        target: NodeItem,
        target_port: str,
        style: Optional[str] = None,
        select: bool = True,
        weight: Optional[str] = None,
        dash: Optional[str] = None,
        route: Optional[str] = None,
        color: Optional[QColor] = None,
    ) -> Optional[ConnectionItem]:
        if (
            source is None
            or target is None
            or source is target
            or not source.LINKABLE
            or not target.LINKABLE
            or source_port not in PORT_NAMES
            or target_port not in PORT_NAMES
            or self.connection_exists(source, source_port, target, target_port)
        ):
            return None
        if (
            style is None
            and weight is None
            and dash is None
            and route is None
            and color is None
            and self.inherit_enabled
        ):
            inherited = self._dominant_line_style(source, target)
            if inherited is not None:
                weight, dash, route, color = inherited
        if style is None:
            resolved_style = self.default_line_style
            resolved_weight = weight if weight is not None else self.default_line_weight
            resolved_dash = dash if dash is not None else self.default_line_dash
        else:
            resolved_style = style
            resolved_weight = weight
            resolved_dash = dash
        resolved_route = route if route is not None else self.default_line_route
        resolved_color = color if color is not None else self.default_line_color
        connection = ConnectionItem(
            source,
            source_port,
            target,
            target_port,
            resolved_style,
            weight=resolved_weight,
            dash=resolved_dash,
            route=resolved_route,
            color=resolved_color,
        )
        connection.set_ui_scale(self.view_scale())
        self.addItem(connection)
        self.connections.append(connection)
        connection.update_path()
        if not self._loading:
            self.refresh_connections(exclude=connection)
        if select and not self._loading:
            self.clearSelection()
            connection.setSelected(True)
        if not self._loading:
            self.notify_changed()
        return connection

    def connection_exists(
        self, source: NodeItem, source_port: str, target: NodeItem, target_port: str
    ) -> bool:
        for connection in self.connections:
            same = (
                connection.source is source
                and connection.target is target
                and connection.source_port == source_port
                and connection.target_port == target_port
            )
            reverse = (
                connection.source is target
                and connection.target is source
                and connection.source_port == target_port
                and connection.target_port == source_port
            )
            if same or reverse:
                return True
        return False

    def connection_exists_excluding(
        self,
        connection: ConnectionItem,
        source: NodeItem,
        source_port: str,
        target: NodeItem,
        target_port: str,
    ) -> bool:
        for other in self.connections:
            if other is connection:
                continue
            same = (
                other.source is source
                and other.target is target
                and other.source_port == source_port
                and other.target_port == target_port
            )
            reverse = (
                other.source is target
                and other.target is source
                and other.source_port == target_port
                and other.target_port == source_port
            )
            if same or reverse:
                return True
        return False

    def _dominant_line_style(
        self, source: NodeItem, target: NodeItem
    ) -> Optional[tuple[str, str, str, QColor]]:
        pool = [
            connection
            for connection in self.connections
            if connection.source in (source, target) or connection.target in (source, target)
        ]
        if not pool:
            return None

        def most_common(values: list) -> object:
            return Counter(values).most_common(1)[0][0]

        weight = most_common([connection.line_weight for connection in pool])
        dash = most_common([connection.dash_style for connection in pool])
        route = most_common([connection.route for connection in pool])
        color_value = most_common([color_name(connection.line_color) for connection in pool])
        return str(weight), str(dash), str(route), QColor(str(color_value))

    def _connection_from_data(
        self, item: dict, by_id: dict[str, NodeItem]
    ) -> Optional[ConnectionItem]:
        if not isinstance(item, dict):
            return None
        source = by_id.get(str(item.get("source", "")))
        target = by_id.get(str(item.get("target", "")))
        source_port = str(item.get("source_port", ""))
        target_port = str(item.get("target_port", ""))
        if (
            source is None
            or target is None
            or source is target
            or source_port not in PORT_NAMES
            or target_port not in PORT_NAMES
            or self.connection_exists(source, source_port, target, target_port)
        ):
            return None
        style = str(item.get("style", "thick"))
        weight = item.get("weight")
        dash = item.get("dash")
        route = item.get("route")
        connection = ConnectionItem(
            source,
            source_port,
            target,
            target_port,
            style,
            weight=weight if weight in LINE_WEIGHTS else None,
            dash=dash if dash in LINE_DASHES else None,
            route=route if route in LINE_ROUTES else None,
            color=item.get("color"),
        )
        connection.set_ui_scale(self.view_scale())
        self.addItem(connection)
        self.connections.append(connection)
        connection.update_path()
        return connection

    # ---- connection dragging ---------------------------------------------

    def begin_connection(self, node: NodeItem, port: str, scene_pos: QPointF) -> None:
        if not node.LINKABLE:
            return
        self.cancel_connection()
        self._connection_source = node
        self._connection_source_port = port
        temp_pen = QPen(QColor(ACCENT_LIGHT), 2.2)
        temp_pen.setCosmetic(True)
        temp_pen.setStyle(Qt.PenStyle.DashLine)
        temp_pen.setDashPattern([5.0, 4.0])
        temp_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self._temp_connection = QGraphicsPathItem()
        self._temp_connection.setPen(temp_pen)
        self._temp_connection.setZValue(10000.0)
        self.addItem(self._temp_connection)
        for item in self.nodes:
            item._ports_forced = True
            item.update()
        self.update_connection_drag(scene_pos)
        self._set_view_cursor(Qt.CursorShape.CrossCursor)

    def _connection_curve(self, start: QPointF, direction: QPointF, end: QPointF, end_direction: Optional[QPointF]) -> QPainterPath:
        distance = QLineF(start, end).length()
        strength = clamp(distance * 0.44, 14.0, 240.0)
        c1 = QPointF(start.x() + direction.x() * strength, start.y() + direction.y() * strength)
        if end_direction is None:
            c2 = QPointF(end.x(), end.y())
        else:
            c2 = QPointF(end.x() + end_direction.x() * strength, end.y() + end_direction.y() * strength)
        path = QPainterPath(start)
        path.cubicTo(c1, c2, end)
        return path

    def update_connection_drag(self, scene_pos: QPointF) -> None:
        if self._connection_source is None or self._connection_source_port is None:
            return
        target = self.find_snap_target(scene_pos)
        if target is not None:
            target_node, target_port = target
            end = target_node.port_scene_pos(target_port)
            end_direction = target_node.port_direction(target_port)
        else:
            target_node, target_port = None, None
            end = scene_pos
            end_direction = None

        start = self._connection_source.port_scene_pos(self._connection_source_port)
        direction = self._connection_source.port_direction(self._connection_source_port)
        if self._temp_connection is not None:
            self._temp_connection.setPath(self._connection_curve(start, direction, end, end_direction))

        if target_node is not self._target_node or target_port != self._target_port:
            if self._target_node is not None:
                self._target_node._target_port = None
                self._target_node.update()
            self._target_node = target_node
            self._target_port = target_port
            if target_node is not None:
                target_node._target_port = target_port
                target_node.update()

    def finish_connection(self, scene_pos: QPointF) -> None:
        if self._connection_source is None or self._connection_source_port is None:
            self.cancel_connection()
            return
        target = self.find_snap_target(scene_pos)
        source = self._connection_source
        source_port = self._connection_source_port
        self._cleanup_connection_drag()
        if target is not None:
            target_node, target_port = target
            self.add_connection(
                source,
                source_port,
                target_node,
                target_port,
                select=True,
            )

    def cancel_connection(self) -> None:
        self._cleanup_connection_drag()

    def _cleanup_connection_drag(self) -> None:
        if self._temp_connection is not None:
            try:
                if self._temp_connection.scene() is self:
                    self.removeItem(self._temp_connection)
            except RuntimeError:
                pass
            self._temp_connection = None
        if self._target_node is not None:
            self._target_node._target_port = None
            self._target_node.update()
        for item in self.nodes:
            item._ports_forced = False
            item.update()
        self._connection_source = None
        self._connection_source_port = None
        self._target_node = None
        self._target_port = None
        self._set_view_cursor(Qt.CursorShape.ArrowCursor)

    def _set_view_cursor(self, cursor) -> None:
        for view in self.views():
            view.viewport().setCursor(cursor)

    def find_node_at(self, scene_pos: QPointF) -> Optional[NodeItem]:
        for node in sorted(self.nodes, key=lambda item: item.zValue(), reverse=True):
            try:
                local = node.mapFromScene(scene_pos)
                if node.body_rect().adjusted(-5, -5, 5, 5).contains(local):
                    return node
            except RuntimeError:
                continue
        return None

    def find_snap_target(self, scene_pos: QPointF) -> Optional[tuple[NodeItem, str]]:
        if self._connection_source is None:
            return None
        return self.find_port_target(scene_pos, exclude=self._connection_source)

    def find_port_target(
        self, scene_pos: QPointF, exclude: Optional[NodeItem] = None
    ) -> Optional[tuple[NodeItem, str]]:
        scale = self.view_scale()
        node_under = self.find_node_at(scene_pos)
        if node_under is not None and node_under is not exclude and node_under.LINKABLE:
            best: Optional[tuple[float, NodeItem, str]] = None
            for port in PORT_NAMES:
                pos = node_under.port_scene_pos(port)
                distance = QLineF(pos, scene_pos).length()
                if best is None or distance < best[0]:
                    best = (distance, node_under, port)
            if best is not None:
                return best[1], best[2]

        snap_radius = 30.0 / max(0.08, scale)
        best = None
        for node in self.nodes:
            if node is exclude or not node.LINKABLE:
                continue
            for port in PORT_NAMES:
                pos = node.port_scene_pos(port)
                distance = QLineF(pos, scene_pos).length()
                if best is None or distance < best[0]:
                    best = (distance, node, port)
        if best is not None and best[0] <= snap_radius:
            return best[1], best[2]
        return None

    # ---- selection / deletion --------------------------------------------

    def selected_nodes(self) -> list[NodeItem]:
        return [item for item in self.selectedItems() if isinstance(item, NodeItem)]

    def selected_connections(self) -> list[ConnectionItem]:
        return [item for item in self.selectedItems() if isinstance(item, ConnectionItem)]

    def delete_selected(self) -> int:
        nodes = list(self.selected_nodes())
        connection_set: set[ConnectionItem] = set(self.selected_connections())
        for node in nodes:
            connection_set.update(node._connections)
        if not nodes and not connection_set:
            return 0
        previous_loading = self._loading
        self._loading = True
        try:
            for connection in list(connection_set):
                self._discard_connection(connection)
            for node in nodes:
                self._discard_node(node)
            self.clearSelection()
        finally:
            self._loading = previous_loading
        self.notify_changed()
        return len(nodes) + len(connection_set)

    def copy_selection(self) -> Optional[dict]:
        nodes = sorted(self.selected_nodes(), key=lambda item: item.zValue())
        if not nodes:
            return None
        node_ids = {node.node_id for node in nodes}
        connections = [
            connection
            for connection in self.connections
            if connection.source is not None
            and connection.target is not None
            and connection.source.node_id in node_ids
            and connection.target.node_id in node_ids
        ]
        return {
            "wave_board_clipboard": 1,
            "version": 1,
            "nodes": [copy.deepcopy(node.to_dict()) for node in nodes],
            "connections": [copy.deepcopy(connection.to_dict()) for connection in connections],
        }

    def paste_payload(
        self,
        payload: dict,
        scene_pos: Optional[QPointF] = None,
        offset: Optional[QPointF] = None,
    ) -> list[NodeItem]:
        if not isinstance(payload, dict):
            return []
        entries = [item for item in payload.get("nodes", []) if isinstance(item, dict)]
        if not entries:
            return []

        if offset is not None:
            delta = QPointF(offset)
        elif scene_pos is not None:
            min_x = min(safe_float(item.get("x"), 0.0) for item in entries)
            min_y = min(safe_float(item.get("y"), 0.0) for item in entries)
            max_x = max(
                safe_float(item.get("x"), 0.0) + safe_float(item.get("w"), 200.0)
                for item in entries
            )
            max_y = max(
                safe_float(item.get("y"), 0.0) + safe_float(item.get("h"), 100.0)
                for item in entries
            )
            center = QPointF((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
            delta = QPointF(scene_pos.x() - center.x(), scene_pos.y() - center.y())
        else:
            delta = QPointF(28.0, 28.0)

        previous_loading = self._loading
        self._loading = True
        new_nodes: list[NodeItem] = []
        id_map: dict[str, NodeItem] = {}
        try:
            for item in entries:
                node = node_from_dict(copy.deepcopy(item))
                if node is None:
                    continue
                old_id = str(item.get("id", ""))
                node.node_id = uuid.uuid4().hex
                x = safe_float(item.get("x"), 0.0) + delta.x()
                y = safe_float(item.get("y"), 0.0) + delta.y()
                self.add_node(node, pos=QPointF(x, y), select=False)
                if old_id:
                    id_map[old_id] = node
                new_nodes.append(node)

            for item in payload.get("connections", []):
                self._connection_from_data(item, id_map)
            self.refresh_connections()

            self.clearSelection()
            for node in new_nodes:
                node.setSelected(True)
        finally:
            self._loading = previous_loading
        if new_nodes:
            self.notify_changed()
        return new_nodes

    def clear_board(self) -> None:
        self.cancel_connection()
        self.clear_line_attach_preview()
        self.clear_guides()
        if self._editing_node is not None:
            try:
                self._editing_node.end_editing(from_focus=True)
            except RuntimeError:
                pass
            self._editing_node = None
        previous_loading = self._loading
        self._loading = True
        try:
            self.clearSelection()
            for connection in list(self.connections):
                self._discard_connection(connection)
            for node in list(self.nodes):
                self._discard_node(node)
            self.nodes.clear()
            self.connections.clear()
            self._next_z = 20.0
        finally:
            self._loading = previous_loading

    def content_bounds(self) -> QRectF:
        bounds = QRectF()
        for node in self.nodes:
            try:
                rect = node.mapToScene(node.body_rect()).boundingRect()
            except RuntimeError:
                continue
            bounds = rect if bounds.isNull() else bounds.united(rect)
        for connection in self.connections:
            try:
                rect = connection._path.boundingRect()
            except RuntimeError:
                continue
            bounds = rect if bounds.isNull() else bounds.united(rect)
        return bounds

    # ---- serialization ----------------------------------------------------

    def to_dict(self, view: Optional[QGraphicsView] = None) -> dict:
        if view is None and self.views():
            view = self.views()[0]
        if view is not None:
            center = view.mapToScene(view.viewport().rect().center())
            zoom = view.transform().m11()
        else:
            center = QPointF(0, 0)
            zoom = 1.0
        return {
            "app": APP_NAME,
            "version": 1,
            "grid": bool(self.grid_enabled),
            "grid_style": "dots",
            "magnet": bool(self.magnet_enabled),
            "inherit": bool(self.inherit_enabled),
            "bundle": bool(self.bundle_enabled),
            "view": {
                "x": round(float(center.x()), 3),
                "y": round(float(center.y()), 3),
                "zoom": round(float(zoom), 5),
            },
            "nodes": [node.to_dict() for node in sorted(self.nodes, key=lambda item: item.zValue())],
            "connections": [connection.to_dict() for connection in self.connections],
        }

    def load_from_dict(self, data: dict) -> tuple[int, int]:
        if not isinstance(data, dict):
            raise ValueError("The board file does not contain a JSON object.")
        nodes_data = data.get("nodes", [])
        connections_data = data.get("connections", [])
        if not isinstance(nodes_data, list):
            raise ValueError("The board's 'nodes' value must be a list.")
        if not isinstance(connections_data, list):
            raise ValueError("The board's 'connections' value must be a list.")

        self._loading = True
        try:
            self.clear_board()
            by_id: dict[str, NodeItem] = {}
            for index, item in enumerate(nodes_data):
                if not isinstance(item, dict):
                    continue
                node = node_from_dict(item)
                if node is None:
                    continue
                if node.node_id in by_id:
                    node.node_id = uuid.uuid4().hex
                z = safe_float(item.get("z"), 20.0 + index)
                self.add_node(node, select=False, z=z)
                by_id[node.node_id] = node

            for item in connections_data:
                self._connection_from_data(item, by_id)
            self.clearSelection()
            if self.nodes:
                self._next_z = max(node.zValue() for node in self.nodes) + 1.0
            else:
                self._next_z = 20.0
            self.refresh_connections()
            self.update()
        finally:
            self._loading = False
        return len(self.nodes), len(self.connections)


# ---------------------------------------------------------------------------
# Canvas view
# ---------------------------------------------------------------------------


class CanvasView(QGraphicsView):
    zoom_changed = pyqtSignal(float)
    files_dropped = pyqtSignal(list, QPointF)
    background_double_clicked = pyqtSignal(QPointF)
    copy_requested = pyqtSignal()
    cut_requested = pyqtSignal()
    paste_requested = pyqtSignal()
    duplicate_requested = pyqtSignal()
    select_all_requested = pyqtSignal()
    nudge_requested = pyqtSignal(float, float)
    edit_selected_requested = pyqtSignal()
    resized = pyqtSignal()

    MIN_ZOOM = 0.12
    MAX_ZOOM = 4.5

    def __init__(self, scene: BoardScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.setMinimumSize(640, 380)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self._panning = False
        self._pan_start = QPointF()
        self._pan_center_scene = QPointF()
        self._space_pressed = False
        self._dragging_file = False

        self.empty_label = QLabel(self.viewport())
        self.empty_label.setTextFormat(Qt.TextFormat.RichText)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.empty_label.setStyleSheet("background: transparent;")
        self.empty_label.hide()
        self.empty_label.setGeometry(self.viewport().rect())
        self.update_empty_style()

        scene.content_changed.connect(self.update_empty_state)
        QTimer.singleShot(0, self.update_empty_state)

    # ---- empty state ------------------------------------------------------

    def update_empty_style(self) -> None:
        title = CURRENT_THEME_MAP.get("#63738B", TEXT_MUTED)
        hint = CURRENT_THEME_MAP.get("#445166", TEXT_FAINT)
        self.empty_label.setText(
            f"<div style='color:{title}; font-size:20px; font-weight:600;'>Start with an idea</div>"
            f"<div style='color:{hint}; font-size:13px;'>Double-click anywhere, or use the toolbar "
            "to add a note, image, or shape. Press F1 for shortcuts.</div>"
        )
        self.viewport().update()

    def update_empty_state(self) -> None:
        scene = self.scene()
        has_content = bool(scene.nodes) if isinstance(scene, BoardScene) else bool(scene.items())
        self.empty_label.setVisible(not has_content)
        if not has_content:
            self.empty_label.raise_()
            self.empty_label.setGeometry(self.viewport().rect())

    # ---- zoom -------------------------------------------------------------

    def zoom_by(self, factor: float, anchor: Optional[QPointF] = None) -> None:
        old_scale = self.transform().m11()
        new_scale = clamp(old_scale * factor, self.MIN_ZOOM, self.MAX_ZOOM)
        if abs(new_scale - old_scale) < 1e-7:
            return
        if anchor is None:
            anchor = QPointF(self.viewport().rect().center())
        scene_anchor = self.mapToScene(anchor.toPoint())
        self.scale(new_scale / old_scale, new_scale / old_scale)
        # Keep the scene point that was under the cursor pinned to the cursor.
        mapped = self.viewportTransform().map(scene_anchor)
        delta = QPointF(mapped.x() - anchor.x(), mapped.y() - anchor.y())
        if abs(delta.x()) > 0.001 or abs(delta.y()) > 0.001:
            center = self.mapToScene(self.viewport().rect().center())
            self.centerOn(QPointF(center.x() + delta.x() / new_scale, center.y() + delta.y() / new_scale))
        scene = self.scene()
        if isinstance(scene, BoardScene):
            scene.refresh_ui_scale(new_scale)
        self.viewport().update()
        self.zoom_changed.emit(new_scale)

    def set_zoom(self, scale: float, anchor: Optional[QPointF] = None) -> None:
        scale = clamp(float(scale), self.MIN_ZOOM, self.MAX_ZOOM)
        current = self.transform().m11()
        if abs(scale - current) < 1e-7:
            return
        self.zoom_by(scale / current, anchor)

    def reset_view(self) -> None:
        self.setTransform(QTransform())
        self.centerOn(QPointF(0, 0))
        scene = self.scene()
        if isinstance(scene, BoardScene):
            scene.refresh_ui_scale(1.0)
        self.viewport().update()
        self.zoom_changed.emit(1.0)

    def fit_content(self) -> None:
        scene = self.scene()
        if not isinstance(scene, BoardScene) or not scene.nodes:
            self.reset_view()
            return
        bounds = scene.content_bounds()
        if bounds.isNull() or bounds.width() <= 0 or bounds.height() <= 0:
            self.reset_view()
            return
        margin = 90.0
        bounds = bounds.adjusted(-margin, -margin, margin, margin)
        viewport_rect = self.viewport().rect()
        available_w = max(100, viewport_rect.width() - 60)
        available_h = max(100, viewport_rect.height() - 60)
        scale = min(available_w / bounds.width(), available_h / bounds.height())
        scale = clamp(scale, self.MIN_ZOOM, 1.65)
        transform = QTransform()
        transform.scale(scale, scale)
        self.setTransform(transform)
        self.centerOn(bounds.center())
        scene.refresh_ui_scale(scale)
        self.viewport().update()
        self.zoom_changed.emit(scale)

    def view_state(self) -> dict:
        center = self.mapToScene(self.viewport().rect().center())
        return {"x": center.x(), "y": center.y(), "zoom": self.transform().m11()}

    def restore_view_state(self, state: dict) -> None:
        center = QPointF(safe_float(state.get("x"), 0.0), safe_float(state.get("y"), 0.0))
        zoom = clamp(safe_float(state.get("zoom"), 1.0), self.MIN_ZOOM, self.MAX_ZOOM)
        transform = QTransform()
        transform.scale(zoom, zoom)
        self.setTransform(transform)
        self.centerOn(center)
        scene = self.scene()
        if isinstance(scene, BoardScene):
            scene.refresh_ui_scale(zoom)
        self.viewport().update()
        self.zoom_changed.emit(zoom)

    def wheelEvent(self, event) -> None:
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, ConnectionItem):
            item.cycle_dash_style(1 if event.angleDelta().y() < 0 else -1)
            event.accept()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y() * 8
        if delta == 0:
            event.ignore()
            return
        factor = math.exp(delta * 0.0015)
        self.zoom_by(factor, event.position())
        event.accept()

    # ---- panning ----------------------------------------------------------

    def _start_pan(self, view_pos: QPointF) -> None:
        self._panning = True
        self._pan_start = QPointF(view_pos)
        self._pan_center_scene = self.mapToScene(self.viewport().rect().center())
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def _finish_pan(self) -> None:
        self._panning = False
        if self._space_pressed:
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def _is_text_editing(self) -> bool:
        scene = self.scene()
        return isinstance(scene, BoardScene) and scene.is_editing_text()

    def mousePressEvent(self, event) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, ConnectionItem) and event.button() == Qt.MouseButton.MiddleButton:
            item.cycle_weight()
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_pressed
        ):
            self._start_pan(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            delta = event.position() - self._pan_start
            scale = max(0.02, self.transform().m11())
            target_center = QPointF(
                self._pan_center_scene.x() - delta.x() / scale,
                self._pan_center_scene.y() - delta.y() / scale,
            )
            self.centerOn(target_center)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._finish_pan()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            position = event.position().toPoint()
            item = self.itemAt(position)
            if item is None:
                self.background_double_clicked.emit(self.mapToScene(position))
                event.accept()
                return
            if isinstance(item, NodeTextItem):
                node = item.node
                local = node.mapFromScene(self.mapToScene(position))
                if (
                    node.SUPPORTS_TEXT
                    and not node._editing
                    and node.body_rect().contains(local)
                    and node.port_at(local) is None
                    and node.handle_at(local) is None
                ):
                    node.begin_editing(scene_pos=self.mapToScene(position))
                    event.accept()
                    return
            elif isinstance(item, NodeItem) and item.SUPPORTS_TEXT:
                local = item.mapFromScene(self.mapToScene(position))
                if (
                    item.SUPPORTS_TEXT
                    and not item._editing
                    and item.body_rect().contains(local)
                    and item.port_at(local) is None
                ):
                    item.begin_editing(scene_pos=self.mapToScene(position))
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

    # ---- keyboard ---------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        key = event.key()
        modifiers = event.modifiers()
        editing = self._is_text_editing()
        if key == Qt.Key.Key_Space:
            if not event.isAutoRepeat() and not editing:
                self._space_pressed = True
                self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
                event.accept()
                return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            scene = self.scene()
            if isinstance(scene, BoardScene) and not editing:
                scene.delete_selected()
                event.accept()
                return
        if key == Qt.Key.Key_Escape:
            if not editing:
                scene = self.scene()
                if isinstance(scene, BoardScene):
                    if scene._connection_source is not None:
                        scene.cancel_connection()
                    else:
                        scene.clearSelection()
                event.accept()
                return
        if not editing and modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_C:
                self.copy_requested.emit()
                event.accept()
                return
            if key == Qt.Key.Key_X:
                self.cut_requested.emit()
                event.accept()
                return
            if key == Qt.Key.Key_V:
                self.paste_requested.emit()
                event.accept()
                return
            if key in (Qt.Key.Key_D, Qt.Key.Key_J):
                self.duplicate_requested.emit()
                event.accept()
                return
            if key == Qt.Key.Key_A:
                self.select_all_requested.emit()
                event.accept()
                return
            if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.zoom_by(1.22)
                event.accept()
                return
            if key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
                self.zoom_by(1.0 / 1.22)
                event.accept()
                return
        if not editing and key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            scene = self.scene()
            if isinstance(scene, BoardScene) and scene.selected_nodes():
                scale = max(0.08, self.transform().m11())
                step = (10.0 if modifiers & Qt.KeyboardModifier.ShiftModifier else 1.0) / scale
                dx = -step if key == Qt.Key.Key_Left else step if key == Qt.Key.Key_Right else 0.0
                dy = -step if key == Qt.Key.Key_Up else step if key == Qt.Key.Key_Down else 0.0
                self.nudge_requested.emit(dx, dy)
                event.accept()
                return
        if not editing and key in (Qt.Key.Key_F2, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.edit_selected_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            if not self._is_text_editing():
                self._space_pressed = False
                if not self._panning:
                    self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        scene = self.scene()
        if isinstance(scene, BoardScene) and scene._connection_source is not None:
            scene.cancel_connection()
        if not self._panning and not self._is_text_editing():
            self._space_pressed = False
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        super().focusOutEvent(event)

    # ---- drag and drop ----------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            super().dropEvent(event)
            return
        paths = []
        for url in event.mimeData().urls():
            local = url.toLocalFile()
            if local and os.path.isfile(local):
                paths.append(local)
        if paths:
            position = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self.files_dropped.emit(paths, self.mapToScene(position))
            event.acceptProposedAction()
        else:
            event.ignore()

    # ---- geometry ---------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        label = getattr(self, "empty_label", None)
        if label is not None:
            label.setGeometry(self.viewport().rect())
            if label.isVisible():
                label.raise_()
        self.resized.emit()


# ---------------------------------------------------------------------------
# UI primitives and theme
# ---------------------------------------------------------------------------


class ColorSwatchButton(QToolButton):
    colorPicked = pyqtSignal(QColor)

    def __init__(self, kind: str, color: QColor, title: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.color = QColor(color)
        self.dialog_title = title
        self.setProperty("role", "swatch")
        self.setFixedSize(32, 32)
        self.setIconSize(QSize(20, 20))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.set_color(self.color, emit=False)
        self.clicked.connect(self._choose)

    def set_color(self, color: QColor, emit: bool = False) -> None:
        if not color.isValid():
            return
        self.color = QColor(color)
        self.setIcon(swatch_icon(self.kind, self.color))
        if emit:
            self.colorPicked.emit(QColor(self.color))

    def _choose(self) -> None:
        options = (
            QColorDialog.ColorDialogOption.ShowAlphaChannel
            | QColorDialog.ColorDialogOption.DontUseNativeDialog
        )
        chosen = QColorDialog.getColor(self.color, self.window(), self.dialog_title, options)
        if chosen.isValid():
            self.set_color(chosen, emit=True)


class ThemeColorButton(QToolButton):
    """Swatch + hex row that previews the whole app while the picker is open."""

    colorPicked = pyqtSignal(QColor)
    colorCommitted = pyqtSignal(QColor)

    def __init__(self, color: QColor, title: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.dialog_title = title
        self.color = QColor(color)
        self._before = QColor(color)
        self.setProperty("role", "themeSwatch")
        self.setFixedHeight(34)
        self.setIconSize(QSize(18, 18))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.set_color(self.color, emit=False)
        self.clicked.connect(self._choose)

    def set_color(self, color: QColor, emit: bool = False) -> None:
        if not color.isValid():
            return
        self.color = QColor(color)
        self.setIcon(swatch_icon("fill", self.color))
        self.setText(self.color.name().upper())
        if emit:
            self.colorPicked.emit(QColor(self.color))

    def _preview(self, color: QColor) -> None:
        if color.isValid():
            self.set_color(color, emit=True)

    def _restore(self) -> None:
        self.set_color(self._before, emit=True)

    def _commit(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.color = QColor(color)
        self.colorCommitted.emit(QColor(self.color))

    def _choose(self) -> None:
        self._before = QColor(self.color)
        dialog = QColorDialog(self.color, self.window())
        dialog.setWindowTitle(self.dialog_title)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, False)
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        dialog.currentColorChanged.connect(self._preview)
        dialog.colorSelected.connect(self._commit)
        dialog.rejected.connect(self._restore)
        dialog.exec()


def make_tool_button(
    text: str,
    icon_name: str,
    tooltip: str,
    slot=None,
    checkable: bool = False,
    role: str = "tool",
) -> QToolButton:
    button = QToolButton()
    button.setText(text)
    button.setProperty("iconName", icon_name)
    button.setIcon(ui_icon(icon_name, ICON_COLOR))
    button.setIconSize(QSize(18, 18))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    button.setProperty("role", role)
    button.setCheckable(checkable)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(tooltip)
    button.setFixedHeight(34)
    button.setSizePolicy(button.sizePolicy().horizontalPolicy(), button.sizePolicy().verticalPolicy())
    if slot is not None:
        button.clicked.connect(slot)
    return button


def make_zoom_button(icon_name: str, tooltip: str, slot) -> QToolButton:
    button = QToolButton()
    button.setProperty("iconName", icon_name)
    button.setProperty("iconTone", "zoom")
    button.setIcon(ui_icon(icon_name, CURRENT_THEME_MAP.get("#A8B7CB", "#A8B7CB")))
    button.setIconSize(QSize(14, 14))
    button.setProperty("role", "zoom")
    button.setFixedSize(24, 24)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip(tooltip)
    button.clicked.connect(slot)
    return button


def make_divider() -> QFrame:
    divider = QFrame()
    divider.setObjectName("Divider")
    divider.setFrameShape(QFrame.Shape.NoFrame)
    divider.setFixedSize(1, 22)
    return divider


def theme_palette(preset: str = "blue", accent: Optional[str] = None, canvas: Optional[str] = None) -> QPalette:
    mapping = theme_color_map(preset, accent, canvas)
    def col(hex_value: str) -> QColor:
        return QColor(mapping.get(hex_value.upper(), hex_value))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, col("#090D14"))
    palette.setColor(QPalette.ColorRole.WindowText, col("#DCE7F6"))
    palette.setColor(QPalette.ColorRole.Base, col("#0A0F16"))
    palette.setColor(QPalette.ColorRole.AlternateBase, col("#111A26"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, col("#131C28"))
    palette.setColor(QPalette.ColorRole.ToolTipText, col("#E8F0FB"))
    palette.setColor(QPalette.ColorRole.Text, col("#DCE7F6"))
    palette.setColor(QPalette.ColorRole.Button, col("#141D2A"))
    palette.setColor(QPalette.ColorRole.ButtonText, col("#DCE7F6"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Highlight, col("#2D7DFF"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, col("#6FA8FF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, col("#5C6A7F"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, col("#4B596D"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, col("#4B596D"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, col("#4B596D"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, col("#080D14"))
    return palette


def dark_palette() -> QPalette:
    return theme_palette("blue")


def apply_dark_title_bar(window: QMainWindow, preset: str = "blue") -> None:
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
        dark = preset != "light"
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
        mapping = CURRENT_THEME_MAP
        def colorref(hex_value: str) -> int:
            color = QColor(mapping.get(hex_value.upper(), hex_value))
            return color.red() | (color.green() << 8) | (color.blue() << 16)
        caption = ctypes.c_int(colorref("#0E1622" if dark else "#F3F5F8"))
        text = ctypes.c_int(colorref("#EAF1FF" if dark else "#1B232E"))
        border = ctypes.c_int(colorref("#1B2432" if dark else "#D7DEE8"))
        for attribute, color in ((35, caption), (36, text), (34, border)):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(color), ctypes.sizeof(color)
            )
    except Exception:
        pass


APP_QSS = """
QWidget {
    color: #D6E2F2;
    font-family: "Segoe UI";
    font-size: 12px;
}
QMainWindow, QDialog, QMessageBox {
    background: #090D14;
}
QWidget#Header {
    background: #0C1119;
    border-bottom: 1px solid #1A2230;
}
QWidget#HeaderTop, QWidget#ToolRow {
    background: transparent;
}
QLabel#LogoBox {
    background: #03060B;
    border: 1px solid #202B3B;
    border-radius: 11px;
}
QLabel#BrandTitle {
    color: #F3F7FE;
    font-size: 18px;
    font-weight: 650;
    letter-spacing: 0.2px;
}
QLabel#BrandSub {
    color: #5C6A7F;
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 1.7px;
}
QLabel#DocName {
    color: #95A5BB;
    font-size: 12px;
}
QLabel#DirtyDot {
    color: #FFCA3F;
    font-size: 13px;
}
QLabel#SectionLabel {
    color: #66768D;
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 0.8px;
}
QLabel#ValuePill {
    color: #A9B8CC;
    background: #0A0F16;
    border: 1px solid #202B39;
    border-radius: 6px;
    font-size: 10px;
    padding: 2px 3px;
}
QLabel#ZoomLabel {
    color: #A5B4C9;
    font-size: 11px;
    font-weight: 600;
}
QLabel#StatusHint {
    color: #68788E;
    font-size: 11px;
}
QLabel#StatusCount {
    color: #8A9BB0;
    font-size: 11px;
}
QLabel#StatusSeparator {
    color: #2A3647;
    font-size: 12px;
}
QFrame#Divider {
    background: #1C2634;
    border: none;
}
QFrame#StatusDivider {
    background: #263243;
    border: none;
}
QFrame#Segmented {
    background: #080D14;
    border: 1px solid #202B3A;
    border-radius: 8px;
}
QFrame#LinePanel {
    background: #0E1622;
    border: 1px solid #2A3B53;
    border-radius: 12px;
}
QLabel#LinePanelTitle {
    color: #EAF2FF;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}
QLabel#LinePanelGroup {
    color: #60728B;
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.8px;
}
QFrame#PanelDivider {
    background: #223047;
    border: none;
}
QFrame#LinePanel QToolButton[role="segment"] {
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 2px 7px;
    color: #8295AC;
    font-size: 10px;
}
QFrame#LinePanel QToolButton[role="segment"]:hover {
    background: #172335;
    color: #EAF2FF;
}
QFrame#LinePanel QToolButton[role="segment"]:checked {
    background: #1C3B66;
    color: #F0F6FF;
}
QToolButton {
    outline: none;
}
QToolButton[role="tool"], QToolButton[role="ghost"], QToolButton[role="danger"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 9px;
    color: #C8D5E7;
}
QToolButton[role="primary"] {
    background: #2D7DFF;
    border: 1px solid #4B8DFF;
    border-radius: 8px;
    padding: 5px 12px;
    color: #FFFFFF;
}
QToolButton[role="primary"]:hover {
    background: #3D8BFF;
    border-color: #6FA8FF;
}
QToolButton[role="primary"]:pressed {
    background: #2368DA;
}
QToolButton[role="primary"]:disabled {
    background: #172A46;
    border-color: #243B5B;
    color: #61748F;
}
QToolButton[role="tool"]:hover, QToolButton[role="ghost"]:hover {
    background: #151E2B;
    border-color: #243248;
    color: #F0F6FF;
}
QToolButton[role="tool"]:pressed, QToolButton[role="ghost"]:pressed {
    background: #1B2636;
}
QToolButton[role="tool"]:checked {
    background: rgba(45, 125, 255, 0.16);
    border-color: rgba(45, 125, 255, 0.55);
    color: #F0F6FF;
}
QToolButton[role="ghost"] {
    border-color: #1D2735;
    background: #0F151F;
}
QToolButton[role="danger"]:hover {
    background: rgba(235, 82, 82, 0.13);
    border-color: rgba(235, 82, 82, 0.28);
    color: #FF9A9A;
}
QToolButton[role="segment"] {
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 3px 9px;
    color: #7D8DA4;
    font-size: 11px;
}
QToolButton[role="segment"]:hover {
    color: #DCE8F8;
}
QToolButton[role="segment"]:checked {
    background: #1A2940;
    color: #F0F6FF;
}
QToolButton[role="swatch"] {
    background: #0B1119;
    border: 1px solid #202B3A;
    border-radius: 8px;
    padding: 3px;
}
QToolButton[role="swatch"]:hover {
    border-color: #3B4D67;
    background: #111A26;
}
QToolButton[role="swatch"]:disabled {
    background: #0A0F16;
    border-color: #171F2B;
}
QToolButton[role="zoom"] {
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 2px;
}
QToolButton[role="zoom"]:hover {
    background: #182231;
}
QToolButton:disabled {
    color: #4B596D;
}
QToolButton::menu-button {
    border: none;
    width: 15px;
}
QSlider {
    min-height: 18px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #1E2837;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #2D7DFF;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #F0F5FF;
    border: 2px solid #2D7DFF;
    width: 11px;
    height: 11px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #FFFFFF;
}
QSlider:disabled::sub-page:horizontal {
    background: #2A3546;
}
QSlider:disabled::handle:horizontal {
    background: #5A6678;
    border-color: #354155;
}
QSpinBox {
    background: #0A0F16;
    border: 1px solid #202B3A;
    border-radius: 7px;
    padding: 4px 5px;
    color: #C9D6E8;
    selection-background-color: #2D7DFF;
}
QSpinBox:focus {
    border-color: #2D7DFF;
    color: #F0F6FF;
}
QSpinBox:disabled {
    color: #4B596D;
    background: #0A0E14;
}
QComboBox {
    background: #0A0F16;
    border: 1px solid #202B3A;
    border-radius: 7px;
    padding: 3px 8px;
    color: #C9D6E8;
}
QComboBox:focus {
    border-color: #2D7DFF;
    color: #F0F6FF;
}
QComboBox:disabled {
    color: #4B596D;
    background: #0A0E14;
}
QComboBox QAbstractItemView {
    background: #101823;
    border: 1px solid #26344A;
    color: #DCE8F8;
    selection-background-color: #2D7DFF;
    selection-color: #FFFFFF;
    outline: none;
}
QStatusBar {
    background: #0B1017;
    border-top: 1px solid #161F2B;
}
QStatusBar::item {
    border: none;
}
QToolTip {
    background: #131C28;
    color: #DCE8F8;
    border: 1px solid #2A3850;
    padding: 4px 6px;
    border-radius: 4px;
}
QMenu {
    background: #101823;
    border: 1px solid #26344A;
    border-radius: 8px;
    padding: 5px;
}
QMenu::item {
    background: transparent;
    color: #CBD8E9;
    padding: 6px 26px 6px 8px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: #1A2A40;
    color: #F0F6FF;
}
QMenu::separator {
    height: 1px;
    background: #202B3B;
    margin: 4px 6px;
}
QMessageBox QLabel {
    color: #DCE7F6;
}
QMessageBox QPushButton, QColorDialog QPushButton {
    background: #141D2A;
    border: 1px solid #26344A;
    border-radius: 6px;
    padding: 5px 14px;
    min-width: 68px;
}
QMessageBox QPushButton:hover, QColorDialog QPushButton:hover {
    background: #1B283A;
    border-color: #345176;
}
QPushButton:default {
    background: #2D7DFF;
    border-color: #2D7DFF;
    color: #FFFFFF;
}
QLineEdit {
    background: #0A0F16;
    border: 1px solid #202B3A;
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: #2D7DFF;
}
QColorDialog {
    background: #0F151F;
}
QFrame#ThemePanel {
    background: #0E1622;
    border: 1px solid #2A3B53;
    border-radius: 14px;
}
QLabel#ThemeHeading {
    color: #EAF2FF;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.3px;
}
QLabel#ThemeCaption {
    color: #60728B;
    font-size: 8px;
    font-weight: 600;
    letter-spacing: 0.9px;
}
QLabel#ThemeHex {
    color: #95A5BB;
    font-size: 10px;
    font-weight: 600;
}
QToolButton[role="themeCard"] {
    background: #0A0F16;
    border: 1px solid #202B3A;
    border-radius: 10px;
    padding: 6px 4px 5px 4px;
    color: #C8D5E7;
    font-size: 10px;
    font-weight: 600;
}
QToolButton[role="themeCard"]:hover {
    border-color: #3B4D67;
    background: #111A26;
    color: #F0F6FF;
}
QToolButton[role="themeCard"]:checked {
    border-color: #2D7DFF;
    background: #1A2940;
    color: #F0F6FF;
}
QToolButton[role="themeSwatch"] {
    background: #0A0F16;
    border: 1px solid #202B3A;
    border-radius: 8px;
    padding: 2px;
}
QToolButton[role="themeSwatch"]:hover {
    border-color: #3B4D67;
    background: #111A26;
}
"""


# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------

QSS_HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}")
THEME_EXTRA_COLORS = (
    "#1E4E9E",
    "#121B28",
    "#121A28",
    "#172943",
    "#EDF4FF",
    "#F2F7FF",
    "#B9C7D8",
    "#111A26",
    "#2A3A50",
    "#8FB8FF",
    "#070B11",
    "#F8FCFF",
    "#9FB3CF",
    "#BFD5F4",
    "#A8B7CB",
    "#BFD0E6",
    "#63738B",
    "#445166",
)
THEME_OVERRIDES: dict[str, dict[str, str]] = {
    "blue": {},
    "graphite": {
        "#2D7DFF": "#6C8CB0",
        "#3D8BFF": "#7E9CBD",
        "#4B8DFF": "#7C9AB8",
        "#6FA8FF": "#9DB6D4",
        "#2368DA": "#557191",
        "#1E4E9E": "#3C5570",
        "#172A46": "#2C3846",
        "#243B5B": "#3A4A5C",
        "#61748F": "#74828F",
        "#1A2940": "#333B45",
        "#1A2A40": "#333B45",
        "#1C3B66": "#33465C",
        "#172335": "#292D32",
        "#182231": "#282C31",
        "#151E2B": "#272A2E",
        "#141D2A": "#26292D",
        "#131C28": "#24272B",
        "#111A26": "#222427",
        "#0F151F": "#202225",
        "#0E1622": "#1D1F21",
        "#101823": "#1F2124",
        "#0C1119": "#17181A",
        "#0B1017": "#161718",
        "#0A0F16": "#18191B",
        "#090D14": "#121314",
        "#080D14": "#101112",
        "#03060B": "#0C0D0E",
        "#FFCA3F": "#E0B24A",
        "#FF9A9A": "#E08A8A",
        "#F0F5FF": "#E8ECF2",
        "#F8FCFF": "#E8ECF2",
        "#FFFFFF": "#FFFFFF",
        "#172943": "#232527",
        "#121B28": "#1A1B1C",
        "#121A28": "#191A1B",
        "#111A26": "#1E2022",
        "#2A3A50": "#343638",
        "#8FB8FF": "#93A7BC",
        "#9FB3CF": "#A7B4C4",
        "#BFD5F4": "#C3CDD8",
        "#A8B7CB": "#9AA5B1",
        "#BFD0E6": "#C2CBD5",
        "#63738B": "#9AA0A8",
        "#445166": "#7C828A",
        "#B9C7D8": "#C4C5C6",
        "#EDF4FF": "#E9EAEB",
        "#F2F7FF": "#EDEEEF",
    },
    "light": {
        "#2D7DFF": "#2563EB",
        "#3D8BFF": "#3B82F6",
        "#4B8DFF": "#3B82F6",
        "#6FA8FF": "#60A5FA",
        "#2368DA": "#1D4ED8",
        "#1E4E9E": "#1E40AF",
        "#172A46": "#E2E8F0",
        "#243B5B": "#CBD5E1",
        "#61748F": "#94A3B8",
        "#1A2940": "#DCE9FF",
        "#1A2A40": "#DCE9FF",
        "#1C3B66": "#DCE9FF",
        "#FFCA3F": "#B7791F",
        "#FF9A9A": "#D64545",
        "#F0F5FF": "#FFFFFF",
        "#F8FCFF": "#FFFFFF",
        "#FFFFFF": "#FFFFFF",
        "#172943": "#EDF2FA",
        "#121B28": "#FFFFFF",
        "#121A28": "#F4F7FC",
        "#111A26": "#E7EDF5",
        "#2A3A50": "#D2DBE6",
        "#8FB8FF": "#4B7FD6",
        "#9FB3CF": "#7D8DA4",
        "#BFD5F4": "#4B596D",
        "#A8B7CB": "#5C6A7F",
        "#BFD0E6": "#3A4A5C",
        "#63738B": "#5A6B7E",
        "#445166": "#74849A",
        "#B9C7D8": "#5A6B7E",
        "#EDF4FF": "#1B232E",
        "#F2F7FF": "#16202B",
    },
}

CUSTOM_ACCENT: Optional[str] = None
CUSTOM_CANVAS: Optional[str] = None
_THEME_UNSET = object()


def _blend(first: QColor, second: QColor, amount: float) -> QColor:
    amount = clamp(amount, 0.0, 1.0)
    return QColor(
        round(first.red() * (1.0 - amount) + second.red() * amount),
        round(first.green() * (1.0 - amount) + second.green() * amount),
        round(first.blue() * (1.0 - amount) + second.blue() * amount),
    )


def _rgba(color_hex: str, alpha: float) -> str:
    color = QColor(color_hex)
    return (
        f"rgba({color.red()}, {color.green()}, {color.blue()}, {round(alpha, 3)})"
    )


def _accent_overrides(accent_hex: str, window: QColor) -> dict[str, str]:
    accent = QColor(accent_hex)
    if not accent.isValid():
        return {}
    return {
        "#2D7DFF": accent.name(),
        "#3D8BFF": accent.lighter(112).name(),
        "#4B8DFF": accent.lighter(118).name(),
        "#6FA8FF": accent.lighter(138).name(),
        "#2368DA": accent.darker(112).name(),
        "#1E4E9E": accent.darker(135).name(),
        "#1A2940": _blend(accent, window, 0.72).name(),
        "#1A2A40": _blend(accent, window, 0.74).name(),
        "#1C3B66": _blend(accent, window, 0.55).name(),
        "#172A46": _blend(accent, window, 0.66).name(),
        "#243B5B": _blend(accent, window, 0.60).name(),
        "#172335": _blend(accent, window, 0.82).name(),
        "#182231": _blend(accent, window, 0.84).name(),
        "#151E2B": _blend(accent, window, 0.86).name(),
        "#141D2A": _blend(accent, window, 0.84).name(),
        "#1B283A": _blend(accent, window, 0.78).name(),
        "#1B2636": _blend(accent, window, 0.80).name(),
        "#1A2230": _blend(accent, window, 0.72).name(),
        "#26344A": _blend(accent, window, 0.62).name(),
        "#2A3B53": _blend(accent, window, 0.60).name(),
        "#2A3850": _blend(accent, window, 0.62).name(),
        "#243248": _blend(accent, window, 0.62).name(),
        "#345176": _blend(accent, window, 0.45).name(),
        "#3B4D67": _blend(accent, window, 0.48).name(),
        "#202B3A": _blend(accent, window, 0.68).name(),
        "#202B39": _blend(accent, window, 0.68).name(),
        "#202B3B": _blend(accent, window, 0.68).name(),
        "#1D2735": _blend(accent, window, 0.66).name(),
        "#223047": _blend(accent, window, 0.66).name(),
        "#263243": _blend(accent, window, 0.66).name(),
        "#2A3647": _blend(accent, window, 0.66).name(),
        "#1C2634": _blend(accent, window, 0.64).name(),
        "#161F2B": _blend(accent, window, 0.68).name(),
        "#171F2B": _blend(accent, window, 0.68).name(),
        "#1E2837": _blend(accent, window, 0.64).name(),
        "#2A3546": _blend(accent, window, 0.66).name(),
        "#354155": _blend(accent, window, 0.62).name(),
        "#5A6678": _blend(accent, window, 0.52).name(),
        "#111A26": _blend(accent, window, 0.84).name(),
    }


def _canvas_overrides(canvas_hex: str) -> dict[str, str]:
    canvas = QColor(canvas_hex)
    if not canvas.isValid():
        return {}
    hue, saturation, lightness, _alpha = canvas.getHslF()
    hue = hue if hue >= 0.0 else 0.0

    def shade(delta: float) -> str:
        return QColor.fromHslF(hue, saturation, clamp(lightness + delta, 0.0, 1.0)).name()

    return {
        "#090D14": canvas.name(),
        "#080D14": shade(-0.025),
        "#0A0F16": shade(0.02),
        "#0B1017": shade(-0.015),
        "#0C1119": shade(0.03),
        "#0E1622": shade(0.08),
        "#101823": shade(0.07),
        "#03060B": shade(-0.035),
        "#0F151F": shade(0.05),
        "#111A26": shade(0.09),
        "#111925": shade(0.09),
        "#131C28": shade(0.10),
        "#141D2A": shade(0.11),
        "#151E2B": shade(0.11),
    }


def theme_color_map(
    preset: str = "blue",
    accent=_THEME_UNSET,
    canvas=_THEME_UNSET,
) -> dict[str, str]:
    if preset not in THEME_PRESETS:
        preset = "blue"
    if accent is _THEME_UNSET:
        accent = CUSTOM_ACCENT
    if canvas is _THEME_UNSET:
        canvas = CUSTOM_CANVAS
    colors = set(QSS_HEX_RE.findall(APP_QSS))
    colors.update(THEME_EXTRA_COLORS)
    result = {value.upper(): value.upper() for value in colors}
    if preset != "blue":
        for source in list(result):
            overrides = THEME_OVERRIDES.get(preset, {})
            if source in overrides:
                result[source] = overrides[source]
                continue
            color = QColor(source)
            hue, saturation, lightness, _alpha = color.getHslF()
            hue = hue if hue >= 0.0 else 0.0
            if preset == "graphite":
                result[source] = QColor.fromHslF(hue, min(saturation, 0.035), lightness).name()
            else:
                result[source] = QColor.fromHslF(
                    hue, min(saturation, 0.34), clamp(1.0 - lightness, 0.0, 1.0)
                ).name()
        for source, target in THEME_OVERRIDES.get(preset, {}).items():
            result[source.upper()] = target
    if accent:
        window = QColor(result.get("#090D14", "#090D14"))
        for source, target in _accent_overrides(accent, window).items():
            result[source.upper()] = target
    if canvas:
        for source, target in _canvas_overrides(canvas).items():
            result[source.upper()] = target
    return result


def theme_qss(preset: str = "blue", accent: Optional[str] = None, canvas: Optional[str] = None) -> str:
    mapping = theme_color_map(preset, accent, canvas)
    qss = QSS_HEX_RE.sub(
        lambda match: mapping.get(match.group(0).upper(), match.group(0)), APP_QSS
    )
    accent_hex = mapping.get("#2D7DFF", "#2D7DFF")
    danger_hex = mapping.get("#FF9A9A", "#FF9A9A")
    qss = qss.replace("rgba(45, 125, 255, 0.16)", _rgba(accent_hex, 0.16))
    qss = qss.replace("rgba(45, 125, 255, 0.55)", _rgba(accent_hex, 0.55))
    qss = qss.replace("rgba(235, 82, 82, 0.13)", _rgba(danger_hex, 0.13))
    qss = qss.replace("rgba(235, 82, 82, 0.28)", _rgba(danger_hex, 0.28))
    return qss


def apply_theme_globals(
    preset: str = "blue",
    accent: Optional[str] = None,
    canvas: Optional[str] = None,
) -> None:
    global CURRENT_THEME, CURRENT_THEME_MAP, CUSTOM_ACCENT, CUSTOM_CANVAS
    global BG_COLOR, CANVAS_GRID_MINOR, CANVAS_GRID_MAJOR
    global ACCENT, ACCENT_LIGHT, ACCENT_DIM, YELLOW
    global TEXT_MAIN, TEXT_MUTED, TEXT_FAINT, CARD_BG, CARD_BORDER, ICON_COLOR
    global TEXT_NODE_FILL, TEXT_NODE_TEXT, SHAPE_FILL, SHAPE_TEXT, COMMENT_TEXT
    global IMAGE_FILL, IMAGE_BORDER, PORT_FILL, PORT_BORDER, HANDLE_FILL, NODE_SHADOW_ALPHA

    if preset not in THEME_PRESETS:
        preset = "blue"
    CUSTOM_ACCENT = accent
    CUSTOM_CANVAS = canvas
    CURRENT_THEME = preset
    mapping = theme_color_map(preset, accent, canvas)
    CURRENT_THEME_MAP = mapping

    def value(key: str) -> str:
        return mapping.get(key.upper(), key)

    BG_COLOR = value("#090D14")
    if preset == "light":
        CANVAS_GRID_MINOR = QColor(94, 114, 145, 44)
        CANVAS_GRID_MAJOR = QColor(94, 114, 145, 92)
    elif preset == "graphite":
        CANVAS_GRID_MINOR = QColor(150, 150, 150, 34)
        CANVAS_GRID_MAJOR = QColor(162, 162, 162, 74)
    else:
        CANVAS_GRID_MINOR = QColor(116, 139, 173, 38)
        CANVAS_GRID_MAJOR = QColor(126, 154, 196, 74)
    ACCENT = value("#2D7DFF")
    ACCENT_LIGHT = value("#6FA8FF")
    ACCENT_DIM = value("#1E4E9E")
    YELLOW = value("#FFCA3F")
    TEXT_MAIN = value("#DCE7F6")
    TEXT_MUTED = value("#7D8CA3")
    TEXT_FAINT = value("#4F5D72")
    CARD_BG = value("#121B28")
    CARD_BORDER = value("#26344A")
    ICON_COLOR = value("#C8D5E7")
    TEXT_NODE_FILL = value("#121A28")
    TEXT_NODE_TEXT = value("#EDF4FF")
    SHAPE_FILL = value("#172943")
    SHAPE_TEXT = value("#F2F7FF")
    COMMENT_TEXT = value("#B9C7D8")
    IMAGE_FILL = value("#111A26")
    IMAGE_BORDER = value("#2A3A50")
    PORT_FILL = value("#8FB8FF")
    PORT_BORDER = value("#070B11")
    HANDLE_FILL = value("#F8FCFF")
    NODE_SHADOW_ALPHA = 24 if preset == "light" else 56


def theme_preview_icon(preset: str) -> QIcon:
    mapping = theme_color_map(preset, None, None)
    def color(key: str) -> QColor:
        return QColor(mapping.get(key.upper(), key))

    pixmap = QPixmap(82, 56)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color("#090D14"))
    painter.drawRoundedRect(QRectF(1.0, 1.0, 80.0, 54.0), 7.0, 7.0)
    painter.setBrush(color("#0C1119"))
    painter.drawRoundedRect(QRectF(1.0, 1.0, 80.0, 17.0), 7.0, 7.0)
    painter.drawRect(QRectF(1.0, 11.0, 80.0, 7.0))
    painter.setBrush(color("#2D7DFF"))
    painter.drawRoundedRect(QRectF(6.0, 21.0, 26.0, 9.0), 3.0, 3.0)
    painter.setBrush(color("#121B28"))
    painter.drawRoundedRect(QRectF(6.0, 35.0, 32.0, 14.0), 3.0, 3.0)
    painter.setBrush(color("#26344A"))
    painter.setPen(QPen(color("#26344A"), 1.0))
    painter.drawRoundedRect(QRectF(44.0, 21.0, 30.0, 28.0), 4.0, 4.0)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color("#DCE7F6"))
    painter.drawRoundedRect(QRectF(48.0, 26.0, 18.0, 2.5), 1.2, 1.2)
    painter.drawRoundedRect(QRectF(48.0, 32.0, 22.0, 2.5), 1.2, 1.2)
    painter.setBrush(color("#2D7DFF"))
    painter.drawRoundedRect(QRectF(48.0, 38.0, 14.0, 2.5), 1.2, 1.2)
    painter.end()
    return QIcon(pixmap)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_ORG, APP_NAME)
        self.current_file: Optional[str] = None
        self._dirty = False
        self._syncing_ui = False
        self._dark_titlebar_applied = False
        self._clipboard: Optional[dict] = None
        self._paste_serial = 0
        saved_theme = str(self.settings.value("theme", "blue") or "blue")
        if saved_theme not in THEME_PRESETS:
            saved_theme = "blue"
        saved_accent = str(self.settings.value("themeAccent", "") or "")
        saved_canvas = str(self.settings.value("themeCanvas", "") or "")
        saved_accent = saved_accent if QColor(saved_accent).isValid() else None
        saved_canvas = saved_canvas if QColor(saved_canvas).isValid() else None
        directory = str(
            self.settings.value(
                "lastDir",
                QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation),
            )
            or os.path.expanduser("~")
        )
        self.last_dir = directory if os.path.isdir(directory) else os.path.expanduser("~")

        self._hint_timer = QTimer(self)
        self._hint_timer.setSingleShot(True)
        self._hint_timer.timeout.connect(self._update_hint)

        self.scene = BoardScene(self)
        self.view = CanvasView(self.scene)

        self.updates = UpdateManager(APP_VERSION, self)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(brand_icon())
        self.setMinimumSize(1180, 680)
        self._build_ui()
        self._connect_signals()
        self._install_shortcuts()
        self._restore_window_state()

        self._update_document_ui()
        self._sync_grid_button()
        self._sync_format_buttons()
        self._sync_properties()
        self._update_counts()
        self._update_hint()
        self._on_zoom_changed(self.view.transform().m11())
        self.view.update_empty_state()
        self._apply_theme(saved_theme, saved_accent, saved_canvas, save=False)
        QTimer.singleShot(0, self.view.setFocus)
        # Look for a newer build shortly after launch, then every six hours.
        QTimer.singleShot(2500, self.updates.check)
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(6 * 60 * 60 * 1000)
        self._update_timer.timeout.connect(self.updates.check)
        self._update_timer.start()

    # ---- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._build_header())
        self.update_banner = UpdateBanner(self.updates, central)
        central_layout.addWidget(self.update_banner)
        central_layout.addWidget(self.view, 1)
        self.setCentralWidget(central)
        self._build_theme_panel()
        self._build_connection_panel()
        self._build_status_bar()

    # ---- updates ----------------------------------------------------------

    def _show_update_dialog(self) -> None:
        UpdateDialog(self.updates, self).exec()

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("Header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(18, 9, 18, 8)
        layout.setSpacing(8)

        top = QWidget()
        top.setObjectName("HeaderTop")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        logo = QLabel()
        logo.setObjectName("LogoBox")
        logo.setFixedSize(40, 40)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(brand_pixmap(31))
        logo.setToolTip("Wave Board")
        top_layout.addWidget(logo)

        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 1, 0, 1)
        title_stack.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setObjectName("BrandTitle")
        subtitle = QLabel("INFINITE VISUAL CANVAS")
        subtitle.setObjectName("BrandSub")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        top_layout.addLayout(title_stack)

        self.dirty_dot = QLabel("●")
        self.dirty_dot.setObjectName("DirtyDot")
        self.dirty_dot.setFixedWidth(12)
        self.dirty_dot.hide()
        self.doc_label = QLabel("Untitled board")
        self.doc_label.setObjectName("DocName")
        doc_widget = QWidget()
        doc_layout = QHBoxLayout(doc_widget)
        doc_layout.setContentsMargins(0, 0, 0, 0)
        doc_layout.setSpacing(5)
        doc_layout.addWidget(self.dirty_dot)
        doc_layout.addWidget(self.doc_label)
        top_layout.addSpacing(12)
        top_layout.addWidget(doc_widget)

        top_layout.addStretch(1)

        self.updates_btn = make_tool_button(
            "Updates",
            "download",
            "Check for a newer version of Wave Board",
            self._show_update_dialog,
            role="ghost",
        )
        top_layout.addWidget(self.updates_btn)
        self.theme_btn = make_tool_button(
            "Theme",
            "palette",
            "Change the app colors — presets, accent and background",
            lambda: self._show_theme_panel(),
            role="ghost",
        )
        top_layout.addWidget(self.theme_btn)
        self.new_btn = make_tool_button(
            "New", "new", "Create a new board (Ctrl+N)", lambda: self.new_board(), role="ghost"
        )
        self.open_btn = make_tool_button(
            "Open", "open", "Open a board JSON file (Ctrl+O)", lambda: self.open_board(), role="ghost"
        )
        self.save_btn = make_tool_button(
            "Save", "save", "Save the board as JSON (Ctrl+S)", lambda: self.save_board(), role="primary"
        )
        top_layout.addWidget(self.new_btn)
        top_layout.addWidget(self.open_btn)
        top_layout.addWidget(self.save_btn)

        layout.addWidget(top)

        tools = QWidget()
        tools.setObjectName("ToolRow")
        tool_layout = QHBoxLayout(tools)
        tool_layout.setContentsMargins(0, 0, 0, 0)
        tool_layout.setSpacing(6)

        self.add_text_btn = make_tool_button(
            "Add Text", "text", "Add a text note (menu includes comments)", lambda: self.add_text()
        )
        text_menu = QMenu(self.add_text_btn)
        note_action = text_menu.addAction(ui_icon("text", ICON_COLOR), "Text note")
        comment_action = text_menu.addAction(ui_icon("comment", ICON_COLOR), "Comment / caption")
        note_action.setProperty("iconName", "text")
        comment_action.setProperty("iconName", "comment")
        note_action.triggered.connect(lambda: self.add_text())
        comment_action.triggered.connect(lambda: self.add_comment())
        self.add_text_btn.setMenu(text_menu)
        self.add_text_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.add_image_btn = make_tool_button(
            "Add Image", "image", "Insert an image from your PC", lambda: self.add_image()
        )
        self.add_shape_btn = make_tool_button(
            "Add Shape",
            "shape",
            "Add a rectangle (open the menu for a square)",
            lambda: self.add_rectangle(),
        )
        shape_menu = QMenu(self.add_shape_btn)
        rectangle_action = shape_menu.addAction(ui_icon("rectangle", ICON_COLOR), "Rectangle")
        square_action = shape_menu.addAction(ui_icon("square", ICON_COLOR), "Square")
        rectangle_action.setProperty("iconName", "rectangle")
        square_action.setProperty("iconName", "square")
        rectangle_action.triggered.connect(lambda: self.add_rectangle())
        square_action.triggered.connect(lambda: self.add_square())
        self.add_shape_btn.setMenu(shape_menu)
        self.add_shape_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        tool_layout.addWidget(self.add_text_btn)
        tool_layout.addWidget(self.add_image_btn)
        tool_layout.addWidget(self.add_shape_btn)
        tool_layout.addWidget(make_divider())

        line_label = QLabel("LINE")
        line_label.setObjectName("SectionLabel")
        tool_layout.addWidget(line_label)
        segmented = QFrame()
        segmented.setObjectName("Segmented")
        segmented.setFixedHeight(30)
        segmented_layout = QHBoxLayout(segmented)
        segmented_layout.setContentsMargins(2, 1, 2, 1)
        segmented_layout.setSpacing(1)
        self.thick_btn = QToolButton()
        self.thick_btn.setText("Thick")
        self.thick_btn.setProperty("iconName", "thick")
        self.thick_btn.setProperty("iconTone", "soft")
        self.thick_btn.setIcon(ui_icon("thick", CURRENT_THEME_MAP.get("#BFD5F4", "#BFD5F4")))
        self.thick_btn.setIconSize(QSize(15, 15))
        self.thick_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.thick_btn.setProperty("role", "segment")
        self.thick_btn.setCheckable(True)
        self.thick_btn.setChecked(True)
        self.thick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thick_btn.setFixedHeight(26)
        self.thick_btn.setToolTip("Thick solid connections for primary links")
        self.thin_btn = QToolButton()
        self.thin_btn.setText("Thin")
        self.thin_btn.setProperty("iconName", "thin")
        self.thin_btn.setProperty("iconTone", "soft")
        self.thin_btn.setIcon(ui_icon("thin", CURRENT_THEME_MAP.get("#9FB3CF", "#9FB3CF")))
        self.thin_btn.setIconSize(QSize(15, 15))
        self.thin_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.thin_btn.setProperty("role", "segment")
        self.thin_btn.setCheckable(True)
        self.thin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.thin_btn.setFixedHeight(26)
        self.thin_btn.setToolTip("Thin dashed connections for secondary links")
        self.line_group = QButtonGroup(self)
        self.line_group.setExclusive(True)
        self.line_group.addButton(self.thick_btn)
        self.line_group.addButton(self.thin_btn)
        segmented_layout.addWidget(self.thick_btn)
        segmented_layout.addWidget(self.thin_btn)
        tool_layout.addWidget(segmented)
        tool_layout.addWidget(make_divider())

        corner_label = QLabel("CORNER")
        corner_label.setObjectName("SectionLabel")
        tool_layout.addWidget(corner_label)
        self.radius_slider = QSlider(Qt.Orientation.Horizontal)
        self.radius_slider.setRange(0, 90)
        self.radius_slider.setValue(int(self.scene.default_shape_radius))
        self.radius_slider.setFixedWidth(104)
        self.radius_slider.setToolTip("Corner radius of the selected shape — updates in real time")
        self.radius_value = QLabel(str(int(self.scene.default_shape_radius)))
        self.radius_value.setObjectName("ValuePill")
        self.radius_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.radius_value.setFixedWidth(31)
        tool_layout.addWidget(self.radius_slider)
        tool_layout.addWidget(self.radius_value)
        tool_layout.addWidget(make_divider())

        self.grid_btn = make_tool_button("Grid", "grid", "Show or hide the background grid (Ctrl+G)", None, checkable=True)
        self.grid_btn.setChecked(True)
        tool_layout.addWidget(self.grid_btn)
        tool_layout.addWidget(make_divider())

        self.fill_btn = ColorSwatchButton(
            "fill", self.scene.default_shape_fill, "Shape fill", "Fill color of selected shapes"
        )
        self.border_btn = ColorSwatchButton(
            "border",
            self.scene.default_shape_border,
            "Shape border",
            "Border color of selected shapes",
        )
        self.text_color_btn = ColorSwatchButton(
            "text",
            self.scene.default_text_color,
            "Text color",
            "Text color of selected notes and shapes",
        )
        tool_layout.addWidget(self.fill_btn)
        tool_layout.addWidget(self.border_btn)
        tool_layout.addWidget(self.text_color_btn)

        font_label = QLabel("Aa")
        font_label.setObjectName("SectionLabel")
        tool_layout.addWidget(font_label)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 84)
        self.font_spin.setValue(int(self.scene.default_font_size))
        self.font_spin.setFixedWidth(50)
        self.font_spin.setFixedHeight(30)
        self.font_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.font_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.font_spin.setToolTip("Font size of selected notes and shapes")
        tool_layout.addWidget(self.font_spin)

        tool_layout.addStretch(1)
        self.delete_btn = make_tool_button(
            "Delete",
            "delete",
            "Delete selected items (Delete or Backspace)",
            lambda: self.delete_selected(),
            role="danger",
        )
        tool_layout.addWidget(self.delete_btn)

        layout.addWidget(tools)
        layout.addWidget(self._build_format_row())
        return header

    def _build_format_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("ToolRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        text_label = QLabel("TEXT")
        text_label.setObjectName("SectionLabel")
        layout.addWidget(text_label)

        self.align_group = QButtonGroup(self)
        self.align_group.setExclusive(True)
        self.align_buttons: dict[str, QToolButton] = {}
        for value, icon_name, tooltip in (
            ("left", "align_left", "Align text left"),
            ("center", "align_center", "Center text horizontally"),
            ("right", "align_right", "Align text right"),
        ):
            button = QToolButton()
            button.setProperty("iconName", icon_name)
            button.setProperty("iconTone", "soft")
            button.setIcon(ui_icon(icon_name, CURRENT_THEME_MAP.get("#BFD0E6", "#BFD0E6")))
            button.setIconSize(QSize(15, 15))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setProperty("role", "segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(28, 26)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda checked=False, value=value: self._on_text_align(value))
            self.align_group.addButton(button)
            self.align_buttons[value] = button
            layout.addWidget(button)

        layout.addWidget(make_divider())

        self.valign_group = QButtonGroup(self)
        self.valign_group.setExclusive(True)
        self.valign_buttons: dict[str, QToolButton] = {}
        for value, icon_name, tooltip in (
            ("top", "valign_top", "Align text to the top"),
            ("middle", "valign_middle", "Center text vertically"),
            ("bottom", "valign_bottom", "Align text to the bottom"),
        ):
            button = QToolButton()
            button.setProperty("iconName", icon_name)
            button.setProperty("iconTone", "soft")
            button.setIcon(ui_icon(icon_name, CURRENT_THEME_MAP.get("#BFD0E6", "#BFD0E6")))
            button.setIconSize(QSize(15, 15))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setProperty("role", "segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(28, 26)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda checked=False, value=value: self._on_text_valign(value))
            self.valign_group.addButton(button)
            self.valign_buttons[value] = button
            layout.addWidget(button)

        layout.addWidget(make_divider())

        self.font_combo = QComboBox()
        self.font_combo.setObjectName("FontCombo")
        self.font_combo.setFixedHeight(26)
        self.font_combo.setMinimumWidth(130)
        self.font_combo.setMaximumWidth(170)
        self.font_combo.setToolTip(
            "Font family — applies to the text selection, or the whole selected note/shape"
        )
        families = QFontDatabase.families()
        current_family = self.scene.default_font_family or "Segoe UI"
        if not families:
            families = ["Segoe UI"]
        elif current_family not in families:
            families = [current_family] + list(families)
        for family in sorted(families, key=str.casefold):
            self.font_combo.addItem(family)
        self.font_combo.setCurrentText(current_family)
        self.font_combo.currentTextChanged.connect(self._on_font_family_changed)
        layout.addWidget(self.font_combo)

        self.bold_btn = QToolButton()
        self.bold_btn.setText("B")
        self.bold_btn.setProperty("role", "segment")
        self.bold_btn.setCheckable(True)
        self.bold_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bold_btn.setFixedSize(28, 26)
        bold_font = QFont("Segoe UI", 10)
        bold_font.setWeight(QFont.Weight.Bold)
        self.bold_btn.setFont(bold_font)
        self.bold_btn.setToolTip(
            "Bold — applies to the text selection, or the whole selected note/shape"
        )
        self.bold_btn.toggled.connect(self._on_bold_toggled)
        layout.addWidget(self.bold_btn)

        self.text_fit_btn = QToolButton()
        self.text_fit_btn.setText("Fit")
        self.text_fit_btn.setProperty("iconName", "fit")
        self.text_fit_btn.setProperty("iconTone", "soft")
        self.text_fit_btn.setIcon(ui_icon("fit", CURRENT_THEME_MAP.get("#BFD0E6", "#BFD0E6")))
        self.text_fit_btn.setIconSize(QSize(14, 14))
        self.text_fit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.text_fit_btn.setProperty("role", "segment")
        self.text_fit_btn.setCheckable(True)
        self.text_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_fit_btn.setFixedHeight(26)
        self.text_fit_btn.setToolTip("Shrink the text until it fits inside the selected box")
        self.text_fit_btn.clicked.connect(self._on_text_fit)
        layout.addWidget(self.text_fit_btn)

        layout.addWidget(make_divider())

        self.magnet_btn = make_tool_button(
            "Magnet",
            "magnet",
            "Magnetic alignment guides for nodes and grid points (hold Ctrl while moving to use it temporarily)",
            None,
            checkable=True,
        )
        self.magnet_btn.setChecked(True)
        layout.addWidget(self.magnet_btn)

        self.inherit_btn = make_tool_button(
            "Copy Style",
            "inherit",
            "New links copy the most-used weight, dash, route and color in their group",
            None,
            checkable=True,
        )
        self.inherit_btn.setChecked(True)
        layout.addWidget(self.inherit_btn)

        self.bundle_btn = make_tool_button(
            "Bundle",
            "bundle",
            "Fan multiple links that share a port into a clean parallel bundle",
            None,
            checkable=True,
        )
        self.bundle_btn.setChecked(True)
        layout.addWidget(self.bundle_btn)

        layout.addStretch(1)

        tip = QLabel("Shift+drag a box onto a link to insert it · hold Ctrl for magnet")
        tip.setObjectName("StatusHint")
        layout.addWidget(tip)
        return row

    def _build_theme_panel(self) -> None:
        panel = QFrame(self)
        panel.setObjectName("ThemePanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        panel.setFixedWidth(274)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 13, 14, 14)
        layout.setSpacing(9)

        heading = QLabel("APPEARANCE")
        heading.setObjectName("ThemeHeading")
        layout.addWidget(heading)

        theme_caption = QLabel("THEME")
        theme_caption.setObjectName("ThemeCaption")
        layout.addWidget(theme_caption)

        cards = QWidget()
        card_layout = QHBoxLayout(cards)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(7)
        self.theme_cards: dict[str, QToolButton] = {}
        for preset in THEME_PRESETS:
            card = QToolButton()
            card.setProperty("role", "themeCard")
            card.setCheckable(True)
            card.setAutoExclusive(False)
            card.setText(THEME_LABELS[preset])
            card.setIcon(theme_preview_icon(preset))
            card.setIconSize(QSize(70, 48))
            card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            card.setFixedSize(76, 80)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setToolTip(f"Switch the whole app to the {THEME_LABELS[preset]} theme")
            card.clicked.connect(lambda checked=False, p=preset: self._choose_theme(p))
            card_layout.addWidget(card)
            self.theme_cards[preset] = card
        layout.addWidget(cards)

        accent_caption = QLabel("ACCENT")
        accent_caption.setObjectName("ThemeCaption")
        layout.addWidget(accent_caption)
        self.accent_btn = ThemeColorButton(
            QColor(ACCENT),
            "Accent color",
            "Tint buttons, ports and links across the whole app",
        )
        self.accent_btn.colorPicked.connect(self._on_accent_preview)
        self.accent_btn.colorCommitted.connect(self._on_accent_commit)
        layout.addWidget(self.accent_btn)

        canvas_caption = QLabel("BACKGROUND")
        canvas_caption.setObjectName("ThemeCaption")
        layout.addWidget(canvas_caption)
        self.canvas_btn = ThemeColorButton(
            QColor(BG_COLOR),
            "Background color",
            "Recolor the canvas and the surrounding panels",
        )
        self.canvas_btn.colorPicked.connect(self._on_canvas_preview)
        self.canvas_btn.colorCommitted.connect(self._on_canvas_commit)
        layout.addWidget(self.canvas_btn)

        reset = QToolButton()
        reset.setText("Reset colors")
        reset.setProperty("role", "ghost")
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.setFixedHeight(30)
        reset.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        reset.setToolTip("Return to the theme's original accent and background")
        reset.clicked.connect(self._reset_theme_colors)
        layout.addWidget(reset)

        note = QLabel("Changes apply live and are remembered next launch.")
        note.setObjectName("ThemeCaption")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.theme_panel = panel
        panel.hide()

    def _show_theme_panel(self) -> None:
        panel = getattr(self, "theme_panel", None)
        if panel is None:
            return
        self._sync_theme_panel()
        panel.adjustSize()
        position = self.theme_btn.mapToGlobal(QPoint(0, self.theme_btn.height() + 8))
        screen = self.theme_btn.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            if position.x() + panel.width() > area.right():
                position.setX(max(area.left(), area.right() - panel.width()))
            if position.y() + panel.height() > area.bottom():
                position.setY(max(area.top(), self.theme_btn.mapToGlobal(QPoint(0, 0)).y() - panel.height() - 8))
        panel.move(position)
        panel.show()
        panel.raise_()

    def _sync_theme_panel(self) -> None:
        for preset, card in getattr(self, "theme_cards", {}).items():
            card.setChecked(preset == CURRENT_THEME)
        accent_btn = getattr(self, "accent_btn", None)
        if accent_btn is not None:
            accent_btn.set_color(QColor(ACCENT), emit=False)
        canvas_btn = getattr(self, "canvas_btn", None)
        if canvas_btn is not None:
            canvas_btn.set_color(QColor(BG_COLOR), emit=False)

    def _current_accent(self) -> Optional[str]:
        return CUSTOM_ACCENT

    def _choose_theme(self, preset: str) -> None:
        self._apply_theme(preset, CUSTOM_ACCENT, CUSTOM_CANVAS, save=True)

    def _on_accent_preview(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._apply_theme(CURRENT_THEME, color.name(), CUSTOM_CANVAS, save=False)

    def _on_accent_commit(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._apply_theme(CURRENT_THEME, color.name(), CUSTOM_CANVAS, save=True)

    def _on_canvas_preview(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._apply_theme(CURRENT_THEME, CUSTOM_ACCENT, color.name(), save=False)

    def _on_canvas_commit(self, color: QColor) -> None:
        if not color.isValid():
            return
        self._apply_theme(CURRENT_THEME, CUSTOM_ACCENT, color.name(), save=True)

    def _reset_theme_colors(self) -> None:
        self._apply_theme(CURRENT_THEME, None, None, save=True)

    def _theme_tokens(self) -> dict[str, str]:
        return {
            "accent": ACCENT,
            "card_border": CARD_BORDER,
            "text_node_fill": TEXT_NODE_FILL,
            "text_node_text": TEXT_NODE_TEXT,
            "comment_text": COMMENT_TEXT,
            "shape_fill": SHAPE_FILL,
            "shape_text": SHAPE_TEXT,
            "image_fill": IMAGE_FILL,
            "image_border": IMAGE_BORDER,
        }

    def _retheme_scene(self, old: dict[str, str], new: dict[str, str]) -> None:
        lookup: dict[str, QColor] = {}
        for key, value in old.items():
            target = new.get(key)
            if not target:
                continue
            source_color = QColor(value)
            target_color = QColor(target)
            if not source_color.isValid() or not target_color.isValid():
                continue
            if source_color.name().lower() != target_color.name().lower():
                lookup[source_color.name().lower()] = target_color
        if not lookup:
            return

        def remap(color: QColor) -> Optional[QColor]:
            if not isinstance(color, QColor) or not color.isValid():
                return None
            replacement = lookup.get(color.name().lower())
            if replacement is None:
                return None
            result = QColor(replacement)
            result.setAlpha(color.alpha())
            return result

        for node in list(getattr(self.scene, "nodes", ())):
            try:
                for attribute in ("fill", "border", "text_color"):
                    current = getattr(node, attribute, None)
                    replacement = remap(current)
                    if replacement is not None:
                        setattr(node, attribute, replacement)
                if hasattr(node, "remap_text_colors"):
                    node.remap_text_colors(lookup)
                node.update()
            except RuntimeError:
                continue
        for connection in list(getattr(self.scene, "connections", ())):
            try:
                replacement = remap(connection.line_color)
                if replacement is not None:
                    connection.line_color = replacement
                    connection.update()
            except RuntimeError:
                continue

        scene = self.scene
        for attribute in ("default_line_color", "default_shape_fill", "default_shape_border", "default_text_color"):
            current = getattr(scene, attribute, None)
            replacement = remap(current)
            if replacement is not None:
                setattr(scene, attribute, replacement)

    def _refresh_theme_icons(self) -> None:
        zoom_tone = CURRENT_THEME_MAP.get("#A8B7CB", "#A8B7CB")
        soft_tone = CURRENT_THEME_MAP.get("#BFD0E6", "#BFD0E6")
        for button in self.findChildren(QToolButton):
            name = button.property("iconName")
            if not isinstance(name, str) or not name:
                continue
            tone_kind = button.property("iconTone")
            if tone_kind == "zoom":
                tone = zoom_tone
            elif tone_kind == "soft":
                tone = soft_tone
            else:
                tone = ICON_COLOR
            button.setIcon(ui_icon(name, tone))
        for menu in self.findChildren(QMenu):
            for action in menu.actions():
                name = action.property("iconName")
                if isinstance(name, str) and name:
                    action.setIcon(ui_icon(name, ICON_COLOR))

    def _apply_theme(
        self,
        preset: Optional[str] = None,
        accent: Optional[str] = None,
        canvas: Optional[str] = None,
        save: bool = True,
    ) -> None:
        preset = preset if preset in THEME_PRESETS else CURRENT_THEME
        if preset not in THEME_PRESETS:
            preset = "blue"
        accent = accent or None
        canvas = canvas or None
        old_tokens = self._theme_tokens()
        apply_theme_globals(preset, accent, canvas)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(theme_palette(preset, accent, canvas))
            app.setStyleSheet(theme_qss(preset, accent, canvas))
        self._retheme_scene(old_tokens, self._theme_tokens())
        self._refresh_theme_icons()
        view = getattr(self, "view", None)
        if view is not None:
            view.update_empty_style()
            view.viewport().update()
        self.scene.update()

        if save:
            try:
                self.settings.setValue("theme", preset)
                self.settings.setValue("themeAccent", accent or "")
                self.settings.setValue("themeCanvas", canvas or "")
                self.settings.sync()
            except Exception:
                pass

        self._sync_theme_panel()
        line_btn = getattr(self, "line_color_btn", None)
        if line_btn is not None:
            line_btn.set_color(self.scene.default_line_color)
        if not self.scene.selected_nodes():
            self.fill_btn.set_color(self.scene.default_shape_fill)
            self.border_btn.set_color(self.scene.default_shape_border)
            self.text_color_btn.set_color(self.scene.default_text_color)
        self._sync_properties()
        if self.isVisible():
            apply_dark_title_bar(self, preset)
        self._repaint_widgets()

    def _repaint_widgets(self) -> None:
        for widget in self.findChildren(QWidget):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def _build_connection_panel(self) -> None:
        panel = QFrame(self.view.viewport())
        panel.setObjectName("LinePanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.hide()

        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(7)

        self.line_panel_title = QLabel("LINE")
        self.line_panel_title.setObjectName("LinePanelTitle")
        layout.addWidget(self.line_panel_title)
        layout.addWidget(self._panel_divider())

        self.route_group = QButtonGroup(self)
        self.route_group.setExclusive(True)
        self.route_buttons: dict[str, QToolButton] = {}
        layout.addWidget(self._panel_group_label("ROUTE"))
        for value, text, tooltip in (
            ("curve", "Soft", "Soft curved connection"),
            ("elbow", "Sharp", "Sharp right-angle routing"),
            ("straight", "Straight", "Direct line between ports"),
        ):
            button = self._panel_segment(text, tooltip, self.route_group)
            button.clicked.connect(
                lambda checked=False, value=value: self._on_connection_route(value)
            )
            self.route_buttons[value] = button
            layout.addWidget(button)
        layout.addWidget(self._panel_divider())

        self.weight_group = QButtonGroup(self)
        self.weight_group.setExclusive(True)
        self.weight_buttons: dict[str, QToolButton] = {}
        layout.addWidget(self._panel_group_label("WEIGHT"))
        for value, text, tooltip in (
            ("thin", "Thin", "Thin line"),
            ("medium", "Medium", "Medium line"),
            ("thick", "Wide", "Wide line"),
        ):
            button = self._panel_segment(text, tooltip, self.weight_group)
            button.clicked.connect(
                lambda checked=False, value=value: self._on_connection_weight(value)
            )
            self.weight_buttons[value] = button
            layout.addWidget(button)
        layout.addWidget(self._panel_divider())

        self.dash_group = QButtonGroup(self)
        self.dash_group.setExclusive(True)
        self.dash_buttons: dict[str, QToolButton] = {}
        layout.addWidget(self._panel_group_label("DASH"))
        for value, text, tooltip in (
            ("solid", "Solid", "Solid line"),
            ("dashed", "Dash", "Dashed line"),
            ("dotted", "Dot", "Dotted line"),
        ):
            button = self._panel_segment(text, tooltip, self.dash_group)
            button.clicked.connect(
                lambda checked=False, value=value: self._on_connection_dash(value)
            )
            self.dash_buttons[value] = button
            layout.addWidget(button)
        layout.addWidget(self._panel_divider())

        self.line_color_btn = ColorSwatchButton(
            "line",
            self.scene.default_line_color,
            "Line color",
            "Color of selected connections",
        )
        self.line_color_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.line_color_btn.setFixedSize(30, 30)
        self.line_color_btn.setIconSize(QSize(18, 18))
        layout.addWidget(self.line_color_btn)

        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 170))
        panel.setGraphicsEffect(shadow)
        self.line_panel = panel

    def _panel_group_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("LinePanelGroup")
        return label

    def _panel_divider(self) -> QFrame:
        divider = QFrame()
        divider.setObjectName("PanelDivider")
        divider.setFixedSize(1, 18)
        return divider

    def _panel_segment(self, text: str, tooltip: str, group: QButtonGroup) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setProperty("role", "segment")
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        preferred_widths = {
            "Soft": 46,
            "Sharp": 48,
            "Straight": 60,
            "Thin": 42,
            "Medium": 58,
            "Wide": 44,
            "Solid": 46,
            "Dash": 44,
            "Dot": 36,
        }
        button.setFixedSize(preferred_widths.get(text, 48), 24)
        group.addButton(button)
        return button

    def _position_connection_panel(self) -> None:
        panel = getattr(self, "line_panel", None)
        if panel is None:
            return
        viewport = self.view.viewport()
        hint = panel.sizeHint()
        width = min(max(300, hint.width()), max(300, viewport.width() - 28))
        height = max(42, hint.height())
        x = max(10, (viewport.width() - width) // 2)
        y = max(10, viewport.height() - height - 18)
        panel.setGeometry(x, y, width, height)
        if panel.isVisible():
            panel.raise_()

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(False)
        bar.setFixedHeight(32)
        self.setStatusBar(bar)

        self.hint_label = QLabel("")
        self.hint_label.setObjectName("StatusHint")
        bar.addWidget(self.hint_label, 1)

        self.count_label = QLabel("0 nodes · 0 links")
        self.count_label.setObjectName("StatusCount")
        bar.addPermanentWidget(self.count_label, 0)

        separator = QFrame()
        separator.setObjectName("StatusDivider")
        separator.setFixedSize(1, 14)
        bar.addPermanentWidget(separator, 0)

        self.zoom_out_btn = make_zoom_button("minus", "Zoom out", lambda: self.view.zoom_by(1.0 / 1.22))
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("ZoomLabel")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(40)
        self.zoom_in_btn = make_zoom_button("plus", "Zoom in", lambda: self.view.zoom_by(1.22))
        self.fit_btn = make_zoom_button("fit", "Fit board to view (Ctrl+0)", lambda: self.view.fit_content())
        self.help_btn = make_zoom_button("help", "Keyboard shortcuts (F1)", self.show_shortcuts)
        self.help_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        bar.addPermanentWidget(self.zoom_out_btn, 0)
        bar.addPermanentWidget(self.zoom_label, 0)
        bar.addPermanentWidget(self.zoom_in_btn, 0)
        bar.addPermanentWidget(self.fit_btn, 0)
        help_separator = QFrame()
        help_separator.setObjectName("StatusDivider")
        help_separator.setFixedSize(1, 14)
        bar.addPermanentWidget(help_separator, 0)
        bar.addPermanentWidget(self.help_btn, 0)

    def _connect_signals(self) -> None:
        self.scene.content_changed.connect(self._on_content_changed)
        self.scene.selectionChanged.connect(self._sync_properties)
        self.scene.editing_changed.connect(self._on_editing_changed)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        self.view.files_dropped.connect(self._on_files_dropped)
        self.view.background_double_clicked.connect(self._add_text_at)
        self.view.copy_requested.connect(self.copy_selection)
        self.view.cut_requested.connect(self.cut_selection)
        self.view.paste_requested.connect(self.paste_clipboard)
        self.view.duplicate_requested.connect(self.duplicate_selection)
        self.view.select_all_requested.connect(self._select_all)
        self.view.nudge_requested.connect(self._nudge_selected)
        self.view.edit_selected_requested.connect(self._edit_selected)
        self.view.resized.connect(self._position_connection_panel)
        self.grid_btn.toggled.connect(self._on_grid_toggled)
        self.magnet_btn.clicked.connect(self._on_magnet_toggled)
        self.inherit_btn.clicked.connect(self._on_inherit_toggled)
        self.bundle_btn.clicked.connect(self._on_bundle_toggled)
        self.radius_slider.valueChanged.connect(self._on_radius_changed)
        self.font_spin.valueChanged.connect(self._on_font_changed)
        self.fill_btn.colorPicked.connect(self._on_fill_changed)
        self.border_btn.colorPicked.connect(self._on_border_changed)
        self.text_color_btn.colorPicked.connect(self._on_text_color_changed)
        self.line_color_btn.colorPicked.connect(self._on_line_color_changed)
        self.thick_btn.clicked.connect(lambda checked=False: self._set_line_style("thick"))
        self.thin_btn.clicked.connect(lambda checked=False: self._set_line_style("thin"))

    def _install_shortcuts(self) -> None:
        self._add_shortcut("Ctrl+N", lambda: self.new_board())
        self._add_shortcut("Ctrl+O", lambda: self.open_board())
        self._add_shortcut("Ctrl+S", lambda: self.save_board())
        self._add_shortcut("Ctrl+Shift+S", lambda: self.save_board_as())
        self._add_shortcut("Ctrl+0", lambda: self.view.fit_content())
        self._add_shortcut("Ctrl+1", lambda: self.view.reset_view())
        self._add_shortcut("Ctrl+G", self._toggle_grid_shortcut)
        self._add_shortcut("F1", self.show_shortcuts)

    def _add_shortcut(self, sequence: str, slot) -> QAction:
        action = QAction(self)
        action.setShortcut(QKeySequence(sequence))
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action.triggered.connect(slot)
        self.addAction(action)
        return action

    def _toggle_grid_shortcut(self) -> None:
        self.grid_btn.toggle()

    def _restore_window_state(self) -> None:
        geometry = self.settings.value("geometry")
        restored = False
        if geometry is not None:
            try:
                restored = self.restoreGeometry(geometry)
            except TypeError:
                restored = False
        if restored:
            return
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(1500, max(1180, available.width() - 80))
            height = min(940, max(680, available.height() - 100))
            self.resize(width, height)
            self.move(available.center() - self.rect().center())
        else:
            self.resize(1480, 920)

    # ---- document state ---------------------------------------------------

    def _display_name(self) -> str:
        if self.current_file:
            return os.path.basename(self.current_file)
        return "Untitled board"

    def _update_document_ui(self) -> None:
        name = self._display_name()
        suffix = "  •" if self._dirty else ""
        self.setWindowTitle(f"{APP_NAME} — {name}{suffix}")
        elided = self.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, 320)
        self.doc_label.setText(elided)
        self.doc_label.setMaximumWidth(330)
        self.dirty_dot.setVisible(self._dirty)
        self.doc_label.setToolTip(self.current_file or "This board has not been saved yet")
        self.save_btn.setToolTip(
            f"Save to {self.current_file} (Ctrl+S)"
            if self.current_file
            else "Save the board as JSON (Ctrl+S)"
        )

    def _update_counts(self) -> None:
        nodes = len(self.scene.nodes)
        links = len(self.scene.connections)
        selected = len(self.scene.selectedItems())
        text = f"{nodes} {'node' if nodes == 1 else 'nodes'} · {links} {'link' if links == 1 else 'links'}"
        if selected:
            text += f"  ·  {selected} selected"
        self.count_label.setText(text)

    def _update_hint(self) -> None:
        if self.scene.is_editing_text():
            text = "Editing text — press Esc or click outside the note to finish"
        elif self.scene._connection_source is not None:
            text = "Release over another node to connect · Esc to cancel"
        else:
            nodes = self.scene.selected_nodes()
            connections = self.scene.selected_connections()
            if connections:
                text = (
                    "Click selected this link · double-click to remove · drag an end to relink · "
                    "scroll changes type · middle-click changes thickness"
                )
            elif nodes:
                text = (
                    "Shift+drag a box onto a link to snap it in the middle · hold Ctrl while moving for magnet · "
                    "Ctrl+click multi-select · F1 shortcuts"
                )
            elif self.scene.nodes:
                text = (
                    "Middle-drag or Space + drag to pan · Scroll to zoom · drag a port to connect · "
                    "Shift+drag onto a link inserts a node · F1 shortcuts"
                )
            else:
                text = "Double-click anywhere to add a note · Ctrl+V pastes · Middle-drag or Space + drag to pan · F1 shortcuts"
        self.hint_label.setText(text)

    def _flash_hint(self, text: str, milliseconds: int = 2600) -> None:
        self.hint_label.setText(text)
        self._hint_timer.start(milliseconds)

    def _on_content_changed(self) -> None:
        self._dirty = True
        self._update_document_ui()
        self._update_counts()
        self._update_hint()
        self.view.update_empty_state()

    def _on_editing_changed(self, editing: bool) -> None:
        self._update_hint()

    def _on_zoom_changed(self, scale: float) -> None:
        self.zoom_label.setText(f"{int(round(scale * 100))}%")

    # ---- selection / properties ------------------------------------------

    def _sync_properties(self) -> None:
        if self._syncing_ui:
            return
        nodes = self.scene.selected_nodes()
        connections = self.scene.selected_connections()
        shapes = [node for node in nodes if isinstance(node, ShapeNode)]
        text_nodes = [node for node in nodes if node.text_item is not None]
        self._syncing_ui = True
        try:
            self.radius_slider.setEnabled(bool(shapes))
            self.fill_btn.setEnabled(bool(shapes))
            self.border_btn.setEnabled(bool(shapes))
            self.font_spin.setEnabled(bool(text_nodes))
            self.text_color_btn.setEnabled(bool(text_nodes))
            self.font_combo.setEnabled(bool(text_nodes))
            self.bold_btn.setEnabled(bool(text_nodes))
            self.delete_btn.setEnabled(bool(nodes or connections))
            if shapes:
                self.radius_slider.setValue(int(round(shapes[0].radius)))
                self.radius_value.setText(str(int(round(shapes[0].radius))))
                self.fill_btn.set_color(shapes[0].fill)
                self.border_btn.set_color(shapes[0].border)
            if text_nodes:
                first = text_nodes[0]
                size = int(first.font_size)
                bold = bool(first.font_bold)
                family = first.font_family or "Segoe UI"
                color = QColor(first.text_color)
                fmt = first.selection_text_format()
                if fmt is not None:
                    if fmt.fontPointSize() > 0:
                        size = int(round(fmt.fontPointSize()))
                    bold = fmt.fontWeight() >= int(QFont.Weight.DemiBold)
                    if fmt.fontFamilies():
                        family = fmt.fontFamilies()[0]
                    brush = fmt.foreground()
                    if brush.style() != Qt.BrushStyle.NoBrush and brush.color().isValid():
                        color = brush.color()
                self.font_spin.setValue(size)
                self.text_color_btn.set_color(color)
                if self.font_combo.findText(family) < 0:
                    self.font_combo.addItem(family)
                self.font_combo.setCurrentText(family)
                self.bold_btn.setChecked(bold)
            weight = connections[0].line_weight if connections else self.scene.default_line_weight
            self._set_line_buttons_checked(weight)
            self._sync_connection_panel(connections)
            self._sync_text_controls(text_nodes)
        finally:
            self._syncing_ui = False
        self._update_counts()
        self._update_hint()

    def _set_line_buttons_checked(self, weight: str) -> None:
        self.line_group.setExclusive(False)
        self.thick_btn.setChecked(weight == "thick")
        self.thin_btn.setChecked(weight == "thin")
        self.line_group.setExclusive(True)

    def _sync_connection_panel(self, connections: list[ConnectionItem]) -> None:
        panel = getattr(self, "line_panel", None)
        if panel is None:
            return
        if not connections:
            panel.hide()
            return
        first = connections[0]
        previous = self._syncing_ui
        self._syncing_ui = True
        try:
            self.line_panel_title.setText(
                "LINE" if len(connections) == 1 else f"{len(connections)} LINES"
            )
            route_button = self.route_buttons.get(first.route)
            if route_button is not None:
                route_button.setChecked(True)
            weight_button = self.weight_buttons.get(first.line_weight)
            if weight_button is not None:
                weight_button.setChecked(True)
            dash_button = self.dash_buttons.get(first.dash_style)
            if dash_button is not None:
                dash_button.setChecked(True)
            self.line_color_btn.set_color(first.line_color)
        finally:
            self._syncing_ui = previous
        panel.show()
        self._position_connection_panel()
        panel.raise_()

    def _on_radius_changed(self, value: int) -> None:
        self.radius_value.setText(str(value))
        if self._syncing_ui:
            return
        shapes = [node for node in self.scene.selected_nodes() if isinstance(node, ShapeNode)]
        if not shapes:
            return
        self.scene.default_shape_radius = float(value)
        for shape in shapes:
            shape.set_radius(float(value))

    def _on_font_changed(self, value: int) -> None:
        if self._syncing_ui:
            return
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        if not nodes:
            return
        self.scene.default_font_size = int(value)
        for node in nodes:
            node.apply_text_size(int(value))

    def _on_font_family_changed(self, family: str) -> None:
        if self._syncing_ui or not family:
            return
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        if not nodes:
            return
        self.scene.default_font_family = family
        for node in nodes:
            node.apply_text_family(family)
        self._flash_hint(f"Font: {family}")

    def _on_bold_toggled(self, checked: bool) -> None:
        if self._syncing_ui:
            return
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        if not nodes:
            return
        for node in nodes:
            node.apply_text_bold(bool(checked))
        self._flash_hint("Text is bold" if checked else "Text is regular weight")

    def _on_fill_changed(self, color: QColor) -> None:
        self.scene.default_shape_fill = QColor(color)
        shapes = [node for node in self.scene.selected_nodes() if isinstance(node, ShapeNode)]
        for shape in shapes:
            shape.set_fill(color)

    def _on_border_changed(self, color: QColor) -> None:
        self.scene.default_shape_border = QColor(color)
        shapes = [node for node in self.scene.selected_nodes() if isinstance(node, ShapeNode)]
        for shape in shapes:
            shape.set_border(color)

    def _on_text_color_changed(self, color: QColor) -> None:
        self.scene.default_text_color = QColor(color)
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        for node in nodes:
            node.apply_text_color(color)

    def _set_line_style(self, style: str) -> None:
        if self._syncing_ui:
            return
        weight = "thin" if style == "thin" else "thick"
        dash = "dashed" if style == "thin" else "solid"
        self.scene.default_line_style = style
        self.scene.default_line_weight = weight
        self.scene.default_line_dash = dash
        connections = self.scene.selected_connections()
        for connection in connections:
            connection.set_style(style)
        self._set_line_buttons_checked(weight)
        self._sync_connection_panel(connections)
        if connections:
            self._flash_hint(
                "Primary connection style applied"
                if style == "thick"
                else "Secondary connection style applied"
            )
        self.view.setFocus()

    def _on_connection_route(self, route: str) -> None:
        if self._syncing_ui:
            return
        connections = self.scene.selected_connections()
        if not connections:
            return
        for connection in connections:
            connection.set_route(route)
        self.scene.default_line_route = route
        self._sync_connection_panel(connections)
        labels = {"curve": "Soft curve", "elbow": "Sharp corners", "straight": "Straight"}
        self._flash_hint(f"Line route: {labels.get(route, route)}")
        self.view.setFocus()

    def _on_connection_weight(self, weight: str) -> None:
        if self._syncing_ui:
            return
        connections = self.scene.selected_connections()
        if not connections:
            return
        for connection in connections:
            connection.set_weight(weight)
        self.scene.default_line_weight = weight
        self.scene.default_line_style = "thin" if weight == "thin" else "thick"
        self._set_line_buttons_checked(weight)
        self._sync_connection_panel(connections)
        labels = {"thin": "Thin", "medium": "Medium", "thick": "Wide"}
        self._flash_hint(f"Line weight: {labels.get(weight, weight)}")
        self.view.setFocus()

    def _on_connection_dash(self, dash: str) -> None:
        if self._syncing_ui:
            return
        connections = self.scene.selected_connections()
        if not connections:
            return
        for connection in connections:
            connection.set_dash_style(dash)
        self.scene.default_line_dash = dash
        self._sync_connection_panel(connections)
        labels = {"solid": "Solid", "dashed": "Dashed", "dotted": "Dotted"}
        self._flash_hint(f"Line style: {labels.get(dash, dash)}")
        self.view.setFocus()

    def _on_line_color_changed(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.scene.default_line_color = QColor(color)
        connections = self.scene.selected_connections()
        for connection in connections:
            connection.set_line_color(color)
        self._sync_connection_panel(connections)
        if connections:
            self._flash_hint("Line color updated")
        self.view.setFocus()

    def _on_grid_toggled(self, checked: bool) -> None:
        if self._syncing_ui:
            return
        self.scene.set_grid_enabled(checked)
        self._flash_hint("Grid enabled" if checked else "Grid hidden")

    def _sync_grid_button(self) -> None:
        self._syncing_ui = True
        try:
            self.grid_btn.setChecked(self.scene.grid_enabled)
        finally:
            self._syncing_ui = False

    def _sync_format_buttons(self) -> None:
        self._syncing_ui = True
        try:
            self.magnet_btn.setChecked(self.scene.magnet_enabled)
            self.inherit_btn.setChecked(self.scene.inherit_enabled)
            self.bundle_btn.setChecked(self.scene.bundle_enabled)
            self.text_fit_btn.setChecked(self.scene.default_text_fit)
            align = self.scene.default_text_align or "left"
            valign = self.scene.default_text_valign or "top"
            align_button = self.align_buttons.get(align)
            if align_button is not None:
                align_button.setChecked(True)
            valign_button = self.valign_buttons.get(valign)
            if valign_button is not None:
                valign_button.setChecked(True)
        finally:
            self._syncing_ui = False

    def _sync_text_controls(self, text_nodes: list[NodeItem]) -> None:
        first = text_nodes[0] if text_nodes else None
        align = first.text_align if first is not None else (self.scene.default_text_align or "left")
        valign = first.text_valign if first is not None else (self.scene.default_text_valign or "top")
        fit = first.text_fit if first is not None else self.scene.default_text_fit
        align_button = self.align_buttons.get(align)
        if align_button is not None:
            align_button.setChecked(True)
        valign_button = self.valign_buttons.get(valign)
        if valign_button is not None:
            valign_button.setChecked(True)
        self.text_fit_btn.setChecked(bool(fit))

    def _on_text_align(self, align: str) -> None:
        if self._syncing_ui or align not in TEXT_ALIGNS:
            return
        self.scene.default_text_align = align
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        for node in nodes:
            node.set_text_align(align)
        self._sync_text_controls(nodes)
        self._flash_hint(f"Text aligned {align}")
        self.view.setFocus()

    def _on_text_valign(self, valign: str) -> None:
        if self._syncing_ui or valign not in TEXT_VALIGNS:
            return
        self.scene.default_text_valign = valign
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        for node in nodes:
            node.set_text_valign(valign)
        self._sync_text_controls(nodes)
        labels = {"top": "top", "middle": "middle", "bottom": "bottom"}
        self._flash_hint(f"Text placed at the {labels.get(valign, valign)}")
        self.view.setFocus()

    def _on_text_fit(self, checked: bool = False) -> None:
        if self._syncing_ui:
            return
        enabled = bool(checked)
        self.scene.default_text_fit = enabled
        nodes = [node for node in self.scene.selected_nodes() if node.text_item is not None]
        for node in nodes:
            node.set_text_fit(enabled)
        self._sync_text_controls(nodes)
        self._flash_hint("Text now shrinks to fit its box" if enabled else "Text fit disabled")
        self.view.setFocus()

    def _on_magnet_toggled(self, checked: bool = False) -> None:
        if self._syncing_ui:
            return
        self.scene.set_magnet_enabled(bool(checked))
        self._flash_hint(
            "Magnet on - nodes snap to each other while moving"
            if checked
            else "Magnet off - hold Ctrl while moving to snap temporarily"
        )
        self.view.setFocus()

    def _on_inherit_toggled(self, checked: bool = False) -> None:
        if self._syncing_ui:
            return
        self.scene.set_inherit_enabled(bool(checked))
        self._flash_hint(
            "New links copy the most-used style in their group"
            if checked
            else "New links use the current line defaults"
        )
        self.view.setFocus()

    def _on_bundle_toggled(self, checked: bool = False) -> None:
        if self._syncing_ui:
            return
        self.scene.set_bundle_enabled(bool(checked))
        self._flash_hint(
            "Bundled links fan out neatly from shared ports"
            if checked
            else "Link bundling off"
        )
        self.view.setFocus()

    # ---- insertion --------------------------------------------------------

    def _view_center(self) -> QPointF:
        return self.view.mapToScene(self.view.viewport().rect().center())

    def _position_for_node(self, width: float, height: float, scene_pos: Optional[QPointF] = None) -> QPointF:
        center = QPointF(scene_pos) if scene_pos is not None else self._view_center()
        cascade = 0.0 if scene_pos is not None else float((len(self.scene.nodes) % 6) * 14)
        return QPointF(center.x() - width / 2.0 + cascade, center.y() - height / 2.0 + cascade)

    def add_text(self) -> None:
        self._add_text_at(self._view_center())

    def _apply_text_defaults(self, node: NodeItem) -> None:
        if self.scene.default_text_align in TEXT_ALIGNS:
            node.text_align = str(self.scene.default_text_align)
        if self.scene.default_text_valign in TEXT_VALIGNS:
            node.text_valign = str(self.scene.default_text_valign)
        node.text_fit = bool(self.scene.default_text_fit)
        family = getattr(self.scene, "default_font_family", "")
        if family:
            node.font_family = str(family)
        node._apply_text_style()
        node.layout_text()

    def _add_text_at(self, scene_pos: QPointF) -> None:
        node = TextNode()
        node.font_size = int(self.scene.default_font_size)
        node.text_color = QColor(self.scene.default_text_color)
        self._apply_text_defaults(node)
        position = self._position_for_node(node._width, node._height, QPointF(scene_pos))
        self.scene.add_node(node, position, select=True)
        self._flash_hint("New note added - type to write, Esc to finish")

        def start_editing() -> None:
            try:
                if node.scene() is self.scene:
                    node.begin_editing(select_all=True)
            except RuntimeError:
                pass

        QTimer.singleShot(30, start_editing)

    def add_comment(self) -> None:
        self._add_comment_at(self._view_center())

    def _add_comment_at(self, scene_pos: QPointF) -> None:
        node = CommentNode()
        node.font_size = int(self.scene.default_font_size)
        node.text_color = QColor(COMMENT_TEXT)
        node.text_align = "left"
        node.text_valign = "top"
        self._apply_text_defaults(node)
        if self.scene.default_text_align is None:
            node.text_align = "left"
        if self.scene.default_text_valign is None:
            node.text_valign = "top"
        node._apply_text_style()
        node.layout_text()
        position = self._position_for_node(node._width, node._height, QPointF(scene_pos))
        self.scene.add_node(node, position, select=True)
        self._flash_hint("Comment added - it cannot be linked")

        def start_editing() -> None:
            try:
                if node.scene() is self.scene:
                    node.begin_editing(select_all=True)
            except RuntimeError:
                pass

        QTimer.singleShot(30, start_editing)

    def _new_shape(self, shape_kind: str, width: float, height: float) -> ShapeNode:
        node = ShapeNode(width=width, height=height)
        node.shape_kind = shape_kind
        node.fill = QColor(self.scene.default_shape_fill)
        node.border = QColor(self.scene.default_shape_border)
        node.radius = float(self.scene.default_shape_radius)
        node.font_size = int(self.scene.default_font_size)
        node.text_color = QColor(self.scene.default_text_color)
        self._apply_text_defaults(node)
        position = self._position_for_node(width, height)
        self.scene.add_node(node, position, select=True)
        self._flash_hint("Shape added — double-click it to add text")
        return node

    def add_rectangle(self) -> None:
        self._new_shape("rectangle", 280.0, 170.0)

    def add_square(self) -> None:
        self._new_shape("square", 200.0, 200.0)

    def add_image(self) -> None:
        filters = (
            "Images (*.png *.jpg *.jpeg *.jfif *.bmp *.gif *.webp *.tif *.tiff *.ico);;"
            "All files (*)"
        )
        path, _ = QFileDialog.getOpenFileName(self, "Add image", self.last_dir, filters)
        if not path:
            return
        self.last_dir = os.path.dirname(path) or self.last_dir
        self.settings.setValue("lastDir", self.last_dir)
        self.add_image_from_path(path)

    def add_image_from_path(self, path: str, scene_pos: Optional[QPointF] = None) -> Optional[ImageNode]:
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as error:
            QMessageBox.critical(self, "Could not read image", f"{path}\n\n{error}")
            return None
        node = ImageNode()
        if not node.set_image_data(data, os.path.basename(path), path):
            QMessageBox.warning(
                self,
                "Unsupported image",
                f"Wave Board could not decode this image.\n\n{path}",
            )
            return None
        pixmap = node._pixmap
        if pixmap is not None and pixmap.width() > 0 and pixmap.height() > 0:
            iw = float(pixmap.width())
            ih = float(pixmap.height())
            scale = min(460.0 / iw, 360.0 / ih, 2.5)
            width = max(48.0, iw * scale)
            height = max(48.0, ih * scale)
            if width > 460.0 or height > 360.0:
                fit = min(460.0 / width, 360.0 / height)
                width *= fit
                height *= fit
        else:
            width, height = 340.0, 240.0
        node._width = width
        node._height = height
        position = self._position_for_node(width, height, scene_pos)
        self.scene.add_node(node, position, select=True)
        self._flash_hint(f"Added {os.path.basename(path)}")
        return node

    def _on_files_dropped(self, paths: list, scene_pos: QPointF) -> None:
        json_paths = [path for path in paths if path.lower().endswith(".json")]
        if json_paths:
            self.open_board(json_paths[0])
            return
        added = 0
        for index, path in enumerate(paths):
            offset = QPointF(scene_pos.x() + index * 26.0, scene_pos.y() + index * 22.0)
            if self.add_image_from_path(path, offset) is not None:
                added += 1
        if added == 0:
            self._flash_hint("No supported image files were dropped")

    def delete_selected(self) -> None:
        removed = self.scene.delete_selected()
        if removed:
            self._flash_hint("Selection deleted")
            self._update_counts()
            self._update_hint()

    # ---- clipboard and keyboard editing ----------------------------------

    def copy_selection(self) -> None:
        payload = self.scene.copy_selection()
        if not payload:
            self._flash_hint("Select one or more nodes to copy")
            return
        self._clipboard = payload
        self._paste_serial = 0
        count = len(payload.get("nodes", []))
        self._flash_hint(f"Copied {count} {'node' if count == 1 else 'nodes'}")

    def cut_selection(self) -> None:
        payload = self.scene.copy_selection()
        if not payload:
            self._flash_hint("Select one or more nodes to cut")
            return
        self._clipboard = payload
        self._paste_serial = 0
        count = len(payload.get("nodes", []))
        self.scene.delete_selected()
        self._flash_hint(f"Cut {count} {'node' if count == 1 else 'nodes'}")

    def paste_clipboard(self) -> None:
        if not self._clipboard:
            self._flash_hint("Nothing to paste - copy a selection first")
            return
        viewport = self.view.viewport()
        local = viewport.mapFromGlobal(QCursor.pos())
        if viewport.rect().contains(local):
            scene_pos = self.view.mapToScene(local)
            scene_pos = QPointF(
                scene_pos.x() + self._paste_serial * 14.0,
                scene_pos.y() + self._paste_serial * 14.0,
            )
            nodes = self.scene.paste_payload(self._clipboard, scene_pos=scene_pos)
        else:
            offset = QPointF(28.0 + self._paste_serial * 14.0, 28.0 + self._paste_serial * 14.0)
            nodes = self.scene.paste_payload(self._clipboard, offset=offset)
        if not nodes:
            self._flash_hint("Nothing to paste")
            return
        self._paste_serial += 1
        self._flash_hint(f"Pasted {len(nodes)} {'node' if len(nodes) == 1 else 'nodes'}")
        self.view.setFocus()

    def duplicate_selection(self) -> None:
        payload = self.scene.copy_selection()
        if not payload:
            self._flash_hint("Select one or more nodes to duplicate")
            return
        nodes = self.scene.paste_payload(payload, offset=QPointF(28.0, 28.0))
        if nodes:
            self._flash_hint(f"Duplicated {len(nodes)} {'node' if len(nodes) == 1 else 'nodes'}")
            self.view.setFocus()

    def _select_all(self) -> None:
        self.scene.clearSelection()
        for node in self.scene.nodes:
            node.setSelected(True)
        for connection in self.scene.connections:
            connection.setSelected(True)
        self.view.setFocus()

    def _nudge_selected(self, dx: float, dy: float) -> None:
        nodes = self.scene.selected_nodes()
        if not nodes:
            return
        delta = QPointF(dx, dy)
        for node in nodes:
            node.setPos(node.pos() + delta)
        self.view.setFocus()

    def _edit_selected(self) -> None:
        nodes = self.scene.selected_nodes()
        if len(nodes) != 1 or not nodes[0].SUPPORTS_TEXT or nodes[0].text_item is None:
            self._flash_hint("Select one note or shape to edit")
            return
        nodes[0].begin_editing()
        self._flash_hint("Editing text - Esc to finish")

    def show_shortcuts(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Wave Board shortcuts")
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(
            "<b>Selection</b><br>"
            "Ctrl+click: add or remove one item from the selection<br>"
            "Ctrl+A: select everything&nbsp;&nbsp; Esc: deselect or finish editing<br><br>"
            "<b>Edit</b><br>"
            "Ctrl+C / Ctrl+X / Ctrl+V: copy, cut, paste<br>"
            "Ctrl+D or Ctrl+J: duplicate selection&nbsp;&nbsp; Delete: remove selection<br>"
            "Arrow keys: nudge 1 px&nbsp;&nbsp; Shift+arrows: nudge 10 px<br>"
            "F2 or Enter: edit selected note or shape<br>"
            "Shift + corner handle: lock proportions while resizing<br><br>"
            "<b>Connections</b><br>"
            "Click a link to select it · double-click a link to remove it<br>"
            "Drag a link to detach the nearest end and drop it on another node<br>"
            "Hover a link and scroll to change its type · middle-click for thickness<br>"
            "Choose Soft, Sharp or Straight routing, weight, dash and color<br>"
            "Shift+drag a box onto a long link to snap it into the middle of the line<br>"
            "Copy Style inherits the most-used line look · Bundle fans shared ports<br><br>"
            "<b>Text</b><br>"
            "Select text while editing to change only that range's color, size, font or bold<br>"
            "With the box selected, the same controls style all of its text<br>"
            "Use the TEXT row to align, center, fit or resize text inside a box<br>"
            "Comment / caption text has no box and can never be linked<br><br>"
            "<b>Canvas</b><br>"
            "Scroll: zoom at cursor&nbsp;&nbsp; Middle-drag or Space+drag: pan<br>"
            "Ctrl+0: fit board&nbsp;&nbsp; Ctrl+1: 100%&nbsp;&nbsp; Ctrl +/-: zoom<br>"
            "Ctrl+G: toggle grid&nbsp;&nbsp; Magnet snaps nodes; hold Ctrl while moving<br>"
            "Ctrl+G grid + Magnet button align nodes to each other and the grid<br>"
            "Double-click canvas: new note<br><br>"
            "<b>File</b><br>"
            "Ctrl+N new&nbsp;&nbsp; Ctrl+O open&nbsp;&nbsp; Ctrl+S save&nbsp;&nbsp; Ctrl+Shift+S save as"
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        self.view.setFocus()

    # ---- save / open / new ------------------------------------------------

    def _default_suggested_path(self) -> str:
        if self.current_file:
            return self.current_file
        return os.path.join(self.last_dir, "Untitled Board.json")

    def save_board(self, save_as: bool = False) -> bool:
        path = self.current_file
        if save_as or not path:
            suggested = self._default_suggested_path()
            path, _ = QFileDialog.getSaveFileName(
                self, "Save board", suggested, "Wave Board (*.json);;JSON (*.json);;All files (*)"
            )
            if not path:
                return False
            if not path.lower().endswith(".json"):
                path += ".json"
        data = self.scene.to_dict(self.view)
        temporary = path + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as error:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                pass
            QMessageBox.critical(self, "Could not save board", f"{path}\n\n{error}")
            return False
        self.current_file = os.path.abspath(path)
        self.last_dir = os.path.dirname(self.current_file) or self.last_dir
        self.settings.setValue("lastDir", self.last_dir)
        self._dirty = False
        self._update_document_ui()
        self._flash_hint(f"Saved — {os.path.basename(self.current_file)}", 3200)
        return True

    def save_board_as(self) -> bool:
        return self.save_board(save_as=True)

    def open_board(self, path: Optional[str] = None) -> bool:
        if path is None:
            if not self._maybe_save_changes():
                return False
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Open board",
                self.last_dir,
                "Wave Board (*.json);;JSON files (*.json);;All files (*)",
            )
            if not path:
                return False
        else:
            if not self._maybe_save_changes():
                return False
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                data = json.load(handle)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, "Could not open board", f"{path}\n\n{error}")
            return False

        backup = self.scene.to_dict(self.view)
        backup_view = self.view.view_state()
        try:
            self.scene.load_from_dict(data)
            grid = data.get("grid", True)
            self.scene.set_grid_enabled(bool(grid), notify=False)
            self.scene.set_magnet_enabled(bool(data.get("magnet", True)), notify=False)
            self.scene.set_inherit_enabled(bool(data.get("inherit", True)), notify=False)
            self.scene.set_bundle_enabled(bool(data.get("bundle", True)), notify=False)
            self._sync_grid_button()
            self._sync_format_buttons()
            view_state = data.get("view")
            if isinstance(view_state, dict):
                self.view.restore_view_state(view_state)
            else:
                self.view.fit_content()
            self.view.update_empty_state()
        except Exception as error:
            try:
                self.scene.load_from_dict(backup)
                self.view.restore_view_state(backup_view)
                self._sync_grid_button()
                self._sync_format_buttons()
                self.view.update_empty_state()
                self._sync_properties()
                self._update_counts()
                self._update_hint()
            except Exception:
                pass
            QMessageBox.critical(self, "Could not open board", f"{path}\n\n{error}")
            return False

        self.current_file = os.path.abspath(path)
        self.last_dir = os.path.dirname(self.current_file) or self.last_dir
        self.settings.setValue("lastDir", self.last_dir)
        self._dirty = False
        self._update_document_ui()
        self._sync_properties()
        self._update_counts()
        self._update_hint()
        self._flash_hint(f"Opened — {os.path.basename(self.current_file)}", 3200)
        self.view.setFocus()
        return True

    def new_board(self) -> None:
        if not self._maybe_save_changes():
            return
        self.scene.clear_board()
        self.scene.set_grid_enabled(True, notify=False)
        self.scene.set_magnet_enabled(True, notify=False)
        self.scene.set_inherit_enabled(True, notify=False)
        self.scene.set_bundle_enabled(True, notify=False)
        self.scene.default_line_style = "thick"
        self.scene.default_line_weight = "thick"
        self.scene.default_line_dash = "solid"
        self.scene.default_line_route = "curve"
        self.scene.default_line_color = QColor(ACCENT)
        self._sync_grid_button()
        self._sync_format_buttons()
        self.current_file = None
        self._dirty = False
        self.view.reset_view()
        self.view.update_empty_state()
        self._update_document_ui()
        self._sync_properties()
        self._update_counts()
        self._update_hint()
        self._flash_hint("New board", 2000)
        self.view.setFocus()

    def _maybe_save_changes(self) -> bool:
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved changes")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"Save changes to “{self._display_name()}”?")
        box.setInformativeText("Your changes will be lost if you don't save them.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        result = box.exec()
        if result == QMessageBox.StandardButton.Save:
            return bool(self.save_board())
        if result == QMessageBox.StandardButton.Discard:
            return True
        return False

    # ---- window lifecycle -------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._dark_titlebar_applied:
            self._dark_titlebar_applied = True
            apply_dark_title_bar(self, CURRENT_THEME)

    def closeEvent(self, event) -> None:
        if not self._maybe_save_changes():
            event.ignore()
            return
        try:
            self.settings.setValue("geometry", self.saveGeometry())
            self.settings.setValue("lastDir", self.last_dir)
            self.settings.sync()
        except Exception:
            pass
        event.accept()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WaveLabs.WaveBoard.1")
        except Exception:
            pass

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(brand_icon())
    app.setStyleSheet(APP_QSS)

    window = MainWindow()
    window.show()

    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.isfile(candidate) and candidate.lower().endswith(".json"):
            QTimer.singleShot(0, lambda: window.open_board(candidate))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
