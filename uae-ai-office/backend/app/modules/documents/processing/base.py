"""Parser abstraction. Processing orchestration (processing_orchestrator.py)
depends only on DocumentParser/ParsedElement/ParsedDocument and
processing.registry.get_parser -- never on pdfplumber, python-docx, or
openpyxl directly, so any individual parser can be replaced later
without touching orchestration.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Every ParsedElement.text
below is untrusted content extracted from a user-uploaded file. This
boundary is documented here, at the point content first enters the
system, and will be enforced again mechanically wherever this content
is later given to Claude (a future step) -- it must never be
concatenated into a system/instruction prompt or otherwise treated as
anything other than retrieved data.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import BinaryIO


@dataclass
class ParsedElement:
    """One atomic, orderable unit of extracted content -- a PDF
    paragraph, a DOCX paragraph/heading/table row, or an XLSX
    spreadsheet row. The chunker consumes these; it never re-parses raw
    file bytes itself.
    """

    text: str
    element_type: str  # "paragraph" | "heading" | "table_row" | "page"
    page_number: int | None = None
    sheet_name: str | None = None
    section_name: str | None = None
    source_location: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    elements: list[ParsedElement]


class DocumentParser(ABC):
    @abstractmethod
    def supports(self, file_type: str) -> bool:
        """Whether this parser handles documents.file_type's exact MIME
        value (the canonical value Step 8's content-type detection
        already assigned at upload time).
        """

    @abstractmethod
    def parse(self, fileobj: BinaryIO) -> ParsedDocument:
        """Extracts structured text from `fileobj` (a seekable,
        already-fully-fetched file-like object -- see
        processing_orchestrator, which fetches it via
        StorageProvider.download(), never a signed URL).

        Raises a app.modules.documents.processing.errors.ProcessingError
        subclass for every failure mode: InsufficientTextError (nothing
        meaningful to extract -- e.g. a scanned PDF with no text layer),
        PathologicalDocumentError (a configured structural limit was
        exceeded), or ParserFailureError (the underlying library itself
        raised on a malformed/corrupt file). Never lets a raw
        library/vendor exception escape uncaught.
        """

