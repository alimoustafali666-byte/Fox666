"""Real, parseable PDF/DOCX/XLSX fixture builders for processing tests.
Unlike tests/documents/helpers.py's PDF_BYTES etc. (which only need to
pass Step 8's magic-byte content-type validation), these produce files
pdfplumber/python-docx/openpyxl can actually extract real text from.
"""

import io
import uuid
import zipfile
from datetime import date

import docx
import openpyxl
from fastapi.testclient import TestClient

from tests.documents.helpers import auth_header


def build_native_text_pdf_bytes(pages: list[str]) -> bytes:
    """A minimal, hand-built but structurally valid single/multi-page
    PDF with a real, pdfplumber-extractable text layer -- computed byte
    offsets and all, so no external PDF-writing library is required as
    a test dependency.
    """
    buf = io.BytesIO()

    def w(data: bytes) -> None:
        buf.write(data)

    w(b"%PDF-1.4\n")

    n_pages = len(pages)
    page_obj_ids = []
    content_obj_ids = []
    next_id = 3
    for _ in range(n_pages):
        page_obj_ids.append(next_id)
        next_id += 1
        content_obj_ids.append(next_id)
        next_id += 1
    font_obj_id = next_id
    next_id += 1

    offsets: dict[int, int] = {}

    offsets[1] = buf.tell()
    w(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

    offsets[2] = buf.tell()
    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    w(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>\nendobj\n".encode())

    for i, text in enumerate(pages):
        pid = page_obj_ids[i]
        cid = content_obj_ids[i]
        offsets[pid] = buf.tell()
        w(
            f"{pid} 0 obj\n<< /Type /Page /Parent 2 0 R "
            f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> "
            f"/MediaBox [0 0 612 792] /Contents {cid} 0 R >>\nendobj\n".encode()
        )

        content_ops = []
        first = True
        for line in text.split("\n"):
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if first:
                content_ops.append(f"({escaped}) Tj")
                first = False
            else:
                content_ops.append(f"0 -16 Td ({escaped}) Tj")
        stream_body = "BT /F1 14 Tf 72 720 Td " + " ".join(content_ops) + " ET"
        stream_bytes = stream_body.encode()

        offsets[cid] = buf.tell()
        w(f"{cid} 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode())
        w(stream_bytes)
        w(b"\nendstream\nendobj\n")

    offsets[font_obj_id] = buf.tell()
    w(f"{font_obj_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode())

    xref_offset = buf.tell()
    total_objs = next_id
    w(f"xref\n0 {total_objs}\n".encode())
    w(b"0000000000 65535 f \n")
    for i in range(1, total_objs):
        w(f"{offsets[i]:010d} 00000 n \n".encode())
    w(f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())

    return buf.getvalue()


def build_empty_pdf_bytes() -> bytes:
    """A structurally valid single-page PDF with no text content at all
    -- stands in for a scanned/image-only PDF for insufficient-text tests
    without needing real image data.
    """
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets: dict[int, int] = {}

    offsets[1] = buf.tell()
    buf.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    offsets[2] = buf.tell()
    buf.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    offsets[3] = buf.tell()
    buf.write(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> "
        b"/MediaBox [0 0 612 792] >>\nendobj\n"
    )

    xref_offset = buf.tell()
    total_objs = 4
    buf.write(f"xref\n0 {total_objs}\n".encode())
    buf.write(b"0000000000 65535 f \n")
    for i in range(1, total_objs):
        buf.write(f"{offsets[i]:010d} 00000 n \n".encode())
    buf.write(f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode())
    return buf.getvalue()


def build_docx_bytes(
    *,
    sections: list[tuple[str, list[str]]] | None = None,
    table_rows: list[list[str]] | None = None,
) -> bytes:
    """sections: [(heading_text, [paragraph_text, ...]), ...]"""
    document = docx.Document()
    for heading, paragraphs in sections or []:
        document.add_heading(heading, level=1)
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)

    if table_rows:
        table = document.add_table(rows=len(table_rows), cols=len(table_rows[0]))
        for row_index, row_values in enumerate(table_rows):
            for col_index, value in enumerate(row_values):
                table.rows[row_index].cells[col_index].text = value

    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def build_xlsx_bytes(sheets: dict[str, list[list[object]]]) -> bytes:
    """sheets: {sheet_name: [[header...], [row...], ...]}"""
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_name, rows in sheets.items():
        sheet = workbook.create_sheet(sheet_name)
        for row in rows:
            sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def build_zip_bomb_shaped_docx_bytes() -> bytes:
    """A DOCX-shaped zip where word/document.xml itself (not just
    [Content_Types].xml, the specific member Step 8's upload-time check
    inspects) declares a small compressed size alongside a large,
    highly-compressible uncompressed size -- proving the general,
    whole-archive zip_safety guard (not just the upload-time
    classification check) rejects it before python-docx ever
    decompresses it.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            b"<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
            b"<Override PartName='/word/document.xml' "
            b"ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
            b"</Types>",
        )
        zf.writestr("word/document.xml", b"0" * (60 * 1024 * 1024))
    return buf.getvalue()


def build_xlsx_with_formula_bytes() -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Calc"
    sheet.append(["A", "B", "Sum"])
    sheet.append([5, 10, "=A2+B2"])
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def build_boq_xlsx_bytes() -> bytes:
    return build_xlsx_bytes(
        {
            "BOQ": [
                ["Item", "Qty", "Unit", "Rate", "Amount"],
                ["Concrete", 50, "m3", 350, 17500],
                ["Steel", 10.5, "ton", 2800.75, 29408.25],
                ["Site Date", date(2026, 1, 15), None, None, None],
            ],
        }
    )


def upload_and_get_document(
    client: TestClient, token: str, *, filename: str, content: bytes,
    document_type: str = "contract", project_id: str | None = None,
    content_type: str = "application/octet-stream",
) -> dict:
    data = {"document_type": document_type}
    if project_id is not None:
        data["project_id"] = project_id
    response = client.post(
        "/v1/documents",
        headers=auth_header(token),
        data=data,
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def trigger_processing(client: TestClient, token: str, document_id: str | uuid.UUID):
    return client.post(f"/v1/documents/{document_id}/process", headers=auth_header(token))

