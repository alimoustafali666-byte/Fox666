import io
import uuid
import zipfile

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import set_company_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def signup(client: TestClient, email: str, company_name: str = "Documents Test Co") -> tuple[str, dict]:
    response = client.post(
        "/v1/auth/signup",
        json={
            "email": email,
            "password": "correct horse battery staple",
            "full_name": "Test User",
            "company_name": company_name,
        },
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    return token, claims


def seed_member(db_session: Session, *, company_id: uuid.UUID, email: str, role: str) -> str:
    user = User(
        email=email, password_hash=hash_password("irrelevant-password-value"), full_name="Seeded"
    )
    db_session.add(user)
    db_session.flush()

    set_company_context(db_session, company_id)
    db_session.add(CompanyMember(company_id=company_id, user_id=user.id, role=role))
    db_session.flush()

    return create_access_token(user_id=user.id, company_id=company_id, role=role)


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_project(client: TestClient, token: str, name: str = "Test Project") -> dict:
    response = client.post("/v1/projects", json={"name": name}, headers=auth_header(token))
    assert response.status_code == 201
    return response.json()


# --- Minimal, structurally valid file bytes for each supported type ---
# Magic bytes only for PDF/PNG/JPEG -- the content_validation module never
# parses further than that for these three types, so a minimal fake body
# with the right signature is all that's needed for these to be accepted.

PDF_BYTES = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< >>\nendobj\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32

EXECUTABLE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
HTML_BYTES = b"<!DOCTYPE html><html><body><script>alert(1)</script></body></html>"
SVG_BYTES = b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"


def _minimal_ooxml_zip(*, content_types_xml: bytes, main_part_name: str, extra_parts: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr(main_part_name, b"<root/>")
        for name, content in (extra_parts or {}).items():
            zf.writestr(name, content)
    return buffer.getvalue()


def valid_docx_bytes() -> bytes:
    content_types = (
        b"<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        b"<Override PartName='/word/document.xml' "
        b"ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
        b"</Types>"
    )
    return _minimal_ooxml_zip(content_types_xml=content_types, main_part_name="word/document.xml")


def valid_xlsx_bytes() -> bytes:
    content_types = (
        b"<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        b"<Override PartName='/xl/workbook.xml' "
        b"ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml'/>"
        b"</Types>"
    )
    return _minimal_ooxml_zip(content_types_xml=content_types, main_part_name="xl/workbook.xml")


def oversized_content_types_zip_bytes() -> bytes:
    """A DOCX-shaped zip whose [Content_Types].xml declares a highly
    compressible, oversized uncompressed size -- the classic "zip bomb"
    entry shape -- used to prove content_validation rejects it based on
    the entry's declared uncompressed size before ever decompressing it.
    """
    huge_but_compressible = b"<!--" + (b"0" * (2 * 1024 * 1024)) + b"-->"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", huge_but_compressible)
        zf.writestr("word/document.xml", b"<root/>")
    return buffer.getvalue()


def macro_enabled_docm_bytes() -> bytes:
    """A DOCX-shaped zip that also carries a vbaProject.bin part, the way
    a real macro-enabled Word document (.docm) would -- used to prove
    macro content is rejected even if uploaded under a spoofed .docx
    extension, not just when the extension itself says .docm.
    """
    content_types = (
        b"<?xml version='1.0'?><Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        b"<Override PartName='/word/document.xml' "
        b"ContentType='application/vnd.ms-word.document.macroEnabled.12.main+xml'/>"
        b"</Types>"
    )
    return _minimal_ooxml_zip(
        content_types_xml=content_types,
        main_part_name="word/document.xml",
        extra_parts={"word/vbaProject.bin": b"\x00\x01\x02"},
    )


def upload_file(
    client: TestClient,
    token: str,
    *,
    filename: str,
    content: bytes,
    document_type: str = "contract",
    project_id: str | None = None,
    content_type: str = "application/octet-stream",
):
    data = {"document_type": document_type}
    if project_id is not None:
        data["project_id"] = project_id
    return client.post(
        "/v1/documents",
        headers=auth_header(token),
        data=data,
        files={"file": (filename, content, content_type)},
    )

