from app.modules.documents.processing.normalize import normalize_text


# 17. normalization does not alter important numbers/codes
def test_normalization_preserves_numbers_currencies_codes_and_dates() -> None:
    text = "Invoice INV-2026-00042: AED 17,500.00 due 2026-03-15, qty 50.5 units."

    assert normalize_text(text) == text


def test_normalization_collapses_repeated_whitespace() -> None:
    text = "Item:   Concrete    Qty:  50"

    assert normalize_text(text) == "Item: Concrete Qty: 50"


def test_normalization_collapses_excessive_blank_lines() -> None:
    text = "Paragraph one.\n\n\n\n\nParagraph two."

    assert normalize_text(text) == "Paragraph one.\n\nParagraph two."


def test_normalization_preserves_meaningful_paragraph_boundaries() -> None:
    text = "Paragraph one.\n\nParagraph two."

    assert normalize_text(text) == text


def test_normalization_handles_windows_and_mac_line_endings() -> None:
    text = "Line one.\r\nLine two.\rLine three."

    assert normalize_text(text) == "Line one.\nLine two.\nLine three."


def test_normalization_handles_unicode_safely() -> None:
    arabic = "البند: خرسانة الكمية: 50"

    assert normalize_text(arabic) == arabic


def test_normalization_strips_leading_and_trailing_whitespace() -> None:
    assert normalize_text("   padded text   ") == "padded text"

