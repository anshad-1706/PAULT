# PAULT Architecture

PAULT keeps the portable vault format independent from its desktop presentation:

```text
PySide6 UI
	↓
VaultService (pault_desktop)
	↓
pault_core (vault API, crypto, storage)
	↓
Encrypted metadata and chunk objects on the selected filesystem
```

`pault_desktop/app.py` owns screens, dialogs, browser interactions, and background task presentation. `pault_desktop/service.py` translates UI operations into the core API and manages the active session and PAULT-created temporary media. The UI does not implement cryptography or parse the on-disk format.

`pault_core/crypto.py` uses Argon2id and AES-256-GCM. `pault_core/storage.py` validates virtual paths and commits encrypted metadata atomically. `pault_core/vault.py` owns sessions, encrypted metadata, authenticated object chunks, folder operations, password rotation, and v1 migration.

Windows is the MVP target. The Python and Qt choices also provide a potential macOS route, but that platform is not validated by the current test environment. Mobile clients are future work.
