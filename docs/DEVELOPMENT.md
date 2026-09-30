# PAULT Development Guide

## Development setup

Python 3.11 or newer is required. On Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Run the desktop app with `pault` or `python -m pault_desktop.app`. Run unit tests with `python -m pytest -q`.

## Repository layout

- `pault_core/` contains the portable encrypted vault implementation.
- `pault_desktop/` contains the PySide6 desktop interface and service boundary.
- `tests/unit/` contains core and service tests.
- `docs/` contains format, architecture, security, threat model, and development notes.

## Current status

The desktop MVP supports create/open/unlock, a responsive multi-select media grid, folder navigation, lazy in-memory image thumbnails, image viewer, video placeholders/external playback, import (including drag/drop), rename, delete, and batch/folder export. Export defaults to `Recovered PAULTs` at the active vault volume root and offers Replace/Keep Both/Cancel for collisions. File import/export is streamed in authenticated chunks. Video playback temporarily extracts a plaintext copy. See [DESKTOP_ARCHITECTURE.md](DESKTOP_ARCHITECTURE.md), [SECURITY.md](SECURITY.md), and [VAULT_FORMAT.md](VAULT_FORMAT.md).

No linter or type checker is configured in `pyproject.toml`; do not treat a successful test run as a substitute for a security review.

## Build the portable Windows application

Use a Windows development machine with Python 3.11 or newer and network access for the one-time build dependency installation. From the repository root, run:

```powershell
scripts\build_windows.ps1
```

The script installs the `portable-build` extra and runs PyInstaller in **one-folder** mode. Qt, the Python runtime, Argon2 native support, and cryptography dependencies are bundled in `dist\PAULT\` (including PyInstaller's support subdirectory). No target-machine Python installation or project checkout is needed. The build is Windows-specific; build it on Windows.

To produce the GitHub release archive from the completed build, run `python scripts\package_release.py`. It packages only `dist\PAULT\` as `dist\PAULT-v<project-version>-windows-x64.zip` (currently `dist\PAULT-v1.0.1-windows-x64.zip`), checks for a vault in the release Vaults folder, and verifies the expected executable, support directory, and logo entries.

The UI loads the included official logo from `pault_desktop\assets\pault_logo.png` using a source/frozen-aware resource resolver. The build script bundles the byte-identical PNG and derives a Windows `.ico` for the executable.

Copy the complete `dist\PAULT\` directory to the USB, for example `E:\PAULT\`. Keep its support files beside `PAULT.exe`; do not copy only the executable. The build includes `Vaults\` as a convenient default. Start `PAULT.exe` from Explorer; its behavior does not depend on the working directory. The portable app stores non-sensitive UI settings in `PAULT\pault.ini` when that directory is writable.

In PAULT, select **Create New Vault**, enter a name such as `Personal`, and browse to `E:\PAULT\Vaults`. Confirm the displayed absolute destination before entering the password and acknowledging the no-recovery warning. A vault can instead be created on any other accessible drive. To open an existing vault, browse to and select its `.pault` folder. Vault data is not stored relative to the source repository or inferred from the process working directory.

## Portable build dependencies

PyInstaller one-folder mode is chosen over one-file mode for more predictable PySide6 plugin and native-library loading, easier support-file inspection, and less runtime extraction. Qt image plugins are bundled; HEIC decoding still depends on plugin support. Image thumbnails are generated only for visible grid items, scaled with `QImageReader`, limited to source images no larger than 32 MiB, held only in process memory, and discarded on lock. Video cards currently show a play placeholder rather than decoded frames. Video playback uses the system media player and a temporary plaintext file; TODO: implement streaming playback without full extraction. No installer, online activation, telemetry, or cloud component is part of this build.
