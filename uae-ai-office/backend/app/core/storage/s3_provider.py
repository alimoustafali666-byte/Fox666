"""S3-compatible StorageProvider. Works against real AWS S3 or any
S3-API-compatible service (MinIO, etc.) purely via configuration --
nothing here is AWS-specific beyond the boto3 client itself, which
speaks the S3 API generically.
"""

import time
from collections.abc import Callable
from typing import BinaryIO, TypeVar

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.core.storage.exceptions import (
    ObjectNotFoundError,
    StorageOperationError,
    StorageUnavailable,
)
from app.core.storage.provider import StorageProvider

_T = TypeVar("_T")

_MAX_ATTEMPTS = 3
_BASE_RETRY_DELAY_SECONDS = 0.2

# Codes/statuses worth one more try -- connectivity blips and the
# service's own "back off and retry" signals. Never a 4xx: an
# authorization or malformed-request failure will fail identically on a
# retry, so retrying it only adds latency and noise, never a different
# outcome.
_TRANSIENT_CLIENT_ERROR_CODES = {"SlowDown", "RequestTimeout", "InternalError", "ServiceUnavailable"}
_NOT_FOUND_CODES = {"404", "NoSuchKey", "NotFound"}


def _is_transient_client_error(exc: ClientError) -> bool:
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    code = exc.response.get("Error", {}).get("Code", "")
    return status >= 500 or code in _TRANSIENT_CLIENT_ERROR_CODES


def _is_not_found_error(exc: ClientError) -> bool:
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
    code = exc.response.get("Error", {}).get("Code", "")
    return status == 404 or code in _NOT_FOUND_CODES


class S3StorageProvider(StorageProvider):
    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        use_ssl: bool,
        default_signed_url_ttl_seconds: int,
        max_signed_url_ttl_seconds: int,
    ) -> None:
        self._bucket = bucket
        self._default_ttl = default_signed_url_ttl_seconds
        self._max_ttl = max_signed_url_ttl_seconds
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            use_ssl=use_ssl,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=BotoConfig(signature_version="s3v4"),
        )

    def __repr__(self) -> str:
        # Deliberately excludes access_key_id/secret_access_key/endpoint
        # credentials-adjacent detail -- this is what would end up in a
        # log line or an error report if this object were ever printed,
        # so it must never be able to leak them.
        return f"S3StorageProvider(bucket={self._bucket!r})"

    def _call_with_retry(self, fn: Callable[[], _T]) -> _T:
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return fn()
            except ClientError as exc:
                if not _is_transient_client_error(exc):
                    raise  # not transient: fail on the first attempt, never retry
                last_exc = exc
            except BotoCoreError as exc:
                # Connection/timeout-shaped failures -- always transient
                # by nature.
                last_exc = exc

            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_BASE_RETRY_DELAY_SECONDS * (2**attempt))

        raise StorageUnavailable("Storage backend is temporarily unavailable.") from last_exc

    def upload(self, *, key: str, data: BinaryIO, content_type: str | None = None) -> None:
        # put_object (a single synchronous PutObject call) is used rather
        # than upload_fileobj: the latter delegates to s3transfer's own
        # threaded TransferManager, which does its own internal retry
        # handling and multipart-eligibility probing -- both wrong fits
        # here. It bypasses our bounded _call_with_retry entirely, and at
        # our enforced 25MB/file ceiling (Step 8) there is no benefit to
        # multipart upload. put_object still streams the body rather than
        # requiring it be materialized as an in-memory bytes object ahead
        # of time.
        kwargs: dict[str, object] = {"Bucket": self._bucket, "Key": key, "Body": data, "ACL": "private"}
        if content_type:
            kwargs["ContentType"] = content_type

        try:
            self._call_with_retry(lambda: self._client.put_object(**kwargs))
        except StorageUnavailable:
            raise
        except ClientError as exc:
            raise StorageOperationError("Failed to upload object.") from exc

    def generate_download_url(self, *, key: str, expires_in_seconds: int | None = None) -> str:
        if not self.exists(key=key):
            raise ObjectNotFoundError(f"No such object: {key}")

        ttl = expires_in_seconds if expires_in_seconds is not None else self._default_ttl
        ttl = max(1, min(ttl, self._max_ttl))

        try:
            return self._client.generate_presigned_url(
                "get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=ttl
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageOperationError("Failed to generate a download URL.") from exc

    def download(self, *, key: str) -> bytes:
        def _get() -> bytes:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return response["Body"].read()

        try:
            return self._call_with_retry(_get)
        except StorageUnavailable:
            raise
        except ClientError as exc:
            if _is_not_found_error(exc):
                raise ObjectNotFoundError(f"No such object: {key}") from exc
            raise StorageOperationError("Failed to download object.") from exc

    def exists(self, *, key: str) -> bool:
        try:
            self._call_with_retry(lambda: self._client.head_object(Bucket=self._bucket, Key=key))
            return True
        except StorageUnavailable:
            raise
        except ClientError as exc:
            if _is_not_found_error(exc):
                return False
            raise StorageOperationError("Failed to check object existence.") from exc

    def delete(self, *, key: str) -> None:
        try:
            self._call_with_retry(lambda: self._client.delete_object(Bucket=self._bucket, Key=key))
        except StorageUnavailable:
            raise
        except ClientError as exc:
            # delete_object is idempotent in the S3 API itself (a missing
            # key is not an error at that layer), so any ClientError
            # reaching here is a real operational failure, not "already
            # gone".
            raise StorageOperationError("Failed to delete object.") from exc

