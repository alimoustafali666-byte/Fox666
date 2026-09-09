"""OCR extraction for image documents and image-only PDF pages."""

from typing import BinaryIO, ClassVar

import pypdfium2 as pdfium
import pytesseract
from PIL import Image

from app.core.config import settings
from app.modules.documents.processing.base import DocumentParser, ParsedDocument, ParsedElement
from app.modules.documents.processing.errors import InsufficientTextError, ParserFailureError


class OcrParser(DocumentParser):
    _IMAGE_TYPES: ClassVar[set[str]] = {"image/png", "image/jpeg"}

    def supports(self, file_type: str) -> bool:
        return file_type in self._IMAGE_TYPES

    def parse(self, fileobj: BinaryIO) -> ParsedDocument:
        try:
            fileobj.seek(0)
            image = Image.open(fileobj)
            text = pytesseract.image_to_string(
                image, lang=settings.ocr_languages, config="--psm 6"
            ).strip()
            if not text:
                raise InsufficientTextError("OCR found no usable text in this document.")
            return ParsedDocument(elements=[ParsedElement(
                text=text,
                element_type="page",
                page_number=1,
                source_location={"page_number": 1, "source": "ocr"},
            )])
        except InsufficientTextError:
            raise
        except Exception as exc:
            raise ParserFailureError("OCR could not read this document.") from exc


def parse_pdf_with_ocr(fileobj: BinaryIO, *, skip_pages: set[int] | None = None) -> ParsedDocument:
    try:
        fileobj.seek(0)
        document = pdfium.PdfDocument(fileobj.read())
        if len(document) > settings.processing_max_pdf_pages:
            raise ParserFailureError("PDF has too many pages for OCR.")
        elements: list[ParsedElement] = []
        for page_number in range(len(document)):
            if page_number + 1 in (skip_pages or set()):
                continue
            page = document[page_number]
            bitmap = page.render(scale=settings.ocr_pdf_render_scale)
            text = pytesseract.image_to_string(
                bitmap.to_pil(), lang=settings.ocr_languages, config="--psm 6"
            ).strip()
            page.close()
            if text:
                elements.append(ParsedElement(
                    text=text,
                    element_type="page",
                    page_number=page_number + 1,
                    source_location={"page_number": page_number + 1, "source": "ocr"},
                ))
        document.close()
        if not elements:
            raise InsufficientTextError("OCR found no usable text in this document.")
        return ParsedDocument(elements=elements)
    except InsufficientTextError:
        raise
    except Exception as exc:
        raise ParserFailureError("OCR could not read this PDF.") from exc