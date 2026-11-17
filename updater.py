"""In-app updater for Wave Board.

Checks a small JSON manifest on every launch (when the network is available),
downloads the new installer with progress, verifies its size/SHA-256 and then
hands it to the setup program, which replaces the installed app after Wave
Board exits.

Manifest (served from the GitHub repository, see version.json):

    {
      "version": "1.2.0",
      "download_url": "https://github.com/wave5ald/waveboard/releases/download/v1.2.0/WaveBoard-1.2.0-Setup.exe",
      "release_notes": "What changed",
      "release_page": "https://github.com/wave5ald/waveboard/releases",
      "sha256": "<lowercase hex>",
      "size_bytes": 75253581
    }
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

APP_SLUG = "WaveBoard"
MANIFEST_URL = "https://raw.githubusercontent.com/wave5ald/waveboard/main/version.json"
MANIFEST_URLS = (MANIFEST_URL,)
RELEASES_URL = "https://github.com/wave5ald/waveboard/releases"
USER_AGENT = "WaveBoard-Updater"
MAX_MANIFEST_BYTES = 512 * 1024
CHECK_INTERVAL_SECONDS = 30 * 60


class UpdateError(Exception):
    """Raised when the manifest or the download cannot be used."""


class UpdateInfo:
    def __init__(self, version: str, download_url: str, notes: str = "",
                 page: str = "", sha256: str = "", size: int = 0) -> None:
        self.version = version
        self.download_url = download_url
        self.notes = notes
        self.page = page or RELEASES_URL
        self.sha256 = sha256
        self.size = size


# --- version comparison ----------------------------------------------------

def _version_key(value: str) -> tuple[int, ...]:
    text = (value or "").strip().lstrip("vV")
    core = text.split("-", 1)[0].split("+", 1)[0]
    parts: list[int] = []
    for chunk in core.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(remote: str, current: str) -> bool:
    return _version_key(remote) > _version_key(current)


# --- network ---------------------------------------------------------------

def manifest_urls() -> tuple[str, ...]:
    """Allow a test manifest without rebuilding (used by the QA script)."""
    override = os.environ.get("WAVEBOARD_UPDATE_URL", "").strip()
    return (override,) if override else MANIFEST_URLS


def _fetch_json(target: str, timeout: int) -> dict:
    if not target.lower().startswith(("https://", "http://")):
        raise UpdateError("Update server must be an HTTP(S) URL")
    # GitHub's CDN caches raw files for a few minutes; a changing query string
    # makes every check read the freshly pushed manifest.
    separator = "&" if "?" in target else "?"
    request = urllib.request.Request(
        f"{target}{separator}v={int(time.time())}",
        headers={
            "User-Agent": USER_AGENT,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(MAX_MANIFEST_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise UpdateError(f"Update server returned HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise UpdateError(f"Could not reach the update server ({error})") from error
    if len(raw) > MAX_MANIFEST_BYTES:
        raise UpdateError("Update manifest is too large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdateError("Update manifest is not valid JSON") from error
    if not isinstance(payload, dict):
        raise UpdateError("Update manifest has an unexpected shape")
    return payload


def fetch_manifest(urls: tuple[str, ...] | None = None, timeout: int = 12) -> dict:
    """Return the newest published manifest, trying every known mirror."""
    last_error: Exception | None = None
    for target in urls or manifest_urls():
        try:
            return _fetch_json(target, timeout)
        except UpdateError as error:
            last_error = error
            continue
    raise last_error or UpdateError("No update manifest could be loaded")


def check_for_update(current_version: str, urls: tuple[str, ...] | None = None) -> UpdateInfo | None:
    data = fetch_manifest(urls)
    version = str(data.get("version", "")).strip()
    download = str(data.get("download_url", "")).strip()
    if not version:
        raise UpdateError("Update manifest has no version")
    if not is_newer(version, current_version):
        return None
    if not download.lower().startswith("https://"):
        raise UpdateError("Download link must use HTTPS")
    return UpdateInfo(
        version=version,
        download_url=download,
        notes=str(data.get("release_notes", "")).strip(),
        page=str(data.get("release_page", "")).strip(),
        sha256=str(data.get("sha256", "")).strip().lower(),
        size=int(data.get("size_bytes", 0) or 0),
    )


def installer_path(version: str) -> str:
    folder = os.path.join(tempfile.gettempdir(), APP_SLUG)
    os.makedirs(folder, exist_ok=True)
    safe = "".join(ch for ch in version if ch.isalnum() or ch in "._-") or "latest"
    return os.path.join(folder, f"WaveBoard-{safe}-Setup.exe")


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_installer(info: UpdateInfo, progress=None) -> str:
    """Download [info] to a temp file, verify it and return its path."""
    target = installer_path(info.version)
    if os.path.isfile(target) and os.path.getsize(target) > 0:
        complete = info.size <= 0 or os.path.getsize(target) == info.size
        checksum_ok = not info.sha256 or _sha256(target) == info.sha256
        if complete and checksum_ok:
            if progress:
                progress(os.path.getsize(target), os.path.getsize(target))
            return target
        try:
            os.remove(target)
        except OSError:
            pass

    request = urllib.request.Request(
        info.download_url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.HTTPError as error:
        raise UpdateError(f"Download failed with HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise UpdateError(f"Download failed ({error})") from error

    received = 0
    with response:
        total = int(response.headers.get("Content-Length") or 0) or info.size
        temporary = target + ".part"
        try:
            with open(temporary, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
            os.replace(temporary, target)
        except OSError as error:
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise UpdateError(f"Could not save the update ({error})") from error

    if info.size and received != info.size:
        _safe_remove(target)
        raise UpdateError(f"Download is incomplete ({received} of {info.size} bytes)")
    if info.sha256 and _sha256(target) != info.sha256:
        _safe_remove(target)
        raise UpdateError("Downloaded file failed the checksum check")
    return target


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def launch_installer(path: str) -> None:
    """Run the setup program in update mode so it waits for this process."""
    if not os.path.isfile(path):
        raise UpdateError("The downloaded installer is missing")
    command = [path, "--update", "--pid", str(os.getpid())]
    creation = 0
    if sys.platform == "win32":
        creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(command, close_fds=True, creationflags=creation)
    except OSError as error:
        raise UpdateError(f"Could not start the installer ({error})") from error


# --- background tasks ------------------------------------------------------

class _CheckSignals(QObject):
    available = pyqtSignal(object)
    up_to_date = pyqtSignal(str)
    failed = pyqtSignal(str)


class _CheckTask(QRunnable):
    def __init__(self, current_version: str, signals: _CheckSignals) -> None:
        super().__init__()
        self.current_version = current_version
        self.signals = signals

    def run(self) -> None:
        try:
            info = check_for_update(self.current_version)
        except UpdateError as error:
            self.signals.failed.emit(str(error))
            return
        except Exception as error:  # pragma: no cover - defensive
            self.signals.failed.emit(f"Update check failed ({error})")
            return
        if info is None:
            self.signals.up_to_date.emit(self.current_version)
        else:
            self.signals.available.emit(info)


class _DownloadSignals(QObject):
    progress = pyqtSignal(int, int)
    ready = pyqtSignal(str)
    failed = pyqtSignal(str)


class _DownloadTask(QRunnable):
    def __init__(self, info: UpdateInfo, signals: _DownloadSignals) -> None:
        super().__init__()
        self.info = info
        self.signals = signals

    def run(self) -> None:
        try:
            path = download_installer(self.info, lambda done, total: self.signals.progress.emit(done, total))
        except UpdateError as error:
            self.signals.failed.emit(str(error))
            return
        except Exception as error:  # pragma: no cover - defensive
            self.signals.failed.emit(f"Download failed ({error})")
            return
        self.signals.ready.emit(path)


class UpdateManager(QObject):
    """Coordinates checking, downloading and installing an update."""

    available = pyqtSignal(object)
    up_to_date = pyqtSignal(str)
    check_failed = pyqtSignal(str)
    progress = pyqtSignal(int, int)
    ready = pyqtSignal(str)
    download_failed = pyqtSignal(str)
    idle = pyqtSignal()

    def __init__(self, current_version: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.info: UpdateInfo | None = None
        self.busy = False
        self._last_check = 0.0
        self._check_signals = _CheckSignals(self)
        self._check_signals.available.connect(self._on_available)
        self._check_signals.up_to_date.connect(self._on_up_to_date)
        self._check_signals.failed.connect(self._on_check_failed)
        self._download_signals = _DownloadSignals(self)
        self._download_signals.progress.connect(self.progress.emit)
        self._download_signals.ready.connect(self._on_ready)
        self._download_signals.failed.connect(self._on_download_failed)

    def check(self, force: bool = False) -> None:
        if self.busy:
            return
        now = time.time()
        if not force and self._last_check and now - self._last_check < CHECK_INTERVAL_SECONDS:
            return
        self._last_check = now
        self.busy = True
        QThreadPool.globalInstance().start(_CheckTask(self.current_version, self._check_signals))

    def download_and_install(self) -> None:
        if self.busy or self.info is None:
            return
        self.busy = True
        QThreadPool.globalInstance().start(_DownloadTask(self.info, self._download_signals))

    def _on_available(self, info: UpdateInfo) -> None:
        self.busy = False
        self.info = info
        self.available.emit(info)

    def _on_up_to_date(self, version: str) -> None:
        self.busy = False
        self.info = None
        self.up_to_date.emit(version)

    def _on_check_failed(self, message: str) -> None:
        self.busy = False
        self.check_failed.emit(message)

    def _on_ready(self, path: str) -> None:
        self.busy = False
        self.ready.emit(path)


    def _on_download_failed(self, message: str) -> None:
        self.busy = False
        self.download_failed.emit(message)


# --- widgets ---------------------------------------------------------------

BANNER_QSS = """
QFrame#UpdateBanner {
    background: rgba(80, 140, 255, 0.14);
    border-bottom: 1px solid rgba(120, 165, 255, 0.35);
}
QFrame#UpdateBanner QLabel { background: transparent; }
QPushButton#UpdatePrimary {
    background: #3B82F6;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 600;
}
QPushButton#UpdatePrimary:hover { background: #2F74E0; }
QPushButton#UpdatePrimary:disabled { background: rgba(120, 150, 200, 0.45); }
QPushButton#UpdateGhost {
    background: transparent;
    color: #9DB2D0;
    border: none;
    padding: 6px 10px;
}
QPushButton#UpdateGhost:hover { color: #FFFFFF; }
QProgressBar#UpdateProgress {
    border: none;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.12);
    max-height: 6px;
}
QProgressBar#UpdateProgress::chunk { background: #3B82F6; border-radius: 3px; }
"""


class UpdateBanner(QFrame):
    """Slim strip under the header; appears only when an update exists."""

    def __init__(self, manager: UpdateManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setObjectName("UpdateBanner")
        self.setStyleSheet(BANNER_QSS)
        self.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 14, 8)
        layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        self.title = QLabel("")
        self.title.setStyleSheet("font-weight: 700;")
        self.notes = QLabel("")
        self.notes.setStyleSheet("color: #9DB2D0;")
        self.notes.setVisible(False)
        self.progress = QProgressBar()
        self.progress.setObjectName("UpdateProgress")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        text_layout.addWidget(self.title)
        text_layout.addWidget(self.notes)
        text_layout.addWidget(self.progress)
        layout.addLayout(text_layout, 1)

        self.action = QPushButton("Update")
        self.action.setObjectName("UpdatePrimary")
        self.action.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action.clicked.connect(self._start)
        layout.addWidget(self.action)

        self.later = QPushButton("Later")
        self.later.setObjectName("UpdateGhost")
        self.later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.later.clicked.connect(self.hide)
        layout.addWidget(self.later)

        manager.available.connect(self.show_available)
        manager.progress.connect(self._on_progress)
        manager.ready.connect(self._on_ready)
        manager.download_failed.connect(self._on_failed)

    def show_available(self, info: UpdateInfo) -> None:
        self.title.setText(f"Wave Board {info.version} is available")
        self.notes.setText(info.notes.splitlines()[0] if info.notes else "")
        self.notes.setVisible(bool(info.notes))
        self.notes.setToolTip(info.notes)
        self.action.setText("Update")
        self.action.setEnabled(True)
        self.later.setVisible(True)
        self.progress.setVisible(False)
        self.show()

    def _start(self) -> None:
        self.action.setEnabled(False)
        self.action.setText("Downloading…")
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.manager.download_and_install()

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            percent = max(0, min(100, int(done * 100 / total)))
            self.action.setText(f"Downloading {percent}%")
        else:
            self.progress.setRange(0, 0)
            self.action.setText("Downloading…")

    def _on_ready(self, path: str) -> None:
        self.action.setText("Restarting…")
        try:
            launch_installer(path)
        except UpdateError as error:
            self._on_failed(str(error))
            return
        QTimer.singleShot(700, _quit_app)

    def _on_failed(self, message: str) -> None:
        self.title.setText("Update could not be installed")
        self.notes.setText(message)
        self.notes.setVisible(True)
        self.action.setText("Retry")
        self.action.setEnabled(True)
        self.progress.setVisible(False)


class UpdateDialog(QDialog):
    """Manual check window: installed version, notes and progress."""

    def __init__(self, manager: UpdateManager, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Updates")
        self.setMinimumWidth(460)
        self.setStyleSheet(BANNER_QSS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(10)

        heading = QLabel("Wave Board updates")
        heading.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(heading)

        current = QLabel(f"Installed version {manager.current_version}")
        current.setStyleSheet("color: #9DB2D0;")
        layout.addWidget(current)

        self.status = QLabel("Check for a newer version whenever you are online.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.notes = QLabel("")
        self.notes.setWordWrap(True)
        self.notes.setVisible(False)
        layout.addWidget(self.notes)

        self.progress = QProgressBar()
        self.progress.setObjectName("UpdateProgress")
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("UpdateGhost")
        self.close_btn.clicked.connect(self.close)
        self.action = QPushButton("Check now")
        self.action.setObjectName("UpdatePrimary")
        self.action.clicked.connect(self._primary)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.action)
        layout.addLayout(buttons)

        manager.available.connect(self._show_available)
        manager.up_to_date.connect(self._show_current)
        manager.check_failed.connect(self._show_error)
        manager.progress.connect(self._on_progress)
        manager.ready.connect(self._on_ready)
        manager.download_failed.connect(self._show_error)
        if manager.info is not None:
            self._show_available(manager.info)

    def _primary(self) -> None:
        if self.manager.info is not None:
            self.action.setEnabled(False)
            self.action.setText("Downloading…")
            self.progress.setVisible(True)
            self.manager.download_and_install()
        else:
            self.action.setEnabled(False)
            self.status.setText("Checking for updates…")
            self.manager.check(force=True)

    def _show_available(self, info: UpdateInfo) -> None:
        self.action.setEnabled(True)
        self.action.setText("Download & install")
        self.status.setText(f"Version {info.version} is ready to install.")
        self.notes.setText(info.notes)
        self.notes.setVisible(bool(info.notes))
        self.progress.setVisible(False)

    def _show_current(self, version: str) -> None:
        self.action.setEnabled(True)
        self.action.setText("Check again")
        self.status.setText(f"You're running the latest version ({version}).")
        self.notes.setVisible(False)
        self.progress.setVisible(False)

    def _show_error(self, message: str) -> None:
        self.action.setEnabled(True)
        self.action.setText("Try again")
        self.status.setText(message)
        self.progress.setVisible(False)

    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)
            self.status.setText(f"Downloading update… {int(done * 100 / total)}%")
        else:
            self.progress.setRange(0, 0)
            self.status.setText("Downloading update…")

    def _on_ready(self, path: str) -> None:
        self.status.setText("Restarting to finish the update…")
        self.action.setEnabled(False)
        try:
            launch_installer(path)
        except UpdateError as error:
            self._show_error(str(error))
            return
        QTimer.singleShot(700, _quit_app)

    def check_now(self) -> None:
        self._primary()


def _quit_app() -> None:
    from PyQt6.QtWidgets import QApplication

    for widget in QApplication.topLevelWidgets():
        widget.close()
    QApplication.quit()
