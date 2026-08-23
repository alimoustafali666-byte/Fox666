import uuid

import pytest

from app.core.storage.exceptions import InvalidObjectKeyError
from app.core.storage.keys import build_document_object_key


# 3. object keys are company namespaced
# 4. object keys are document namespaced
def test_key_is_namespaced_by_company_and_document() -> None:
    company_id = uuid.uuid4()
    document_id = uuid.uuid4()

    key = build_document_object_key(company_id=company_id, document_id=document_id)

    assert key == f"companies/{company_id}/documents/{document_id}/original"


def test_different_companies_get_different_namespaces_for_the_same_document_id() -> None:
    """A duplicate document_id across two companies (not realistic given
    how document ids are generated, but the key builder itself must not
    rely on document_id uniqueness for isolation) still produces disjoint
    keys because company_id is part of the path.
    """
    document_id = uuid.uuid4()
    key_a = build_document_object_key(company_id=uuid.uuid4(), document_id=document_id)
    key_b = build_document_object_key(company_id=uuid.uuid4(), document_id=document_id)

    assert key_a != key_b


# 5. raw filename cannot cause path traversal
@pytest.mark.parametrize(
    "malicious_name",
    [
        "invoice.pdf",  # a plain, everyday filename must ALSO be rejected --
        # object_name is not a filename field, it's an internal
        # discriminator; real filenames belong in Postgres metadata only.
        "my document (final).pdf",
        "résumé.pdf",
    ],
)
def test_raw_filenames_are_rejected_as_object_name(malicious_name: str) -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name=malicious_name
        )


# 6. ../ sequences cannot escape namespace
@pytest.mark.parametrize(
    "traversal",
    [
        "../../../etc/passwd",
        "..%2f..%2fetc%2fpasswd",
        "....//....//etc/passwd",
        "original/../../../other-company",
    ],
)
def test_dot_dot_sequences_cannot_escape_the_namespace(traversal: str) -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name=traversal
        )


# 7. absolute-path-like filenames cannot escape namespace
@pytest.mark.parametrize("absolute", ["/etc/passwd", "\\etc\\passwd", "//etc/passwd", "C:\\Windows\\System32"])
def test_absolute_path_like_names_cannot_escape_the_namespace(absolute: str) -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name=absolute
        )


# 8. unusual Unicode filenames cannot alter namespace
@pytest.mark.parametrize(
    "unicode_name",
    [
        "\u2024\u2024/etc/passwd",  # one-dot-leader lookalikes
        "\uff0e\uff0e\uff0fetc",  # fullwidth '..' + fullwidth slash
        "orig\u0000inal",  # embedded NUL
        "origin\u200bal",  # zero-width space
        "😀document",
    ],
)
def test_unusual_unicode_names_cannot_alter_the_namespace(unicode_name: str) -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name=unicode_name
        )


def test_safe_default_object_name_is_accepted() -> None:
    key = build_document_object_key(company_id=uuid.uuid4(), document_id=uuid.uuid4())
    assert key.endswith("/original")


def test_safe_custom_object_name_is_accepted() -> None:
    key = build_document_object_key(
        company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name="thumbnail-1"
    )
    assert key.endswith("/thumbnail-1")


def test_company_id_must_be_a_real_uuid_instance_not_a_string() -> None:
    """The structural defense: even a string that *looks* like a safe id
    is rejected, because the field must be an actual uuid.UUID -- there
    is no code path where a raw string (however it was validated
    upstream) can reach the key format string.
    """
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id="not-a-uuid-object",  # type: ignore[arg-type]
            document_id=uuid.uuid4(),
        )


def test_document_id_must_be_a_real_uuid_instance_not_a_string() -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id=uuid.uuid4(),
            document_id="../../other-company",  # type: ignore[arg-type]
        )


def test_empty_object_name_is_rejected() -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name="")


def test_overly_long_object_name_is_rejected() -> None:
    with pytest.raises(InvalidObjectKeyError):
        build_document_object_key(
            company_id=uuid.uuid4(), document_id=uuid.uuid4(), object_name="x" * 65
        )

