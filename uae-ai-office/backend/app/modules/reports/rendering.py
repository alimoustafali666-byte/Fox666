"""Format-agnostic report data structures plus one renderer per export
format (CSV/XLSX/DOCX/PDF). Every domain report builder in
app.modules.reports.builders produces the same ReportData shape; these
renderers are the ONLY place that knows how to turn it into bytes --
adding a new report type never means touching export logic, and fixing/
improving an export format never means touching the seven builders.

Arabic (locale="ar") is a first-class case throughout, not an
afterthought: XLSX sheets are flagged right-to-left, DOCX paragraphs and
tables get the `bidi`/`bidiVisual` OOXML flags, and PDF text is run
through arabic_reshaper + python-bidi and drawn with a bundled
Arabic-capable font (Noto Naskh Arabic) -- reportlab's built-in base-14
fonts (Helvetica etc.) have no Arabic glyphs at all, and unshaped Arabic
renders as visually disconnected, wrong-order letters.
"""

import csv
import io
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import arabic_reshaper
import openpyxl
from bidi.algorithm import get_display
from docx import Document as DocxDocument
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

_ARABIC_FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "NotoNaskhArabic.ttf")
_ARABIC_FONT_NAME = "NotoNaskhArabic"
_font_registered = False


def _ensure_arabic_font_registered() -> None:
    global _font_registered
    if not _font_registered:
        try:
            pdfmetrics.registerFont(TTFont(_ARABIC_FONT_NAME, _ARABIC_FONT_PATH))
        except Exception as exc:
            # This asset is a binary file. Copying the tree through any
            # text-only channel (an export, a patch, a chat transcript)
            # silently replaces it with a placeholder, and reportlab then
            # fails deep inside its TTF parser with "Not a recognized
            # TrueType font" -- which says nothing about what to do.
            raise RuntimeError(
                f"The bundled Arabic PDF font at {_ARABIC_FONT_PATH} is missing or is not a "
                "valid TrueType file, so Arabic PDF reports cannot be rendered. Restore it with "
                "a real copy of Noto Naskh Arabic Regular (e.g. Debian/Ubuntu's fonts-noto-core "
                "package ships it at "
                "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf)."
            ) from exc
        _font_registered = True


@dataclass
class ReportColumn:
    key: str
    label_en: str
    label_ar: str


@dataclass
class ReportMeta:
    report_type: str
    title_en: str
    title_ar: str
    company_id: uuid.UUID
    company_name: str
    generated_at: datetime
    generated_by_name: str
    reference_number: str
    filters_summary_en: str
    filters_summary_ar: str
    row_count: int
    logo_bytes: bytes | None = None
    logo_content_type: str | None = None


@dataclass
class ReportData:
    meta: ReportMeta
    columns: list[ReportColumn]
    # Every value already stringified (dates formatted, None -> "",
    # enums translated) -- renderers never make locale/formatting
    # decisions about a value, only about layout.
    rows: list[dict[str, str]] = field(default_factory=list)


def _title(meta: ReportMeta, locale: str) -> str:
    return meta.title_ar if locale == "ar" else meta.title_en


def _filters_summary(meta: ReportMeta, locale: str) -> str:
    return meta.filters_summary_ar if locale == "ar" else meta.filters_summary_en


def _column_label(column: ReportColumn, locale: str) -> str:
    return column.label_ar if locale == "ar" else column.label_en


def _generated_line(meta: ReportMeta, locale: str) -> str:
    when = meta.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    if locale == "ar":
        return f"أُنشئ في {when} بواسطة {meta.generated_by_name}"
    return f"Generated {when} by {meta.generated_by_name}"


# --- CSV ---


def render_csv(data: ReportData, *, locale: str) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([f"{_title(data.meta, locale)}"])
    writer.writerow([data.meta.company_name])
    writer.writerow([_generated_line(data.meta, locale)])
    writer.writerow([f"Reference: {data.meta.reference_number}"])
    if data.meta.filters_summary_en or data.meta.filters_summary_ar:
        writer.writerow([_filters_summary(data.meta, locale)])
    writer.writerow([])
    writer.writerow([_column_label(c, locale) for c in data.columns])
    for row in data.rows:
        writer.writerow([row.get(c.key, "") for c in data.columns])
    # UTF-8 BOM so Excel (the realistic consumer of a business CSV, in
    # either language) doesn't mis-decode non-ASCII bytes as the system
    # codepage -- harmless for pure-ASCII English content too.
    return ("﻿" + buffer.getvalue()).encode("utf-8")


# --- XLSX ---


