"""Native-text PDF extraction only -- no OCR. A PDF with no extractable
text layer (most commonly a scanned/image-only PDF) raises
InsufficientTextError rather than silently succeeding with zero content.
"""

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

                for page_number, page in enumerate(pdf.pages, start=1):
                    raw_text = page.extract_text() or ""
                    # Page-level text is split into paragraph-like units
                    # on blank lines -- respects "page / paragraph"
                    # boundaries without requiring full layout analysis.
                    for paragraph in _PARAGRAPH_SPLIT.split(raw_text):
                        paragraph = paragraph.strip()
                        if not paragraph:
                            continue
                        elements.append(
                            ParsedElement(
                                text=paragraph,
                                element_type="paragraph",
                                page_number=page_number,
                                source_location={"page_number": page_number},
                            )
                        )
        except PathologicalDocumentError:
            raise
        except Exception as exc:
            raise ParserFailureError("PDF could not be read as a valid file.") from exc

        if not elements:
            raise InsufficientTextError(
                "PDF has no extractable native text -- it may be a scanned/image-only "
                "PDF, which OCR (not yet implemented) would be required for."
            )

        return ParsedDocument(elements=elements)

