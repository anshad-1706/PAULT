# Windows Platform Layer

The Windows MVP uses the PySide6 desktop application in `pault_desktop/` and the portable `pault_core` package. Vault paths are selected at runtime, so removable-drive letters are not fixed. Storage availability is polled while unlocked; Windows packaging and stronger volume-removal notifications remain future work.
