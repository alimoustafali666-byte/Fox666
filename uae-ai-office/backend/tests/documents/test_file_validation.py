import hashlib
import io

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.documents.helpers import (
    EXECUTABLE_BYTES,
    HTML_BYTES,
    JPEG_BYTES,
    PDF_BYTES,
    PNG_BYTES,
    SVG_BYTES,
    macro_enabled_docm_bytes,
    oversized_content_types_zip_bytes,
    signup,
    upload_file,
    valid_docx_bytes,
    valid_xlsx_bytes,
)


# 8. valid PDF accepted
def test_valid_pdf_accepted(client: TestClient) -> None:
    token, _ = signup(client, "valid-pdf@example.com")

    response = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text
    assert response.json()["file_type"] == "application/pdf"


# 9. valid DOCX accepted
def test_valid_docx_accepted(client: TestClient) -> None:
    token, _ = signup(client, "valid-docx@example.com")

    response = upload_file(client, token, filename="doc.docx", content=valid_docx_bytes())

    assert response.status_code == 201, response.text
    assert "wordprocessingml" in response.json()["file_type"]


# 10. valid XLSX accepted
def test_valid_xlsx_accepted(client: TestClient) -> None:
    token, _ = signup(client, "valid-xlsx@example.com")

    response = upload_file(client, token, filename="doc.xlsx", content=valid_xlsx_bytes())

    assert response.status_code == 201, response.text
    assert "spreadsheetml" in response.json()["file_type"]


# 11. valid PNG accepted
def test_valid_png_accepted(client: TestClient) -> None:
    token, _ = signup(client, "valid-png@example.com")

    response = upload_file(client, token, filename="doc.png", content=PNG_BYTES)

    assert response.status_code == 201, response.text
    assert response.json()["file_type"] == "image/png"


# 12. valid JPEG accepted
def test_valid_jpeg_accepted(client: TestClient) -> None:
    token, _ = signup(client, "valid-jpeg@example.com")

    response = upload_file(client, token, filename="doc.jpg", content=JPEG_BYTES)

    assert response.status_code == 201, response.text
    assert response.json()["file_type"] == "image/jpeg"


# 13. unsupported executable rejected
def test_executable_rejected(client: TestClient) -> None:
    token, _ = signup(client, "reject-exe@example.com")

    response = upload_file(client, token, filename="tool.exe", content=EXECUTABLE_BYTES)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


# 14. HTML rejected
def test_html_rejected(client: TestClient) -> None:
    token, _ = signup(client, "reject-html@example.com")

    response = upload_file(client, token, filename="page.html", content=HTML_BYTES)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


# 15. SVG rejected
def test_svg_rejected(client: TestClient) -> None:
    token, _ = signup(client, "reject-svg@example.com")

    response = upload_file(client, token, filename="image.svg", content=SVG_BYTES)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


# 16. DOCM/XLSM rejected
def test_docm_extension_rejected_outright(client: TestClient) -> None:
    token, _ = signup(client, "reject-docm-ext@example.com")

    response = upload_file(client, token, filename="macro.docm", content=macro_enabled_docm_bytes())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_macro_enabled_content_rejected_even_under_docx_extension(client: TestClient) -> None:
    """A macro-enabled document renamed to .docx must still be rejected
    -- the extension alone is never sufficient; the zip's own
    [Content_Types].xml / vbaProject.bin presence is inspected too.
    """
    token, _ = signup(client, "reject-docm-spoof@example.com")

    response = upload_file(client, token, filename="macro.docx", content=macro_enabled_docm_bytes())

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


# 17. extension-only spoofing is rejected
def test_extension_only_spoofing_is_rejected(client: TestClient) -> None:
    """An executable renamed to .pdf must still be rejected -- content
    detection, not the claimed extension, decides.
    """
    token, _ = signup(client, "reject-spoof@example.com")

    response = upload_file(client, token, filename="totally-a.pdf", content=EXECUTABLE_BYTES)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_oversized_content_types_entry_is_rejected_not_decompressed(client: TestClient) -> None:
    """A DOCX-shaped zip whose [Content_Types].xml declares a large
    uncompressed size (the "zip bomb" entry shape) must be rejected based
    on that declared size, without ever being decompressed.
    """
    token, _ = signup(client, "reject-zip-bomb-content-types@example.com")

    response = upload_file(
        client, token, filename="bomb.docx", content=oversized_content_types_zip_bytes()
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_pdf_content_with_wrong_extension_is_rejected(client: TestClient) -> None:
    """The inverse spoof: real PDF bytes under an unsupported extension.
    Extension and content must both agree.
    """
    token, _ = signup(client, "reject-spoof-inverse@example.com")

    response = upload_file(client, token, filename="doc.exe", content=PDF_BYTES)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


# 18. file exceeding 25 MB is rejected
def test_file_exceeding_max_size_is_rejected(client: TestClient) -> None:
    oversized = PDF_BYTES + b"\x00" * (settings.storage_max_upload_bytes + 1)
    token, _ = signup(client, "reject-oversized@example.com")

    response = upload_file(client, token, filename="huge.pdf", content=oversized)

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


# 19. misleading Content-Length cannot bypass actual limit
def test_actual_byte_count_is_enforced_independent_of_any_declared_size() -> None:
    """Exercises the streaming size-check directly: the function never
    reads any Content-Length-shaped metadata at all, only the actual
    bytes produced by the file object -- so an object that could (in a
    real request) have arrived with an understated Content-Length header
    is still correctly rejected based on what it actually contains.
    """
    from app.modules.documents.exceptions import FileTooLargeError
    from app.modules.documents.upload_stream import measure_and_checksum

    real_oversized_content = io.BytesIO(b"\x00" * (settings.storage_max_upload_bytes + 1))

    try:
        measure_and_checksum(real_oversized_content, max_bytes=settings.storage_max_upload_bytes)
        raised = False
    except FileTooLargeError:
        raised = True

    assert raised


# 20. filename path traversal cannot affect storage key
def test_filename_path_traversal_cannot_affect_storage_key(client: TestClient) -> None:
    token, _ = signup(client, "traversal-filename@example.com")

    response = upload_file(
        client, token, filename="../../../etc/passwd.pdf", content=PDF_BYTES
    )

    assert response.status_code == 201, response.text
    body = response.json()
    # storage_key is never returned, but the display filename must be
    # reduced to a plain basename with no path components at all.
    assert "storage_key" not in body
    assert body["file_name"] == "passwd.pdf"
    assert "/" not in body["file_name"]
    assert ".." not in body["file_name"]


# 21. control characters in filename handled safely
def test_control_characters_in_filename_handled_safely(client: TestClient) -> None:
    token, _ = signup(client, "control-chars-filename@example.com")
    malicious_name = "invoice\x00\x1b[31m.pdf"

    response = upload_file(client, token, filename=malicious_name, content=PDF_BYTES)

    assert response.status_code == 201, response.text
    file_name = response.json()["file_name"]
    assert "\x00" not in file_name
    assert "\x1b" not in file_name


# 22. SHA-256 checksum is correct
def test_sha256_checksum_is_correct(client: TestClient) -> None:
    token, _ = signup(client, "checksum@example.com")

    response = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert response.status_code == 201, response.text
    assert response.json()["checksum_sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()

