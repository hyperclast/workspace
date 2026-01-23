from .base import StorageBackend
from .exceptions import ObjectNotFoundError, StorageConfigError, StorageError
from .local import LocalStorageBackend
from .r2 import R2StorageBackend

_backends: dict[str, StorageBackend] = {}


def get_storage_backend(provider: str) -> StorageBackend:
    """
    Get storage backend by provider name.
    Backends are cached as singletons.
    """
    if provider not in _backends:
        if provider == "r2":
            _backends[provider] = R2StorageBackend()
        elif provider == "local":
            _backends[provider] = LocalStorageBackend()
        else:
            raise ValueError(f"Unknown storage provider: {provider}")

    return _backends[provider]


__all__ = [
    "StorageBackend",
    "R2StorageBackend",
    "LocalStorageBackend",
    "get_storage_backend",
    "StorageError",
    "ObjectNotFoundError",
    "StorageConfigError",
]
