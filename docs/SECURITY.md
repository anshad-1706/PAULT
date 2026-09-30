# PAULT Security Documentation

## Cryptographic primitives

- Argon2id key derivation: 16-byte random salt, 64 MiB memory cost, three iterations, one lane, 32-byte output by default.
- AES-256-GCM for the wrapped vault secret, encrypted metadata, and each file chunk.
- Nonces are generated using Python's operating-system-backed `os.urandom()`.

File chunks are independently authenticated with associated data containing the vault ID, random object ID, and chunk index. The encrypted manifest records the object mapping, file name, size, SHA-256 digest, and modified time. SHA-256 is an integrity cross-check; authenticity comes from AES-GCM.

## Safety principles

- Passwords and encryption keys are never intentionally written to disk or logs.
- No master password, recovery backdoor, network service, telemetry, or analytics is present.
- File data is staged as ciphertext and authenticated before the encrypted manifest is atomically updated.
- Incorrect passwords and authenticated-data failures do not return vault contents.

## Known limitations

Python immutable bytes and interpreter/runtime copies prevent reliable zeroization. A locked vault cannot protect data from a compromised active host. Visible photo thumbnails and the active image viewer hold decrypted/decoded image data in process memory only; thumbnail generation is lazy and no plaintext thumbnail cache is written to disk. Lock and storage-unavailable handling clear UI references, but cannot guarantee memory erasure. Video playback exports a temporary plaintext file for the default media player; PAULT removes its temporary copy when locking, but the OS, player, paging file, backups, or forensic tools may preserve traces.

Exports are intentionally plaintext copies outside PAULT. The user confirms before export and chooses Replace, Keep Both, or Cancel for name conflicts. Export streams authenticated chunks to a temporary file beside the destination, verifies integrity, then atomically commits the output. Exported copies are not deleted automatically.

USB removal is polled by the desktop UI and storage failures invalidate the session when detected. Polling cannot guarantee immediate detection, and a write interrupted by physical removal may leave an encrypted orphan object. The last committed encrypted manifest remains the recovery point when filesystem atomic replacement behaves as expected.

Portable-build configuration contains only UI preferences such as auto-lock duration. It is stored beside the executable when frozen and never contains vault passwords, keys, or vault metadata. Video plaintext is created only on playback in the OS temporary directory, outside the vault and portable application tree; cleanup is best effort because the system player may keep handles and the OS may retain traces.

## Locking behavior

Lock waits for an active operation to finish, drops the session references, clears metadata references, and removes PAULT-created temporary video files. It cannot guarantee physical erasure of memory or OS-managed storage.
