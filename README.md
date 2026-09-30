# PAULT

**PAULT is a portable offline encrypted vault for protecting personal files on removable storage.**

Created by **Anshad H.**, creator and original author of PAULT. PAULT was conceived and initially developed by Anshad H.

## About

PAULT is a Windows desktop application for keeping personal files such as photos, videos, documents, folders, and other files in an encrypted vault. The application can run from a USB drive. Create a vault on an accessible filesystem, or choose and unlock an existing `.pault` vault. No PAULT account, server, or cloud service is required for normal use.

```text
USB drive
	-> Run PAULT
	-> Create or open a vault
	-> Unlock with its password
	-> Work with protected files
	-> Lock PAULT
	-> Vault data remains encrypted on storage
```

## How to Use PAULT

1. Download `PAULT-v1.0.0-windows-x64.zip` from the [official PAULT GitHub Releases](https://github.com/anshad-1706/PAULT/releases) and extract it.
2. Copy the complete `PAULT` folder to a USB drive. Keep `PAULT.exe`, `_internal`, and `Vaults` together.
3. Open the folder on the USB and double-click `PAULT.exe`. The Windows x64 portable app does not need a traditional installation.
4. Choose **Create New Vault**, select a location and name, then choose **Create Vault**. Or choose **Open Existing Vault** and select your `.pault` vault folder.
5. Set a strong password, add files with **+ Add Files** or drag and drop, and organize them with **+ New Folder**.
6. Choose **Lock Vault** when finished, close PAULT, then use Windows **Safely Remove Hardware / Eject** before disconnecting the USB.

The USB drive letter can differ between computers. Vaults may be stored on the USB or another accessible location. PAULT cannot recover a forgotten vault password. Imported originals remain unchanged, while exports outside PAULT are no longer protected by the vault. See the [complete beginner-friendly User Guide](docs/USER_GUIDE.md) for details, existing-vault use, safe removal, and export instructions.

## Features

- Portable Windows one-folder application; the complete folder runs without a Python installation on the target computer.
- Offline operation with no PAULT server or cloud account.
- Password-protected vaults using Argon2id and AES-256-GCM authenticated encryption.
- Encrypted file and folder names and metadata, plus authenticated file data processed in chunks.
- Create, open, unlock, lock, and change the password for a vault.
- Import files, create and manage folders, rename and delete entries, and export selected files or folders.
- Search, sorting, extended multi-selection, image thumbnails, and an image viewer.
- Video tiles and external system-player playback.
- Manual lock, configurable inactivity auto-lock, and polling for unavailable vault storage.

Image thumbnails are generated in memory and are not cached as plaintext files. Video playback opens the system media player and currently creates a temporary plaintext copy. Exports are also plaintext copies outside the vault; the user confirms before exporting.

## Security Model

PAULT is designed for offline use. Argon2id derives password-based key material, which protects a randomly generated vault secret. AES-256-GCM authenticates and encrypts the vault secret, metadata, and file data. File data is processed in independently authenticated chunks. No cloud account or PAULT server is required for normal operation.

File and folder names are encrypted. The filesystem still exposes the vault layout, object count, approximate object sizes, and public envelope fields such as KDF parameters and timestamps.

PAULT cannot guarantee that plaintext never exists temporarily outside the vault. The operating system, memory, caches, paging, exports, and other applications may create copies. In particular, video playback uses a temporary plaintext file for external playback; cleanup is best effort and cannot guarantee forensic erasure. PAULT is not a backup system and cannot protect an unlocked vault from a compromised host.

For implementation details and limitations, see [docs/SECURITY.md](docs/SECURITY.md) and [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Portable Windows Setup

1. Download the official `PAULT-v1.0.0-windows-x64.zip` from this project's GitHub Releases.
2. Extract the ZIP.
3. Copy the complete `PAULT` folder to a USB drive.
4. Run `PAULT.exe` from that folder.
5. Create a vault or open an existing `.pault` folder, then unlock it with its password.

The portable folder must stay together:

```text
PAULT/
├── PAULT.exe
├── _internal/
└── Vaults/
```

Do not copy only `PAULT.exe`. `Vaults` is the default location for new vaults in the portable build; users may choose any accessible filesystem location. For example, `E:\PAULT\Vaults\Personal.pault` is only an example; no particular drive letter is required.

## Build and Test from Source

Python 3.11 or newer is required. From a fresh checkout:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
```

On Windows, build the one-folder application with:

```powershell
scripts\build_windows.ps1
python scripts\package_release.py
```

The build is written to `dist\PAULT\`; the release packager produces `dist\PAULT-v1.0.1-windows-x64.zip` from that built folder only. See [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for details.

## Attribution, License, and Branding

PAULT was created by Anshad H. Future contributors should be credited for their contributions; this attribution does not imply that future work was authored by the original creator. The source code is released under the GNU General Public License version 3 or later (GPL-3.0-or-later). See [AUTHORS.md](AUTHORS.md) and [LICENSE](LICENSE).

The PAULT name and logo identify the project and are separate from the software license. GPLv3 does not itself grant trademark rights or permission to imply that a modified build is an official PAULT release. See [TRADEMARKS.md](TRADEMARKS.md).

The canonical logo is [pault_desktop/assets/pault_logo.png](pault_desktop/assets/pault_logo.png).

## Security Reporting

Report suspected vulnerabilities privately using GitHub's private vulnerability reporting for this repository; do not use public issues. See [SECURITY.md](SECURITY.md). Do not include passwords, keys, vault data, or plaintext personal files in reports.
