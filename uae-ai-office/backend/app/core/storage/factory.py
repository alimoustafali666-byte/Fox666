"""The only place application code should construct a StorageProvider.
Business/domain code (Documents, in Step 8) depends on get_storage_provider()
and the StorageProvider interface -- never on S3StorageProvider,
FakeStorageProvider, or boto3 directly.
"""

from app.core.config import settings
from app.core.storage.exceptions import StorageConfigurationError
from app.core.storage.fake_provider import FakeStorageProvider
from app.core.storage.provider import StorageProvider
from app.core.storage.s3_provider import S3StorageProvider

_provider: StorageProvider | None = None


def _build_s3_provider() -> S3StorageProvider:
    missing = [
        name
        for name, value in (
            ("STORAGE_BUCKET", settings.storage_bucket),
            ("STORAGE_ACCESS_KEY_ID", settings.storage_access_key_id),
            ("STORAGE_SECRET_ACCESS_KEY", settings.storage_secret_access_key),
        )
        if not value
    ]
    if missing:
        raise StorageConfigurationError(
            "Storage provider is 's3' but required configuration is missing: "
            + ", ".join(missing)
        )

    if settings.storage_endpoint_url is not None:
        scheme = settings.storage_endpoint_url.split("://", 1)[0].lower()
        if scheme not in ("http", "https"):
            # A cheap, worthwhile guard against an obviously-wrong
            # deployment config (e.g. a copy-pasted non-URL value) --
            # not a defense against a determined attacker with control
            # over environment variables, which is a trust boundary this
            # setting is already inside (same as DATABASE_URL).
            raise StorageConfigurationError(
                "STORAGE_ENDPOINT must be an http:// or https:// URL."
            )

    return S3StorageProvider(
        bucket=settings.storage_bucket,
        region=settings.storage_region,
        endpoint_url=settings.storage_endpoint_url,
        access_key_id=settings.storage_access_key_id,
        secret_access_key=settings.storage_secret_access_key,
        use_ssl=settings.storage_use_ssl,
        default_signed_url_ttl_seconds=settings.storage_signed_url_ttl_seconds,
        max_signed_url_ttl_seconds=settings.storage_max_signed_url_ttl_seconds,
    )


def _build_provider() -> StorageProvider:
    if settings.storage_provider == "s3":
        return _build_s3_provider()
    if settings.storage_provider == "fake":
        return FakeStorageProvider(
            default_signed_url_ttl_seconds=settings.storage_signed_url_ttl_seconds,
            max_signed_url_ttl_seconds=settings.storage_max_signed_url_ttl_seconds,
        )
    raise StorageConfigurationError(
        f"Unknown STORAGE_PROVIDER '{settings.storage_provider}' (expected 's3' or 'fake')."
    )


def get_storage_provider() -> StorageProvider:
    """Lazily constructs and caches a single provider instance for the
    process. Constructed on first real use, not at import/app-boot time
    -- so a deployment that never touches storage (nothing does yet;
    Step 8 is the first caller) never needs storage configured at all,
    and the failure for a misconfigured one is clear and immediate the
    first time it's actually needed rather than a confusing SDK error
    buried inside an unrelated request.
    """
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_storage_provider_cache() -> None:
    """Test-only: allows a test to change settings and force the next
    get_storage_provider() call to rebuild rather than reuse a cached
    instance from an earlier test/configuration.
    """
    global _provider
    _provider = None

