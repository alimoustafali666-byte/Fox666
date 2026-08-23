import pytest

from app.modules.audit_log.sanitizer import UnsafeAuditMetadataError, sanitize_metadata


# 5. safe metadata survives
def test_safe_metadata_survives_unchanged() -> None:
    metadata = {"email": "user@example.com", "count": 3, "active": True, "note": None}

    assert sanitize_metadata(metadata) == metadata


def test_none_metadata_stays_none() -> None:
    assert sanitize_metadata(None) is None


def test_nested_dict_is_sanitized_recursively() -> None:
    metadata = {"details": {"file_name": "invoice.pdf", "size": 100}}

    assert sanitize_metadata(metadata) == metadata


def test_list_values_are_sanitized() -> None:
    metadata = {"tags": ["a", "b", "c"]}

    assert sanitize_metadata(metadata) == metadata


# 6 & 7. prohibited sensitive metadata is rejected / passwords cannot enter
@pytest.mark.parametrize(
    "key",
    [
        "password",
        "Password",
        "user_password",
        "password_hash",
        "PASSWORD_HASH",
    ],
)
def test_password_shaped_keys_are_rejected(key: str) -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({key: "irrelevant-value"})


# 8. raw access tokens cannot enter audit metadata
def test_access_token_key_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({"access_token": "irrelevant-value"})


def test_jwt_shaped_value_is_rejected_regardless_of_key_name() -> None:
    """A key-only blocklist can't catch a token accidentally passed under
    an innocuous key -- this is the value-shape check that closes that
    gap.
    """
    jwt_like = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.dGVzdHNpZ25hdHVyZQ"

    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({"note": jwt_like})


# 9. raw refresh tokens cannot enter audit metadata
@pytest.mark.parametrize("key", ["refresh_token", "raw_refresh_token", "token_hash"])
def test_refresh_token_shaped_keys_are_rejected(key: str) -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({key: "irrelevant-value"})


# 10. authorization/cookie values cannot enter audit metadata
@pytest.mark.parametrize(
    "key", ["authorization", "Authorization", "auth_header", "cookie", "Cookie", "session_id"]
)
def test_authorization_and_cookie_keys_are_rejected(key: str) -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({key: "irrelevant-value"})


def test_secret_and_credential_shaped_keys_are_rejected() -> None:
    for key in ("secret", "api_key", "apikey", "client_secret", "credentials", "private_key"):
        with pytest.raises(UnsafeAuditMetadataError):
            sanitize_metadata({key: "irrelevant-value"})


def test_overly_long_string_value_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({"note": "x" * 1000})


def test_too_many_keys_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({f"key_{i}": i for i in range(50)})


def test_non_dict_metadata_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata("not a dict")  # type: ignore[arg-type]


def test_unsupported_value_type_is_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({"callback": lambda: None})


def test_forbidden_key_nested_inside_a_dict_is_still_rejected() -> None:
    with pytest.raises(UnsafeAuditMetadataError):
        sanitize_metadata({"details": {"password": "leaked"}})

