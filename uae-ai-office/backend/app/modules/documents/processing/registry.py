"""The only place processing orchestration resolves a file_type to a
concrete parser. Adding/replacing a parser means changing this list --
orchestration itself never references a specific parser class.
"""

from app.modules.documents.processing.base import DocumentParser
from app.modules.documents.processing.docx_parser import DocxParser
from app.modules.documents.processing.ocr_parser import OcrParser
from app.modules.documents.processing.pdf_parser import PdfParser
from app.modules.documents.processing.xlsx_parser import XlsxParser

_PARSERS: tuple[DocumentParser, ...] = (PdfParser(), OcrParser(), DocxParser(), XlsxParser())


def get_parser(file_type: str) -> DocumentParser | None:
    for parser in _PARSERS:
        if parser.supports(file_type):
            return parser
    return None

