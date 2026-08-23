"""Proves the StorageProvider abstraction is genuinely vendor-independent:
identical generic code, written only against the StorageProvider interface,
produces identical observable behavior whether it runs against the fake
in-memory provider or a (stubbed) real S3 provider. Nothing here imports
S3StorageProvider or FakeStorageProvider by name inside the shared function
-- only the abstract StorageProvider type.
"""

import io

from botocore.stub import Stubber

from app.core.storage.exceptions import ObjectNotFoundError
from app.core.storage.fake_provider import FakeStorageProvider
from app.core.storage.provider import StorageProvider
from app.core.storage.s3_provider import S3StorageProvider


# 1. vendor-independence of the abstraction
def _round_trip_through_provider(provider: StorageProvider, key: str) -> bool:
    """Generic, provider-agnostic business logic: upload an object, confirm
    it exists, fetch a download URL, delete it, and confirm it's gone.
    Written purely against the StorageProvider interface.
    """
    provider.upload(key=key, data=io.BytesIO(b"vendor independent payload"))
    assert provider.exists(key=key) is True
    assert provider.generate_download_url(key=key)
    assert provider.download(key=key) == b"vendor independent payload"

    provider.delete(key=key)
    assert provider.exists(key=key) is False

    try:
        provider.generate_download_url(key=key)
    except ObjectNotFoundError:
        return True
    return False


def test_generic_code_behaves_identically_against_the_fake_provider() -> None:
    provider: StorageProvider = FakeStorageProvider()

    assert _round_trip_through_provider(provider, "vendor-independence/fake") is True


def test_generic_code_behaves_identically_against_a_stubbed_s3_provider() -> None:
    s3_provider = S3StorageProvider(
        bucket="test-bucket",
        region="me-central-1",
        endpoint_url=None,
        access_key_id="AKIA_FAKE_TEST_KEY",
        secret_access_key="another-secret-that-must-not-leak",
        use_ssl=True,
        default_signed_url_ttl_seconds=300,
        max_signed_url_ttl_seconds=600,
    )
    stubber = Stubber(s3_provider._client)  # deliberate white-box test access
    stubber.activate()

    key = "vendor-independence/s3"
    stubber.add_response("put_object", {})
    stubber.add_response("head_object", {})  # exists() check inside the round trip
    stubber.add_response("head_object", {})  # exists() check inside generate_download_url()
    stubber.add_response(
        "get_object", {"Body": io.BytesIO(b"vendor independent payload")}
    )  # download()
    stubber.add_response("delete_object", {})
    stubber.add_client_error(
        "head_object", service_error_code="404", service_message="Not Found", http_status_code=404
    )  # exists() -> False after delete
    stubber.add_client_error(
        "head_object", service_error_code="404", service_message="Not Found", http_status_code=404
    )  # exists() check inside the final generate_download_url() call

    provider: StorageProvider = s3_provider

    assert _round_trip_through_provider(provider, key) is True
    stubber.assert_no_pending_responses()

