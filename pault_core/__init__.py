"""PAULT encrypted vault core package."""

from .vault import (
    VaultIntegrityError,
    VaultSession,
    create_vault,
    open_vault,
    unlock_vault,
)

__all__ = [
    "VaultIntegrityError",
    "VaultSession",
    "create_vault",
    "open_vault",
    "unlock_vault",
]
