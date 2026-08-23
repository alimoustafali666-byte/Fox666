import io

import pytest

from app.core.storage.exceptions import ObjectNotFoundError
from app.core.storage.fake_provider import FakeStorageProvider


def test_upload_then_exists() -> None:
    provider = FakeStorageProvider()

    provider.upload(key="a/b/c", data=io.BytesIO(b"hello"))

    assert provider.exists(key="a/b/c") is True


def test_exists_is_false_for_unknown_key() -> None:
    provider = FakeStorageProvider()

    assert provider.exists(key="never-uploaded") is False


def test_download_returns_uploaded_content() -> None:
    provider = FakeStorageProvider()
    provider.upload(key="a/b/c", data=io.BytesIO(b"hello world"))

    assert provider.download(key="a/b/c") == b"hello world"


def test_download_of_missing_key_raises_object_not_found() -> None:
    provider = FakeStorageProvider()

    with pytest.raises(ObjectNotFoundError):
        provider.download(key="never-uploaded")


# 17. object delete works through abstraction
def test_delete_removes_the_object() -> None:
    provider = FakeStorageProvider()
    provider.upload(key="a/b/c", data=io.BytesIO(b"hello"))

    provider.delete(key="a/b/c")

    assert provider.exists(key="a/b/c") is False


def test_delete_of_missing_key_is_not_an_error() -> None:
    provider = FakeStorageProvider()

    provider.delete(key="never-existed")  # must not raise


# 16. object-not-found maps to typed safe exception
def test_generate_download_url_for_missing_key_raises_typed_error() -> None:
    provider = FakeStorageProvider()

    with pytest.raises(ObjectNotFoundError):
        provider.generate_download_url(key="never-uploaded")


def test_generate_download_url_for_existing_key_succeeds() -> None:
    provider = FakeStorageProvider()
    provider.upload(key="a/b/c", data=io.BytesIO(b"hello"))

    url = provider.generate_download_url(key="a/b/c")

    assert "a/b/c" in url


# 9. signed download URL has bounded expiration
def test_requested_ttl_is_capped_at_the_configured_maximum() -> None:
    provider = FakeStorageProvider(default_signed_url_ttl_seconds=300, max_signed_url_ttl_seconds=600)
    provider.upload(key="a/b/c", data=io.BytesIO(b"hello"))

    url = provider.generate_download_url(key="a/b/c", expires_in_seconds=999_999)

    assert "expires_in=600" in url


def test_default_ttl_is_used_when_not_specified() -> None:
    provider = FakeStorageProvider(default_signed_url_ttl_seconds=300, max_signed_url_ttl_seconds=600)
    provider.upload(key="a/b/c", data=io.BytesIO(b"hello"))

    url = provider.generate_download_url(key="a/b/c")

    assert "expires_in=300" in url

