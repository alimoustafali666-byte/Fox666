import io

import pytest
from botocore.stub import ANY, Stubber

from app.core.storage.exceptions import (
    ObjectNotFoundError,
    StorageOperationError,
    StorageUnavailable,
)
from app.core.storage.s3_provider import S3StorageProvider

SECRET_ACCESS_KEY = "super-secret-value-should-never-leak-12345"


def _make_provider() -> tuple[S3StorageProvider, Stubber]:
    provider = S3StorageProvider(
        bucket="test-bucket",
        region="me-central-1",
        endpoint_url=None,
        access_key_id="AKIA_FAKE_TEST_KEY",
        secret_access_key=SECRET_ACCESS_KEY,
        use_ssl=True,
        default_signed_url_ttl_seconds=300,
        max_signed_url_ttl_seconds=600,
    )
    stubber = Stubber(provider._client)  # deliberate white-box test access
    stubber.activate()
    return provider, stubber


# 2. S3 provider uploads using expected bucket/key
# 10. provider never creates public-read objects
def test_upload_uses_expected_bucket_key_and_never_public_acl() -> None:
    provider, stubber = _make_provider()
    stubber.add_response(
        "put_object",
        {},
        expected_params={
            "Bucket": "test-bucket",
            "Key": "companies/c1/documents/d1/original",
            "Body": ANY,
            "ACL": "private",
        },
    )

    provider.upload(key="companies/c1/documents/d1/original", data=io.BytesIO(b"hello world"))

    stubber.assert_no_pending_responses()


def test_upload_passes_through_content_type() -> None:
    provider, stubber = _make_provider()
    stubber.add_response(
        "put_object",
        {},
        expected_params={
            "Bucket": "test-bucket",
            "Key": "k",
            "Body": ANY,
            "ACL": "private",
            "ContentType": "application/pdf",
        },
    )

    provider.upload(key="k", data=io.BytesIO(b"%PDF-1.4"), content_type="application/pdf")

    stubber.assert_no_pending_responses()


# 18. existence check works through abstraction
def test_exists_true_when_head_object_succeeds() -> None:
    provider, stubber = _make_provider()
    stubber.add_response("head_object", {}, expected_params={"Bucket": "test-bucket", "Key": "k"})

    assert provider.exists(key="k") is True


def test_exists_false_on_404_not_an_exception() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "head_object", service_error_code="404", service_message="Not Found", http_status_code=404
    )

    assert provider.exists(key="missing") is False


# fetching an object's content directly (Step 9's processing pipeline)
def test_download_returns_object_content() -> None:
    provider, stubber = _make_provider()
    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(b"hello world")},
        expected_params={"Bucket": "test-bucket", "Key": "k"},
    )

    assert provider.download(key="k") == b"hello world"


def test_download_of_missing_key_raises_object_not_found() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "get_object", service_error_code="NoSuchKey", service_message="Not Found", http_status_code=404
    )

    with pytest.raises(ObjectNotFoundError):
        provider.download(key="missing")


def test_download_transient_failure_is_retried() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "get_object", service_error_code="InternalError", service_message="oops", http_status_code=500
    )
    stubber.add_response(
        "get_object",
        {"Body": io.BytesIO(b"recovered")},
        expected_params={"Bucket": "test-bucket", "Key": "k"},
    )

    assert provider.download(key="k") == b"recovered"


# 17. object delete works through abstraction
def test_delete_calls_delete_object_with_expected_params() -> None:
    provider, stubber = _make_provider()
    stubber.add_response(
        "delete_object", {}, expected_params={"Bucket": "test-bucket", "Key": "k"}
    )

    provider.delete(key="k")  # must not raise

    stubber.assert_no_pending_responses()


# 16. object-not-found maps to typed safe exception
def test_generate_download_url_raises_object_not_found_when_missing() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "head_object", service_error_code="404", service_message="Not Found", http_status_code=404
    )

    with pytest.raises(ObjectNotFoundError):
        provider.generate_download_url(key="missing")


# 9. signed download URL has bounded expiration
def test_generate_download_url_caps_requested_ttl_at_configured_maximum() -> None:
    provider, stubber = _make_provider()
    stubber.add_response("head_object", {}, expected_params={"Bucket": "test-bucket", "Key": "k"})

    url = provider.generate_download_url(key="k", expires_in_seconds=999_999)

    assert "Expires=" in url or "X-Amz-Expires=" in url
    # the maximum configured for this provider instance is 600s
    assert "X-Amz-Expires=600" in url


def test_generate_download_url_targets_only_the_requested_object() -> None:
    provider, stubber = _make_provider()
    stubber.add_response("head_object", {}, expected_params={"Bucket": "test-bucket", "Key": "k"})

    url = provider.generate_download_url(key="k")

    assert "/test-bucket/k" in url or "Key=k" in url or url.endswith("k") or "/k?" in url


# 14. transient failure retry is bounded
def test_transient_failures_are_retried_up_to_the_bounded_maximum() -> None:
    provider, stubber = _make_provider()
    # 3 failures queued; _MAX_ATTEMPTS is 3, so all 3 are consumed and the
    # call must then raise rather than retry a 4th time.
    for _ in range(3):
        stubber.add_client_error(
            "head_object",
            service_error_code="InternalError",
            service_message="oops",
            http_status_code=500,
        )

    with pytest.raises(StorageUnavailable):
        provider.exists(key="k")

    stubber.assert_no_pending_responses()  # exactly 3 were consumed, not more


def test_transient_failure_succeeds_after_a_retry() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "head_object", service_error_code="InternalError", service_message="oops", http_status_code=500
    )
    stubber.add_response("head_object", {}, expected_params={"Bucket": "test-bucket", "Key": "k"})

    assert provider.exists(key="k") is True


# 15. authorization/configuration failures are not blindly retried
def test_authorization_failure_is_not_retried() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "head_object",
        service_error_code="AccessDenied",
        service_message="Forbidden",
        http_status_code=403,
    )
    # If this were retried, the second queued response would be consumed
    # and the call would unexpectedly succeed instead of raising.
    stubber.add_response("head_object", {}, expected_params={"Bucket": "test-bucket", "Key": "k"})

    with pytest.raises(StorageOperationError):
        provider.exists(key="k")

    # the second (unused) response proves only one attempt was made
    assert stubber._queue  # white-box check that a response is still queued


# 11. storage credentials are not exposed in exceptions
def test_credentials_never_appear_in_exception_text() -> None:
    provider, stubber = _make_provider()
    stubber.add_client_error(
        "head_object",
        service_error_code="InternalError",
        service_message="oops",
        http_status_code=500,
    )
    stubber.add_client_error(
        "head_object",
        service_error_code="InternalError",
        service_message="oops",
        http_status_code=500,
    )
    stubber.add_client_error(
        "head_object",
        service_error_code="InternalError",
        service_message="oops",
        http_status_code=500,
    )

    with pytest.raises(StorageUnavailable) as excinfo:
        provider.exists(key="k")

    assert SECRET_ACCESS_KEY not in str(excinfo.value)
    assert SECRET_ACCESS_KEY not in repr(excinfo.value)


# 12. storage credentials are not logged (repr() is what a log line or
# error report would show if this object were ever printed)
def test_credentials_never_appear_in_provider_repr() -> None:
    provider, _ = _make_provider()

    text = repr(provider)

    assert SECRET_ACCESS_KEY not in text
    assert "AKIA_FAKE_TEST_KEY" not in text

