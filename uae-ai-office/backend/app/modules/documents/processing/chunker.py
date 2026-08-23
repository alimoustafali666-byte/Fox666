"""Deterministic, structure-aware chunking.

Elements are grouped by sheet_name first -- a hard boundary that is
never crossed (XLSX rows from two different sheets never end up in the
same chunk; for PDF/DOCX, sheet_name is always None, so the whole
document is one group). Within a group, whole elements (a PDF
paragraph, a DOCX paragraph/heading/table row, an XLSX row) are
accumulated in order up to the configured token target; an element is
never split across two chunks except in the rare case where a single
element alone exceeds the target, which becomes its own oversized
chunk rather than being cut mid-content. After each chunk boundary, a
suffix of the just-finished chunk (bounded by the configured overlap
ratio) seeds the start of the next one.

Purely a function of its inputs -- no randomness, no dict-iteration-
order dependence -- so identical input always produces identical,
stably-ordered output.
"""

import itertools
from dataclasses import dataclass

from app.modules.documents.processing.base import ParsedElement
from app.modules.documents.processing.tokenizer import TokenCounter, default_token_counter


@dataclass
class Chunk:
    content: str
    token_count: int
    page_number: int | None
    sheet_name: str | None
    section_name: str | None
    source_location: dict | None


def chunk_elements(
    elements: list[ParsedElement],
    *,
    target_tokens: int,
    overlap_ratio: float,
    token_counter: TokenCounter = default_token_counter,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for _, group_iter in itertools.groupby(elements, key=lambda el: el.sheet_name):
        group = list(group_iter)
        chunks.extend(
            _chunk_group(
                group, target_tokens=target_tokens, overlap_ratio=overlap_ratio,
                token_counter=token_counter,
            )
        )
    return chunks


def _chunk_group(
    elements: list[ParsedElement], *, target_tokens: int, overlap_ratio: float,
    token_counter: TokenCounter,
) -> list[Chunk]:
    if not elements:
        return []

    token_counts = [max(1, token_counter.count(el.text)) for el in elements]
    n = len(elements)
    overlap_budget = max(1, round(target_tokens * overlap_ratio))
    chunks: list[Chunk] = []
    start = 0

    while start < n:
        end = start
        total = 0
        while end < n:
            t = token_counts[end]
            if total and total + t > target_tokens:
                break
            total += t
            end += 1
        # elements[start:end] is always non-empty: the inner loop always
        # takes at least one element regardless of its size (the "total
        # and ..." guard only applies once something has been added).
        chunks.append(_finalize_chunk(elements[start:end], token_counter=token_counter))

        if end >= n:
            break

        # Seed the next chunk with a trailing suffix of this one, bounded
        # by overlap_budget, without ever walking back past `start`.
        back = end - 1
        overlap_total = 0
        while back > start:
            t = token_counts[back]
            if overlap_total and overlap_total + t > overlap_budget:
                break
            overlap_total += t
            back -= 1
        next_start = back + 1 if overlap_total > 0 else end
        # Guarantees forward progress every outer iteration.
        start = max(next_start, start + 1)

    return chunks


def _finalize_chunk(elements: list[ParsedElement], *, token_counter: TokenCounter) -> Chunk:
    sheet_name = elements[0].sheet_name
    pages = _ordered_unique(el.page_number for el in elements if el.page_number is not None)
    sections = _ordered_unique(el.section_name for el in elements if el.section_name)

    body = "\n\n".join(el.text for el in elements)
    # A sheet is a hard boundary for the whole chunk, so naming it once
    # up front (rather than repeating "Sheet: X" on every row, which the
    # parser deliberately does not do) keeps a multi-row chunk
    # self-describing on its own.
    content = f"Sheet: {sheet_name}\n\n{body}" if sheet_name else body

    source_location: dict = {}
    if pages:
        source_location["pages"] = pages
    if sections:
        source_location["sections"] = sections
    if sheet_name:
        rows = [
            el.source_location["row"]
            for el in elements
            if el.source_location and "row" in el.source_location
        ]
        if rows:
            source_location["sheet_name"] = sheet_name
            source_location["rows"] = [min(rows), max(rows)]

    return Chunk(
        content=content,
        token_count=token_counter.count(content),
        page_number=pages[0] if pages else None,
        sheet_name=sheet_name,
        section_name=sections[0] if sections else None,
        source_location=source_location or None,
    )


def _ordered_unique(values) -> list:
    seen: list = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen

