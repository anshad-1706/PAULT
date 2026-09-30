# PAULT Threat Model

## Protected against

- Offline inspection of file contents, names, and folder metadata without the vault password.
- Offline password guessing is made more expensive with Argon2id.
- Unauthorized modification, truncation, or reordering of file chunks is detected by AES-GCM authentication and stored size/digest checks.
- A wrong password does not unlock metadata or file contents.

## Exposed information

The filesystem layout and object count are visible. Individual object sizes approximate plaintext sizes plus per-chunk overhead. The outer JSON exposes vault ID, KDF parameters, salt, version, and timestamps. File names and folder names are encrypted.

## Not guaranteed against

- Malware, keyloggers, screen capture, or memory inspection on the active host.
- Physical compromise of the USB device or compromised storage firmware.
- Forensic recovery of RAM, temporary video copies, OS caches, swap/page files, or media-player artifacts.
- Concurrent hostile writes or filesystem behavior that violates atomic rename/fsync assumptions.
- Data loss from physical media failure. PAULT is not a backup system.

## Assumptions

PAULT targets offline inspection of a locked removable drive. The host is not assumed trustworthy while the vault is unlocked. Users must keep independent backups and understand that exported files leave the vault's protection.
