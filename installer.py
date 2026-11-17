"""Wave Board installer.

Build output bundles the app executable as `payload/Wave Board.exe`; running the
installer copies it into the user profile, adds Start Menu / desktop shortcuts
and (optionally) launches it.

Update mode (used by the in-app updater):

    "Wave Board Setup.exe" --update --pid 1234

waits for the running app to exit, replaces the installed executable and
relaunches it without any clicks.

Uninstall:

    "Wave Board Setup.exe" --uninstall
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

APP_NAME = "Wave Board"
APP_EXE = "Wave Board.exe"
INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", APP_NAME)
VERSION = "1.2.0"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\WaveBoard"

QSS = """
QDialog { background: #0E1622; }
QLabel { color: #E7EEF9; }
QLabel#Title { font-size: 24px; font-weight: 800; }
QLabel#Subtitle, QLabel#Status { color: #9DB2D0; font-size: 12px; }
QLineEdit {
    background: #16202E; border: 1px solid #223247; border-radius: 8px;
    padding: 8px 10px; color: #E7EEF9;
}
QCheckBox { color: #E7EEF9; }
QPushButton#Primary {
    background: #2F7BFF; color: white; border: none; border-radius: 8px;
    padding: 9px 20px; font-weight: 700;
}
QPushButton#Primary:hover { background: #407BFF; }
QPushButton#Ghost {
    background: transparent; color: #B9C7DA; border: none; padding: 9px 14px;
}
"""


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for folder in (base, os.path.dirname(os.path.abspath(__file__))):
        candidate = os.path.join(folder, name)
        if os.path.isfile(candidate):
            return candidate
    return os.path.join(base, name)


def payload_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "payload", APP_EXE)


def app_path() -> str:
    return os.path.join(INSTALL_DIR, APP_EXE)


def setup_path() -> str:
    return os.path.join(INSTALL_DIR, "Wave Board Setup.exe")


def copy_self() -> None:
    """Keep a copy of the setup program next to the app for uninstall/repair."""
    if not getattr(sys, "frozen", False):
        return
    source = sys.executable
    target = setup_path()
    if os.path.abspath(source) == os.path.abspath(target):
        return
    try:
        shutil.copy2(source, target)
    except OSError:
        pass


def wait_for_process(pid: int, timeout: float = 60.0) -> None:
    """Block until [pid] exits (or the timeout expires)."""
    if pid <= 0:
        return
    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return
    try:
        milliseconds = int(timeout * 1000)
        ctypes.windll.kernel32.WaitForSingleObject(handle, milliseconds)
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
    time.sleep(0.3)


def _powershell(script: str) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        creationflags=flags,
        check=False,
    )


def create_shortcut(link_path: str, target: str) -> None:
    folder = os.path.dirname(link_path)
    os.makedirs(folder, exist_ok=True)
    script = (
        f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{link_path}");'
        f'$s.TargetPath="{target}";'
        f'$s.WorkingDirectory="{os.path.dirname(target)}";'
        f'$s.IconLocation="{target},0";'
        f'$s.Save()'
    )
    _powershell(script)


def register_uninstaller() -> None:
    uninstaller = setup_path() if os.path.isfile(setup_path()) else (
        sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    )
    script = f"""
$key = 'HKCU:\\{UNINSTALL_KEY}'
New-Item -Path $key -Force | Out-Null
Set-ItemProperty -Path $key -Name DisplayName -Value '{APP_NAME}'
Set-ItemProperty -Path $key -Name DisplayVersion -Value '{VERSION}'
Set-ItemProperty -Path $key -Name Publisher -Value 'Wave Labs'
Set-ItemProperty -Path $key -Name DisplayIcon -Value '{app_path()}'
Set-ItemProperty -Path $key -Name InstallLocation -Value '{INSTALL_DIR}'
Set-ItemProperty -Path $key -Name UninstallString -Value '"{uninstaller}" --uninstall'
Set-ItemProperty -Path $key -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -Path $key -Name NoRepair -Value 1 -Type DWord
"""
    _powershell(script)


def install() -> None:
    source = payload_path()
    if not os.path.isfile(source):
        raise RuntimeError("The bundled Wave Board executable is missing.")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    target = app_path()
    last_error: Exception | None = None
    for _ in range(40):
        try:
            shutil.copy2(source, target)
            return
        except PermissionError as error:
            last_error = error
            time.sleep(0.25)
    raise RuntimeError(f"Wave Board is still running or the file is locked. Close it and retry.\n{last_error}")


def finish_install(launch: bool) -> None:
    copy_self()
    create_shortcut(
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", f"{APP_NAME}.lnk"),
        app_path(),
    )
    register_uninstaller()
    if launch:
        subprocess.Popen([app_path()], cwd=INSTALL_DIR, close_fds=True)


def uninstall() -> None:
    for link in (
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", f"{APP_NAME}.lnk"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop", f"{APP_NAME}.lnk"),
    ):
        try:
            os.remove(link)
        except OSError:
            pass
    _powershell(f"Remove-Item -Path 'HKCU:\\{UNINSTALL_KEY}' -Recurse -Force -ErrorAction SilentlyContinue")
    shutil.rmtree(INSTALL_DIR, ignore_errors=True)
    # Remove the installer itself once it is no longer needed.
    if getattr(sys, "frozen", False):
        copy = os.path.join(tempfile.gettempdir(), "_waveboard_uninstall.bat")
        with open(copy, "w", encoding="utf-8") as handle:
            handle.write(
                "@echo off\n"
                "timeout /t 2 >nul\n"
                f'del /f /q "{sys.executable}"\n'
                f'rmdir /s /q "{INSTALL_DIR}"\n'
                'del /f /q "%~f0"\n'
            )
        subprocess.Popen(["cmd", "/c", copy], close_fds=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class InstallWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, launch: bool, parent=None) -> None:
        super().__init__(parent)
        self.launch = launch

    def run(self) -> None:
        try:
            install()
            finish_install(self.launch)
        except Exception as error:  # noqa: BLE001 - surfaced in the dialog
            self.done.emit(False, str(error))
            return
        self.done.emit(True, "")


class InstallerWindow(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Setup")
        self.setFixedSize(536, 379)
        self.setStyleSheet(QSS)
        icon_file = resource_path("icon.ico")
        if os.path.isfile(icon_file):
            self.setWindowIcon(QIcon(icon_file))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 26, 34, 22)
        layout.setSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel("Install the board to your user profile. Your boards and settings stay untouched.")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        path = QLineEdit(app_path())
        path.setReadOnly(True)
        layout.addWidget(path)

        self.launch_box = QCheckBox("Launch Wave Board after installing")
        self.launch_box.setChecked(True)
        layout.addWidget(self.launch_box)

        self.status = QLabel("Ready to install")
        self.status.setObjectName("Status")
        layout.addWidget(self.status)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("Ghost")
        self.close_btn.clicked.connect(self.reject)
        self.install_btn = QPushButton("Install")
        self.install_btn.setObjectName("Primary")
        self.install_btn.setDefault(True)
        self.install_btn.clicked.connect(self._install)
        buttons.addWidget(self.close_btn)
        buttons.addWidget(self.install_btn)
        layout.addLayout(buttons)

        self.worker: InstallWorker | None = None

    def _install(self) -> None:
        self.install_btn.setEnabled(False)
        self.close_btn.setEnabled(False)
        self.status.setText("Installing…")
        self.worker = InstallWorker(self.launch_box.isChecked(), self)
        self.worker.done.connect(self._finished)
        self.worker.start()

    def _finished(self, ok: bool, message: str) -> None:
        if ok:
            self.accept()
            return
        self.status.setText(message)
        self.install_btn.setEnabled(True)
        self.install_btn.setText("Retry")
        self.close_btn.setEnabled(True)


def main() -> int:
    args = [a.lower() for a in sys.argv[1:]]
    is_update = "--update" in args
    pid = 0
    if "--pid" in sys.argv[1:]:
        index = [a.lower() for a in sys.argv[1:]].index("--pid")
        try:
            pid = int(sys.argv[1:][index + 1])
        except (IndexError, ValueError):
            pid = 0

    if "--uninstall" in args:
        wait_for_process(pid)
        uninstall()
        return 0

    if is_update:
        # Silent: wait for the old app, replace it, relaunch it.
        wait_for_process(pid)
        try:
            install()
            finish_install(True)
        except Exception as error:  # noqa: BLE001
            ctypes.windll.user32.MessageBoxW(None, str(error), f"{APP_NAME} update", 0x10)
            return 1
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName(f"{APP_NAME} Setup")
    window = InstallerWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
