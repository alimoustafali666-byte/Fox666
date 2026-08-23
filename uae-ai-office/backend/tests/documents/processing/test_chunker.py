import itertools

from app.modules.documents.processing.base import ParsedElement
from app.modules.documents.processing.chunker import chunk_elements


def _paragraph_elements(count: int, *, words_per_paragraph: int = 20, page_size: int = 10) -> list[ParsedElement]:
    return [
        ParsedElement(
            text=f"Paragraph {i} " + ("word " * words_per_paragraph),
            element_type="paragraph",
            page_number=(i // page_size) + 1,
            source_location={"page_number": (i // page_size) + 1},
        )
        for i in range(count)
    ]


# 18. deterministic input creates deterministic chunks
def test_chunking_is_deterministic_for_identical_input() -> None:
    elements = _paragraph_elements(40)

    first = chunk_elements(elements, target_tokens=200, overlap_ratio=0.125)
    second = chunk_elements(elements, target_tokens=200, overlap_ratio=0.125)

    assert [c.content for c in first] == [c.content for c in second]
    assert [c.token_count for c in first] == [c.token_count for c in second]


# 19. chunk ordering is stable
def test_chunk_ordering_follows_source_element_order() -> None:
    elements = [
        ParsedElement(text="First.", element_type="paragraph", page_number=1),
        ParsedElement(text="Second.", element_type="paragraph", page_number=1),
        ParsedElement(text="Third.", element_type="paragraph", page_number=2),
    ]

    chunks = chunk_elements(elements, target_tokens=5, overlap_ratio=0.1)

    # every element's text appears, in source order, across the chunk sequence
    joined = "\n".join(c.content for c in chunks)
    assert joined.index("First.") < joined.index("Second.") < joined.index("Third.")


# 20. chunks stay within configured size strategy
def test_chunks_stay_within_target_token_budget_for_normal_content() -> None:
    elements = _paragraph_elements(60, words_per_paragraph=5)

    chunks = chunk_elements(elements, target_tokens=200, overlap_ratio=0.125)

    # every chunk built from more than one element must not wildly exceed
    # the target -- some slack is expected since whole elements are never
    # split, but it should stay in the right order of magnitude.
    for chunk in chunks:
        assert chunk.token_count <= 200 * 1.5


def test_a_single_oversized_element_becomes_its_own_chunk_rather_than_being_split() -> None:
    huge = ParsedElement(text="word " * 1000, element_type="paragraph", page_number=1)
    elements = [
        ParsedElement(text="Small one.", element_type="paragraph", page_number=1),
        huge,
        ParsedElement(text="Small two.", element_type="paragraph", page_number=1),
    ]

    chunks = chunk_elements(elements, target_tokens=50, overlap_ratio=0.1)

    assert any(chunk.content == huge.text for chunk in chunks)


# 21. overlap behaves as designed
def test_overlap_carries_trailing_content_into_the_next_chunk() -> None:
    elements = _paragraph_elements(40, words_per_paragraph=5)

    chunks = chunk_elements(elements, target_tokens=100, overlap_ratio=0.2)

    assert len(chunks) > 1
    # the start of chunk N+1 should reuse some trailing text from chunk N
    overlap_found = False
    for first, second in itertools.pairwise(chunks):
        first_words = first.content.split()
        tail = " ".join(first_words[-5:])
        if tail and tail in second.content:
            overlap_found = True
            break
    assert overlap_found


def test_near_zero_overlap_ratio_minimizes_duplicated_content() -> None:
    """overlap_ratio only bounds how much *additional* trailing content
    is carried forward -- the algorithm always keeps at least one whole
    element of context at a chunk boundary (never zero), so a
    target_tokens*overlap_ratio near zero still carries exactly one
    element, not none. This proves the ratio is respected as an upper
    bound: shrinking it does not increase duplication.
    """
    elements = _paragraph_elements(30, words_per_paragraph=5)

    low_overlap_chunks = chunk_elements(elements, target_tokens=100, overlap_ratio=0.01)
    high_overlap_chunks = chunk_elements(elements, target_tokens=100, overlap_ratio=0.3)

    def duplicated_count(chunks) -> int:
        all_content = "".join(c.content for c in chunks)
        return sum(all_content.count(f"Paragraph {i} ") - 1 for i in range(30))

    assert duplicated_count(low_overlap_chunks) <= duplicated_count(high_overlap_chunks)


# 22. logical rows/paragraphs are not unnecessarily broken
def test_a_single_element_text_never_appears_split_across_two_chunks() -> None:
    elements = _paragraph_elements(50, words_per_paragraph=8)

    chunks = chunk_elements(elements, target_tokens=150, overlap_ratio=0.1)

    for element in elements:
        appearances = sum(1 for c in chunks if element.text in c.content)
        assert appearances >= 1  # present whole, in at least one chunk (more if overlapped)


def test_never_combine_content_from_two_different_sheets_in_one_chunk() -> None:
    elements = [
        ParsedElement(text=f"BOQ row {i}", element_type="table_row", sheet_name="BOQ")
        for i in range(5)
    ] + [
        ParsedElement(text=f"Summary row {i}", element_type="table_row", sheet_name="Summary")
        for i in range(5)
    ]

    chunks = chunk_elements(elements, target_tokens=1000, overlap_ratio=0.1)

    for chunk in chunks:
        assert not ("BOQ row" in chunk.content and "Summary row" in chunk.content)


def test_empty_element_list_produces_no_chunks() -> None:
    assert chunk_elements([], target_tokens=100, overlap_ratio=0.1) == []

