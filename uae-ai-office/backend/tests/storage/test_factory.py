import pytest

from app.core.config import settings
from app.core.storage import factory
from app.core.storage.exceptions import StorageConfigurationError
from app.core.storage.fake_provider import FakeStorageProvider
from app.core.storage.s3_provider import S3StorageProvider


@pytest.fixture(autouse=True)
def _reset_provider_cache():
    factory.reset_storage_provider_cache()
    yield
    factory.reset_storage_provider_cache()


# 13. missing required configuration fails safely
def test_s3_provider_with_no_config_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "storage_bucket", None)
    monkeypatch.setattr(settings, "storage_access_key_id", None)
    monkeypatch.setattr(settings, "storage_secret_access_key", None)

    with pytest.raises(StorageConfigurationError) as excinfo:
        factory.get_storage_provider()

    assert "STORAGE_BUCKET" in str(excinfo.value)
    assert "STORAGE_ACCESS_KEY_ID" in str(excinfo.value)
    assert "STORAGE_SECRET_ACCESS_KEY" in str(excinfo.value)


def test_s3_provider_with_partial_config_reports_only_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "storage_bucket", "a-real-bucket")
    monkeypatch.setattr(settings, "storage_access_key_id", None)
    monkeypatch.setattr(settings, "storage_secret_access_key", "a-real-secret")

    with pytest.raises(StorageConfigurationError) as excinfo:
        factory.get_storage_provider()

    message = str(excinfo.value)
    assert "STORAGE_ACCESS_KEY_ID" in message
    assert "STORAGE_BUCKET" not in message
    assert "STORAGE_SECRET_ACCESS_KEY" not in message
    # never echo the secret itself back, even a valid-looking one
    assert "a-real-secret" not in message


def test_s3_provider_rejects_a_non_http_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "storage_bucket", "a-real-bucket")
    monkeypatch.setattr(settings, "storage_access_key_id", "AKIA_FAKE")
    monkeypatch.setattr(settings, "storage_secret_access_key", "a-real-secret")
    monkeypatch.setattr(settings, "storage_endpoint_url", "ftp://not-http.example.com")

    with pytest.raises(StorageConfigurationError):
        factory.get_storage_provider()


def test_s3_provider_with_full_config_builds_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "storage_bucket", "a-real-bucket")
    monkeypatch.setattr(settings, "storage_access_key_id", "AKIA_FAKE")
    monkeypatch.setattr(settings, "storage_secret_access_key", "a-real-secret")
    monkeypatch.setattr(settings, "storage_endpoint_url", None)

    provider = factory.get_storage_provider()

    assert isinstance(provider, S3StorageProvider)


def test_fake_provider_selection_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "fake")
    monkeypatch.setattr(settings, "storage_bucket", None)
    monkeypatch.setattr(settings, "storage_access_key_id", None)
    monkeypatch.setattr(settings, "storage_secret_access_key", None)

    provider = factory.get_storage_provider()

    assert isinstance(provider, FakeStorageProvider)


def test_unknown_provider_name_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "azure-blob")

    with pytest.raises(StorageConfigurationError):
        factory.get_storage_provider()


def test_get_storage_provider_caches_the_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_provider", "fake")

    first = factory.get_storage_provider()
    second = factory.get_storage_provider()

    assert first is second

