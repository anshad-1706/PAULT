# PAULT Vault Format v2

## Layout

```text
MyVault.pault/
  vault.json                 # public envelope plus encrypted metadata
  objects/
    <random-id>.paultobj     # authenticated encrypted chunk stream
```

## Envelope

The JSON envelope contains `vault_version` (2), a random vault ID, the Argon2id salt and parameters, wrapped vault-secret nonce/ciphertext, encrypted-entry nonce/ciphertext, and timestamps. Names and virtual paths exist only inside the encrypted entries payload. Each file record stores a random object ID, byte size, SHA-256 digest, and modified timestamp. Folder names and entries are encrypted with the same metadata payload.

The password derives a 32-byte key with Argon2id (64 MiB, three iterations, one lane by default). AES-256-GCM wraps a random 32-byte vault secret. A second AES-256-GCM operation encrypts serialized metadata with that secret.

## Object stream

Each object starts with the 9-byte ASCII identifier `PAULTOBJ2` followed by LF (10 bytes total). It contains repeated records:

```text
4-byte unsigned big-endian ciphertext length
12-byte nonce
ciphertext (plaintext chunk plus 16-byte GCM tag)
```

Plaintext chunks are at most 1 MiB. A four-byte zero length ends the stream. Empty files contain the header and terminator only. The associated data for chunk index `i` is the UTF-8/ASCII byte sequence `vault_id:object_id:i`. Each chunk is independently authenticated. The reader checks framing, authentication, total size, and the manifest SHA-256 digest while streaming.

## Commit and recovery

Import writes a uniquely named temporary object, flushes it, verifies it by decrypting and hashing the staged ciphertext, atomically renames it into `objects/`, then atomically replaces `vault.json`. The encrypted object is durable before the manifest points to it. If manifest commit fails, the previous manifest remains valid; an unreferenced encrypted object may remain. Delete commits the updated manifest before removing object data. Filesystem/device failure guarantees depend on the volume's atomic rename and flush semantics.

## Version 1

Version 1 stored base64 file chunks inside the encrypted JSON metadata document. It remains readable; after successful authentication, unlock streams its legacy chunks into v2 objects and atomically commits a v2 manifest. Keep a backup before opening an irreplaceable legacy vault with a new build.
