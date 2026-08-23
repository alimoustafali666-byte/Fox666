"""The abstraction every future module (Documents in Step 8, and
whatever needs object storage after it) depends on. Business/domain code
must never import boto3, a vendor SDK, or a specific provider directly --
only this interface and the factory that resolves it from configuration
(app.core.storage.factory.get_storage_provider).
"""

from abc import ABC, abstractmethod
from typing import BinaryIO


class StorageProvider(ABC):
    @abstractmethod
    def upload(self, *, key: str, data: BinaryIO, content_type: str | None = None) -> None:
        """Uploads `data` (a file-like object opened for binary reading --
        never a fully-materialized bytes blob) to `key`. Always private;
        no implementation may create a publicly readable object.
        """

    @abstractmethod
    def generate_download_url(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        """A short-lived, signed URL for downloading `key`. Raises
        ObjectNotFoundError if the object doesn't exist -- this method
        never hands back a URL for something that isn't there.
        `expires_in_seconds`, when given, is still bounded by the
        provider's configured maximum; callers cannot request an
        arbitrarily long-lived URL.
        """

    @abstractmethod
    def download(self, *, key: str) -> bytes:
        """Fetches `key`'s full object content directly from the private
        backing store -- the only sanctioned way for internal code (the
        Step 9 processing pipeline) to read a document's bytes back.
        Never via generate_download_url() plus an HTTP fetch: that would
        route through a signed URL meant for external callers and, for
        the real S3 provider, an unnecessary network hop through the
        public internet for what is otherwise a same-infrastructure
        read. Raises ObjectNotFoundError if the object doesn't exist.
        Returns the full content as bytes -- documents are already
        capped (25MB) well before this is ever called, so this is a
        bounded, not unbounded, in-memory read.
        """

    @abstractmethod
    def exists(self, *, key: str) -> bool:
        """True/False for "does this object exist" -- never raises for
        the not-found case itself, only for a genuine failure to check
        (connectivity, auth).
        """

    @abstractmethod
    def delete(self, *, key: str) -> None:
        """Idempotent: deleting an already-absent key is not an error,
        matching real S3 DELETE semantics.
        """

