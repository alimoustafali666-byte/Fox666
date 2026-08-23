"""In-memory StorageProvider. Used by the automated test suite (so it
never needs real credentials or a running S3-compatible service) and
available as a local-dev provider (STORAGE_PROVIDER=fake) for anyone
without MinIO/S3 set up yet. Never used in production -- there is no
persistence across process restarts and no real access control.
"""

from typing import BinaryIO

from app.core.storage.exceptions import ObjectNotFoundError
from app.core.storage.provider import StorageProvider

DEFAULT_TTL_SECONDS = 300
MAX_TTL_SECONDS = 3600


class FakeStorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        default_signed_url_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_signed_url_ttl_seconds: int = MAX_TTL_SECONDS,
    ) -> None:
        self._objects: dict[str, bytes] = {}
        self._default_ttl = default_signed_url_ttl_seconds
        self._max_ttl = max_signed_url_ttl_seconds

    def upload(self, *, key: str, data: BinaryIO, content_type: str | None = None) -> None:
        self._objects[key] = data.read()

    def generate_download_url(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        if key not in self._objects:
            raise ObjectNotFoundError(f"No such object: {key}")

        ttl = expires_in_seconds if expires_in_seconds is not None else self._default_ttl
        ttl = max(1, min(ttl, self._max_ttl))
        return f"fake-storage://{key}?expires_in={ttl}"

    def download(self, *, key: str) -> bytes:
        if key not in self._objects:
            raise ObjectNotFoundError(f"No such object: {key}")
        return self._objects[key]

    def exists(self, *, key: str) -> bool:
        return key in self._objects

    def delete(self, *, key: str) -> None:
        self._objects.pop(key, None)

