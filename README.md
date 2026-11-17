# Wave Board

An infinite visual canvas for Windows: notes, comments, shapes and images on a
zoomable board, built with PyQt6.

- **Infinite canvas** - pan, zoom, grid, snapping and alignment guides.
- **Notes & comments** - styled text, sticky notes, colours and sizes.
- **Shapes & images** - rectangles, squares, images with resizing handles.
- **Boards as JSON** - save, open and share boards; autosave-friendly format.
- **Themes** - presets plus custom accent and canvas colours.
- **Built-in updates** - the app checks for a new version on launch and
  installs it with one click (see [Updates](#updates)).

## Requirements

- Windows 10/11
- Python 3.12+ with PyQt6 (`pip install -r requirements.txt`)

## Run from source

```powershell
python main.py
```

## Build

```powershell
.\build.ps1                 # builds the app and the installer
.\build.ps1 -Version 1.3.0  # optional: stamp a different version
```

Outputs:

| File | What it is |
| --- | --- |
| `dist\Wave Board.exe` | portable single-file app |
| `dist\Wave Board Setup.exe` | installer used by new users and by the updater |
| `dist\WaveBoard-<version>-Setup.exe` | copy of the installer named for GitHub Releases |

The build script prints the manifest entry (version, size, SHA-256) that the
release needs.

## Install layout

The installer copies the app to `%LOCALAPPDATA%\Programs\Wave Board`, adds a
Start Menu shortcut and registers itself in *Apps & features*. Boards and
settings live in `%APPDATA%\Wave Labs\Wave Board` and are never touched by an
update.

Uninstall from *Apps & features*, or run the installer with:

```powershell
& "$env:LOCALAPPDATA\Programs\Wave Board\Wave Board Setup.exe" --uninstall
```

## Updates

`updater.py` runs a check 2.5 seconds after launch (and every 6 hours) against
a small JSON manifest. When a newer version is published the app shows a
banner with the release notes and an **Update** button:

1. The installer is downloaded to `%TEMP%\WaveBoard`.
2. Its size and SHA-256 are compared with the manifest.
3. The installer runs in `--update` mode, waits for Wave Board to exit,
   replaces the app and relaunches it.

Offline or server errors are silent on launch - open **Updates** in the header
to check manually and see the reason.

### Manifest

The app reads `version.json` from this repository:

`https://raw.githubusercontent.com/wave5ald/waveboard/main/version.json`

```json
{
  "version": "1.2.0",
  "download_url": "https://github.com/wave5ald/waveboard/releases/download/v1.2.0/WaveBoard-1.2.0-Setup.exe",
  "release_notes": "In-app updates and smaller downloads",
  "release_page": "https://github.com/wave5ald/waveboard/releases",
  "sha256": "<lowercase hex digest>",
  "size_bytes": 75253581
}
```

Every check appends a changing `?v=<timestamp>` to the URL, so GitHub's raw
cache never serves an old manifest.

### Publishing a release

1. Bump `APP_VERSION` in `main.py` and `VERSION` in `installer.py` (or let
   `.\build.ps1 -Version 1.3.0` do it).
2. Run `.\build.ps1 -WriteManifest` - it rebuilds the app and installer,
   refreshes `version.json` with the new size and SHA-256, and prints the entry.
3. Create a release tagged `v<version>` and upload
   `dist\WaveBoard-<version>-Setup.exe` to it.
4. Commit and push `version.json` to `main`.

Installed apps see the new version on their next launch or manual check.

## Repository

<https://github.com/wave5ald/waveboard>
