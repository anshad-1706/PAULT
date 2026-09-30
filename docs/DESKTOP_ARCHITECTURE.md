# PAULT Desktop Architecture

```text
PySide6 screens and controls
          ↓
VaultService (session lifecycle, import plans, temporary media)
          ↓
pault_core VaultSession API
          ↓
Argon2id + AES-256-GCM + atomic encrypted storage
          ↓
Selected local or removable filesystem
```

## UI

`pault_desktop/app.py` contains welcome, create, unlock, media-grid, and image-viewer experiences. `pault_desktop/gallery.py` presents responsive selectable tiles, folder/video icons, pagination, and lazy visible-image thumbnails. Thumbnails are decrypted and rendered in memory; they are not persisted. Qt worker threads run password derivation and file transfer away from the UI thread. The UI owns dialogs, confirmations, progress, drag-and-drop, and auto-lock timing. It does not implement cryptography or serialize vault metadata.

## Vault service

`pault_desktop/service.py` owns the active `VaultSession` reference, validates import plans, rejects duplicate destination paths and symbolic links, expands folder export plans without flattening, handles destination collisions, delegates transfer to the core, verifies a current password before rotation, and tracks temporary video files for removal on lock. Export is outside the encrypted vault and preserves bytes through the authenticated core export. A multi-item import/export is not one all-or-nothing transaction; a failure can leave earlier completed items committed/output.

## Core and storage

`pault_core` owns password derivation, key wrapping, encrypted metadata, virtual folder operations, streamed object encryption/decryption, file integrity checks, password rotation, and the v1 migration. New encrypted object data is staged and verified before the metadata manifest is committed. The UI never sees internal object IDs.

## Portability and lifecycle

Vault location is an absolute, user-selected path independent of the executable directory. Creation defaults to `%USERPROFILE%\PAULT\Vaults` in source/development mode and `<executable directory>\Vaults` in a frozen portable build; the user can browse elsewhere. New locations are checked for an existing vault, nested-vault placement, accessibility, write permission, and at least 1 MiB free space. The selected final destination is shown before creation.

The one-folder PyInstaller build places `PAULT.exe` and its support runtime together under `dist/PAULT/`. In a frozen build, `sys.executable` determines the executable directory for default resources and `pault.ini`; the current working directory is not used to locate vault data. The target machine does not need Python. Copy the entire output folder to USB, not only the EXE.

The UI polls for a missing `vault.json`; when unavailable, it locks the session and requires another password unlock after reconnection. Active operations are allowed to finish or fail safely before locking. Settings contain only auto-lock preferences and are written beside the portable executable (or to `~/.pault` during source development); they do not affect the vault format.

The grid uses Qt extended selection (Ctrl/Shift), clickable folder breadcrumbs, sorting, and incremental 120-item pages. It creates image thumbnails only for visible items; inputs larger than 32 MiB use a generic tile to avoid large preview reads. Thumbnail pixmaps and viewer images are discarded on lock. Video cards currently use a play-icon placeholder; video-frame extraction is not implemented.

Export defaults to `<active vault volume root>\Recovered PAULTs` (for example, `F:\Recovered PAULTs` when the active vault is on F:). This root is derived at runtime and never hardcodes a drive letter. Export supports selected files and folders, preserves folder paths, prompts before writing, and applies a batch Replace/Keep Both/Cancel policy when destination names conflict. The core authenticates and verifies file bytes while writing a temporary destination file before atomic replacement.

The official PNG is included at `pault_desktop/assets/pault_logo.png`. `logo_resource_path()` resolves it from the source root or PyInstaller bundle; the build script bundles the unchanged PNG and derives the Windows executable icon from it. Temporary video copies are created by the OS temp-file API, outside the project, vault, and application directories, and removed on lock when possible. The system player does not expose a reliable completion signal, so cleanup immediately after playback cannot be guaranteed. TODO: implement streaming video playback without full plaintext extraction. Real removable-drive, drive-letter-change, second-USB copy, and clean-host testing require Windows USB hardware/hosts and remain verification tasks.