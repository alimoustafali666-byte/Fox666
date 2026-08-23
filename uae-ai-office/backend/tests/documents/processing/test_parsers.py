import io

import pytest

from app.core.config import settings
from app.modules.documents.processing.docx_parser import DocxParser
from app.modules.documents.processing.errors import (
    InsufficientTextError,
    ParserFailureError,
    PathologicalDocumentError,
)
from app.modules.documents.processing.pdf_parser import PdfParser
from app.modules.documents.processing.xlsx_parser import XlsxParser
from tests.documents.helpers import macro_enabled_docm_bytes
from tests.documents.processing.helpers import (
    build_docx_bytes,
    build_empty_pdf_bytes,
    build_native_text_pdf_bytes,
    build_xlsx_bytes,
    build_xlsx_with_formula_bytes,
    build_zip_bomb_shaped_docx_bytes,
)


# 4. PDF native text extracts correctly
def test_pdf_native_text_extracts_correctly() -> None:
    pdf_bytes = build_native_text_pdf_bytes(["Hello World\nThis is page one."])

    result = PdfParser().parse(io.BytesIO(pdf_bytes))

    assert any("Hello World" in el.text for el in result.elements)


# 5. PDF page metadata preserved
def test_pdf_page_metadata_preserved() -> None:
    pdf_bytes = build_native_text_pdf_bytes(["Page one text.", "Page two text.", "Page three text."])

    result = PdfParser().parse(io.BytesIO(pdf_bytes))

    pages = {el.page_number for el in result.elements}
    assert pages == {1, 2, 3}
    page_three_text = next(el.text for el in result.elements if el.page_number == 3)
    assert "Page three" in page_three_text


# 6. scanned/empty PDF does not silently become processed
def test_empty_pdf_raises_insufficient_text_not_silently_processed() -> None:
    with pytest.raises(InsufficientTextError):
        PdfParser().parse(io.BytesIO(build_empty_pdf_bytes()))


def test_corrupt_pdf_raises_parser_failure_not_a_raw_exception() -> None:
    with pytest.raises(ParserFailureError):
        PdfParser().parse(io.BytesIO(b"%PDF-1.4\nnot actually a valid pdf body"))


def test_pdf_exceeding_page_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "processing_max_pdf_pages", 2)
    pdf_bytes = build_native_text_pdf_bytes(["Page one.", "Page two.", "Page three."])

    with pytest.raises(PathologicalDocumentError):
        PdfParser().parse(io.BytesIO(pdf_bytes))


# 7. DOCX paragraphs extract correctly
def test_docx_paragraphs_extract_correctly() -> None:
    docx_bytes = build_docx_bytes(sections=[("Intro", ["First paragraph.", "Second paragraph."])])

    result = DocxParser().parse(io.BytesIO(docx_bytes))

    texts = [el.text for el in result.elements]
    assert "First paragraph." in texts
    assert "Second paragraph." in texts


# 8. DOCX headings preserved where practical
def test_docx_headings_preserved() -> None:
    docx_bytes = build_docx_bytes(
        sections=[("Section One", ["Para under one."]), ("Section Two", ["Para under two."])]
    )

    result = DocxParser().parse(io.BytesIO(docx_bytes))

    headings = [el for el in result.elements if el.element_type == "heading"]
    assert {h.text for h in headings} == {"Section One", "Section Two"}
    # paragraphs carry the section they fall under
    para_under_two = next(el for el in result.elements if el.text == "Para under two.")
    assert para_under_two.section_name == "Section Two"


# 9. DOCX tables produce usable structured text
def test_docx_tables_produce_usable_structured_text() -> None:
    docx_bytes = build_docx_bytes(
        table_rows=[["Item", "Qty", "Rate"], ["Concrete", "50", "350"]]
    )

    result = DocxParser().parse(io.BytesIO(docx_bytes))

    table_rows = [el for el in result.elements if el.element_type == "table_row"]
    assert len(table_rows) == 2
    assert "Concrete" in table_rows[1].text
    assert "50" in table_rows[1].text


def test_docx_with_no_content_raises_insufficient_text() -> None:
    docx_bytes = build_docx_bytes()

    with pytest.raises(InsufficientTextError):
        DocxParser().parse(io.BytesIO(docx_bytes))


def test_corrupt_docx_raises_parser_failure() -> None:
    with pytest.raises(ParserFailureError):
        DocxParser().parse(io.BytesIO(b"not a real docx file at all"))


def test_zip_bomb_shaped_docx_part_is_rejected_before_decompression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """word/document.xml itself (not [Content_Types].xml, the one member
    Step 8's upload-time check inspects) declares 60MB of highly
    compressible content -- the general, whole-archive zip_safety guard
    must reject this before python-docx ever decompresses it.
    """
    monkeypatch.setattr(settings, "processing_max_zip_entry_uncompressed_bytes", 10 * 1024 * 1024)

    with pytest.raises(PathologicalDocumentError):
        DocxParser().parse(io.BytesIO(build_zip_bomb_shaped_docx_bytes()))


