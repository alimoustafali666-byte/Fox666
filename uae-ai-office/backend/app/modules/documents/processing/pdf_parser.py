"""Prefer native PDF text and fall back to OCR for scanned PDFs."""

import re
from typing import BinaryIO

import pdfplumber

from app.core.config import settings
from app.modules.documents.processing.base import DocumentParser, ParsedDocument, ParsedElement
from app.modules.documents.processing.errors import (
    InsufficientTextError,
    ParserFailureError,
    PathologicalDocumentError,
)
from app.modules.documents.processing.ocr_parser import parse_pdf_with_ocr

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


class PdfParser(DocumentParser):
    def supports(self, file_type: str) -> bool:
        return file_type == "application/pdf"

    def parse(self, fileobj: BinaryIO) -> ParsedDocument:
        fileobj.seek(0)
        elements: list[ParsedElement] = []
        try:
            with pdfplumber.open(fileobj) as pdf:
                if len(pdf.pages) > settings.processing_max_pdf_pages:
                    raise PathologicalDocumentError(
                        f"PDF has more than {settings.processing_max_pdf_pages} pages."
                    )

                native_text_pages: set[int] = set()
                for page_number, page in enumerate(pdf.pages, start=1):
                    raw_text = page.extract_text() or ""
                    # Page-level text is split into paragraph-like units
                    # on blank lines -- respects "page / paragraph"
                    # boundaries without requiring full layout analysis.
                    for paragraph in _PARAGRAPH_SPLIT.split(raw_text):
                        paragraph = paragraph.strip()
                        if not paragraph:
                            continue
                        native_text_pages.add(page_number)
                        elements.append(
                            ParsedElement(
                                text=paragraph,
                                element_type="paragraph",
                                page_number=page_number,
                                source_location={"page_number": page_number},
                            )
                        )
                page_count = len(pdf.pages)
        except PathologicalDocumentError:
            raise
        except Exception as exc:
            raise ParserFailureError("PDF could not be read as a valid file.") from exc

        if not elements or len(native_text_pages) < page_count:
            ocr_document = parse_pdf_with_ocr(fileobj, skip_pages=native_text_pages)
            elements.extend(ocr_document.elements)
        if not elements:
            raise InsufficientTextError("PDF has no usable extracted text.")

        return ParsedDocument(elements=elements)