def render_xlsx(data: ReportData, *, locale: str) -> bytes:
    is_rtl = locale == "ar"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.sheet_view.rightToLeft = is_rtl

    align = Alignment(horizontal="right" if is_rtl else "left", wrap_text=True, vertical="top")
    bold = Font(bold=True)
    title_font = Font(bold=True, size=14)
    header_fill = PatternFill(start_color="1F2A46", end_color="1F2A46", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")

    row_cursor = 1
    ws.cell(row=row_cursor, column=1, value=_title(data.meta, locale)).font = title_font
    row_cursor += 1
    ws.cell(row=row_cursor, column=1, value=data.meta.company_name).font = bold
    row_cursor += 1
    ws.cell(row=row_cursor, column=1, value=_generated_line(data.meta, locale))
    row_cursor += 1
    ws.cell(row=row_cursor, column=1, value=f"Reference: {data.meta.reference_number}")
    row_cursor += 1
    summary = _filters_summary(data.meta, locale)
    if summary:
        ws.cell(row=row_cursor, column=1, value=summary)
        row_cursor += 1
    row_cursor += 1

    header_row = row_cursor
    for col_idx, column in enumerate(data.columns, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=_column_label(column, locale))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align

    for row_offset, row in enumerate(data.rows, start=1):
        for col_idx, column in enumerate(data.columns, start=1):
            cell = ws.cell(row=header_row + row_offset, column=col_idx, value=row.get(column.key, ""))
            cell.alignment = align

    for col_idx, column in enumerate(data.columns, start=1):
        width = max(12, min(40, len(_column_label(column, locale)) + 4))
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# --- DOCX ---


def _set_paragraph_rtl(paragraph, *, rtl: bool) -> None:
    if not rtl:
        return
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = p_pr.makeelement(qn("w:bidi"), {})
    p_pr.append(bidi)


def _set_table_rtl(table, *, rtl: bool) -> None:
    if not rtl:
        return
    tbl_pr = table._tbl.tblPr
    bidi_visual = tbl_pr.makeelement(qn("w:bidiVisual"), {})
    tbl_pr.append(bidi_visual)


def render_docx(data: ReportData, *, locale: str) -> bytes:
    is_rtl = locale == "ar"
    doc = DocxDocument()

    title_p = doc.add_paragraph()
    run = title_p.add_run(_title(data.meta, locale))
    run.bold = True
    run.font.size = Pt(18)
    _set_paragraph_rtl(title_p, rtl=is_rtl)

    company_p = doc.add_paragraph()
    company_run = company_p.add_run(data.meta.company_name)
    company_run.bold = True
    company_run.font.size = Pt(12)
    _set_paragraph_rtl(company_p, rtl=is_rtl)

    meta_p = doc.add_paragraph(_generated_line(data.meta, locale))
    _set_paragraph_rtl(meta_p, rtl=is_rtl)
    ref_p = doc.add_paragraph(f"Reference: {data.meta.reference_number}")
    _set_paragraph_rtl(ref_p, rtl=is_rtl)
    summary = _filters_summary(data.meta, locale)
    if summary:
        summary_p = doc.add_paragraph(summary)
        summary_p.runs[0].italic = True
        _set_paragraph_rtl(summary_p, rtl=is_rtl)

    doc.add_paragraph()

    table = doc.add_table(rows=1, cols=len(data.columns))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Light Grid Accent 1"
    _set_table_rtl(table, rtl=is_rtl)

    header_cells = table.rows[0].cells
    for idx, column in enumerate(data.columns):
        header_cells[idx].text = _column_label(column, locale)
        for p in header_cells[idx].paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _set_paragraph_rtl(p, rtl=is_rtl)
        header_cells[idx]._tc.get_or_add_tcPr()
        shading = header_cells[idx]._tc.get_or_add_tcPr().makeelement(
            qn("w:shd"), {qn("w:val"): "clear", qn("w:fill"): "1F2A46"}
        )
        header_cells[idx]._tc.get_or_add_tcPr().append(shading)

    for row in data.rows:
        cells = table.add_row().cells
        for idx, column in enumerate(data.columns):
            cells[idx].text = str(row.get(column.key, ""))
            for p in cells[idx].paragraphs:
                _set_paragraph_rtl(p, rtl=is_rtl)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# --- PDF ---

_ARABIC_RANGE = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")


def _shape(text: str) -> str:
    """Reshapes+bidi-reorders a string IF it actually contains Arabic
    script characters -- decided per-string by content, not by the
    report's overall locale. A company's actual data (a project name, a
    task title) can be typed in either language regardless of which
    locale the report itself is generated in, so an "English" report can
    still contain Arabic cell values that need shaping, and vice versa.
    Non-Arabic text is returned unchanged.
    """
    if not text or not _ARABIC_RANGE.search(text):
        return text
    return get_display(arabic_reshaper.reshape(text))


class _NumberedCanvas(pdf_canvas.Canvas):
    """Draws 'Page N of M' -- requires a second pass (reportlab has no
    single-pass way to know the final page count while drawing page 1),
    the standard documented technique for page-total footers in
    reportlab: buffer every page, then stamp the total once it's known.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total_pages)
            super().showPage()
        super().save()

    def _draw_page_number(self, total_pages: int) -> None:
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#6b7280"))
        self.drawCentredString(
            A4[0] / 2, 12 * mm, f"Page {self._pageNumber} of {total_pages}"
        )


def render_pdf(data: ReportData, *, locale: str) -> bytes:
    is_rtl = locale == "ar"
    # Always the Arabic-capable font, for BOTH locales: report DATA (a
    # project name, a task title) can contain Arabic text regardless of
    # which locale the report itself was generated in, and reportlab's
    # base-14 fonts (Helvetica) have no Arabic glyphs at all -- using
    # them here would silently render any Arabic cell value as blank
    # boxes. Noto Naskh Arabic also covers Latin + digits cleanly, so
    # there is no quality tradeoff for English-only content.
    _ensure_arabic_font_registered()
    font_name = _ARABIC_FONT_NAME
    font_bold = _ARABIC_FONT_NAME

    buffer = io.BytesIO()
    left_margin = right_margin = 15 * mm

    def _header_footer(canvas_obj, doc) -> None:
        canvas_obj.saveState()
        canvas_obj.setFont(font_bold, 13)
        canvas_obj.setFillColor(colors.HexColor("#1F2A46"))
        title_x = A4[0] - right_margin if is_rtl else left_margin
        align_fn = canvas_obj.drawRightString if is_rtl else canvas_obj.drawString
        align_fn(title_x, A4[1] - 18 * mm, _shape(_title(data.meta, locale)))

        canvas_obj.setFont(font_name, 9)
        canvas_obj.setFillColor(colors.HexColor("#374151"))
        align_fn(title_x, A4[1] - 24 * mm, _shape(data.meta.company_name))

        if data.meta.logo_bytes:
            try:
                from reportlab.lib.utils import ImageReader

                img = ImageReader(io.BytesIO(data.meta.logo_bytes))
                logo_x = left_margin if is_rtl else (A4[0] - right_margin - 20 * mm)
                canvas_obj.drawImage(
                    img, logo_x, A4[1] - 26 * mm, width=20 * mm, height=14 * mm,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                # A malformed/corrupt logo must never break report generation.
                logger.warning("Skipping unreadable company logo in PDF report header.", exc_info=True)

        canvas_obj.setFont(font_name, 7)
        canvas_obj.setFillColor(colors.HexColor("#6b7280"))
        align_fn(
            title_x, 18 * mm,
            _shape(f"{data.meta.reference_number} -- {_generated_line(data.meta, locale)}"),
        )
        canvas_obj.restoreState()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=left_margin, rightMargin=right_margin,
        topMargin=30 * mm, bottomMargin=24 * mm,
        title=_title(data.meta, locale),
    )

    cell_style = ParagraphStyle(
        "cell", fontName=font_name, fontSize=8, leading=10,
        alignment=2 if is_rtl else 0,
    )
    header_style = ParagraphStyle(
        "header", fontName=font_bold, fontSize=8, leading=10,
        alignment=2 if is_rtl else 0, textColor=colors.white,
    )

    columns = list(reversed(data.columns)) if is_rtl else data.columns
    header_row = [Paragraph(_shape(_column_label(c, locale)), header_style) for c in columns]
    table_rows = [header_row]
    for row in data.rows:
        table_rows.append(
            [Paragraph(_shape(str(row.get(c.key, ""))), cell_style) for c in columns]
        )

    available_width = A4[0] - left_margin - right_margin
    col_width = available_width / max(1, len(columns))
    table = Table(table_rows, colWidths=[col_width] * len(columns), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2A46")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    story = [Spacer(1, 2 * mm), table]
    doc.build(
        story,
        onFirstPage=_header_footer,
        onLaterPages=_header_footer,
        canvasmaker=_NumberedCanvas,
    )
    return buffer.getvalue()


RENDERERS = {
    "csv": render_csv,
    "xlsx": render_xlsx,
    "docx": render_docx,
    "pdf": render_pdf,
}

CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}