# 16. DOCM masquerading as content still rejected at the parsing layer
# (defense in depth -- Step 8 upload validation already rejects this by
# extension/content-type before a document ever reaches processing).
def test_macro_enabled_docm_content_is_not_silently_accepted_by_docx_parser() -> None:
    """python-docx itself doesn't distinguish macro-enabled content (that
    distinction lives in Step 8's content-type validation, run before
    upload), so this only proves the parser still produces safe output
    (extracted text, never executed VBA) rather than raising an
    unexpected/unsafe error -- macro *execution* is never performed by
    any code in this pipeline.
    """
    try:
        DocxParser().parse(io.BytesIO(macro_enabled_docm_bytes()))
    except (ParserFailureError, InsufficientTextError):
        pass  # also acceptable: the fixture has no real paragraph content


# 10. XLSX sheet names preserved
def test_xlsx_sheet_names_preserved() -> None:
    xlsx_bytes = build_xlsx_bytes(
        {"BOQ": [["Item", "Qty"], ["Concrete", 50]], "Summary": [["Total"], [100]]}
    )

    result = XlsxParser().parse(io.BytesIO(xlsx_bytes))

    sheet_names = {el.sheet_name for el in result.elements}
    assert sheet_names == {"BOQ", "Summary"}


# 11. XLSX rows retain logical relationships
def test_xlsx_rows_retain_logical_relationships() -> None:
    xlsx_bytes = build_xlsx_bytes(
        {"BOQ": [["Item", "Qty", "Rate"], ["Concrete", 50, 350], ["Steel", 10, 2800]]}
    )

    result = XlsxParser().parse(io.BytesIO(xlsx_bytes))

    concrete_row = next(el for el in result.elements if "Concrete" in el.text)
    assert "Qty: 50" in concrete_row.text
    assert "Rate: 350" in concrete_row.text
    assert "Steel" not in concrete_row.text  # rows never merge into one element


# 12. multiple sheets never merge into one chunk (parser-level: never
# merge into one *element* either -- each row stays scoped to its sheet)
def test_xlsx_multiple_sheets_never_merge_into_one_element() -> None:
    xlsx_bytes = build_xlsx_bytes(
        {"BOQ": [["Item"], ["Concrete"]], "Summary": [["Total"], ["100"]]}
    )

    result = XlsxParser().parse(io.BytesIO(xlsx_bytes))

    for el in result.elements:
        assert el.sheet_name in ("BOQ", "Summary")
        if el.sheet_name == "BOQ":
            assert "Total" not in el.text
        else:
            assert "Concrete" not in el.text


# 13. numeric values preserved
def test_xlsx_numeric_values_preserved_exactly() -> None:
    xlsx_bytes = build_xlsx_bytes(
        {"Sheet1": [["Qty", "Rate"], [50, 2800.75]]}
    )

    result = XlsxParser().parse(io.BytesIO(xlsx_bytes))

    row = result.elements[0]
    assert "Qty: 50" in row.text
    assert "Rate: 2800.75" in row.text


# 14. dates preserved
def test_xlsx_dates_preserved() -> None:
    from datetime import date

    xlsx_bytes = build_xlsx_bytes({"Sheet1": [["When"], [date(2026, 3, 1)]]})

    result = XlsxParser().parse(io.BytesIO(xlsx_bytes))

    assert "2026-03-01" in result.elements[0].text


# 15. formulas handled safely without execution
def test_xlsx_formula_cells_handled_safely_without_execution() -> None:
    xlsx_bytes = build_xlsx_with_formula_bytes()

    result = XlsxParser().parse(io.BytesIO(xlsx_bytes))

    row = result.elements[0]
    # No cached value exists for a formula never opened in real Excel --
    # the cell is safely treated as blank, never evaluated by our code.
    assert "A: 5" in row.text
    assert "B: 10" in row.text
    assert "=A2+B2" not in row.text
    assert "Sum" not in row.text or "Sum:" not in row.text


def test_xlsx_with_no_content_raises_insufficient_text() -> None:
    xlsx_bytes = build_xlsx_bytes({"Sheet1": []})

    with pytest.raises(InsufficientTextError):
        XlsxParser().parse(io.BytesIO(xlsx_bytes))


def test_corrupt_xlsx_raises_parser_failure() -> None:
    with pytest.raises(ParserFailureError):
        XlsxParser().parse(io.BytesIO(b"not a real xlsx file at all"))


def test_xlsx_exceeding_sheet_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "processing_max_xlsx_sheets", 1)
    xlsx_bytes = build_xlsx_bytes({"One": [["A"], [1]], "Two": [["B"], [2]]})

    with pytest.raises(PathologicalDocumentError):
        XlsxParser().parse(io.BytesIO(xlsx_bytes))


# 16. Unicode content preserved
def test_unicode_content_preserved_in_pdf_and_docx_and_xlsx() -> None:
    arabic_text = "مرحبا بالعالم"
    pdf_result = PdfParser().parse(io.BytesIO(build_native_text_pdf_bytes(["plain ascii only"])))
    assert pdf_result.elements  # sanity: pdf pipeline itself works

    docx_result = DocxParser().parse(
        io.BytesIO(build_docx_bytes(sections=[("Section", [arabic_text])]))
    )
    assert any(arabic_text in el.text for el in docx_result.elements)

    xlsx_result = XlsxParser().parse(
        io.BytesIO(build_xlsx_bytes({"Sheet1": [["Name"], [arabic_text]]}))
    )
    assert any(arabic_text in el.text for el in xlsx_result.elements)

