# PAULT v1.0.0 — Initial Public Release

**Tag:** `v1.0.0`
**Artifact:** `PAULT-v1.0.0-windows-x64.zip`

## Overview

PAULT is a portable offline encrypted vault for protecting personal files on removable storage. This is the first public open-source release.

## Features

- Windows x64 portable one-folder application distributed as `PAULT-v1.0.0-windows-x64.zip`.
- Password-protected vaults using Argon2id and AES-256-GCM authenticated encryption.
- Encrypted metadata and independently authenticated file chunks.
- File import/export, virtual folders, search, sorting, multi-selection, image thumbnails and viewing, and external video playback.
- Manual locking, configurable inactivity auto-lock, password changes, and polling for unavailable vault storage.

## Security Model

PAULT is designed for offline use. Password-derived key material protects a random vault secret. AES-256-GCM authenticates encrypted metadata and file content; file data is processed in chunks. No PAULT server or cloud account is required.

Plaintext may exist temporarily in memory, operating-system caches, exports, or external applications. Video playback creates a temporary plaintext copy for the system media player, and cleanup cannot guarantee forensic erasure. See [SECURITY.md](SECURITY.md) and [THREAT_MODEL.md](THREAT_MODEL.md).

## Known Limitations

- The desktop release targets Windows x64; macOS and Linux are not supported release targets.
- Video playback uses an external system player and a temporary plaintext file.
- Exports are plaintext copies outside the vault, and memory or operating-system copies cannot be reliably erased by PAULT.
- Storage availability is polled, so removable-drive detection is not guaranteed to be immediate.
- PAULT is not a backup system; users should maintain independent backups.

## Platform and Installation

The release artifact targets Windows x64. Extract the ZIP, copy the complete `PAULT` folder to removable storage, and run `PAULT.exe`. Keep `_internal` and `Vaults` alongside the executable; do not copy only the EXE. Create or open a vault at any accessible filesystem location.

## Source and License

The source code is released under the GNU General Public License version 3 or later (GPL-3.0-or-later). PAULT was created by Anshad H.; see [AUTHORS.md](../AUTHORS.md). The PAULT name and logo are project branding, separate from the software license; see [TRADEMARKS.md](../TRADEMARKS.md).