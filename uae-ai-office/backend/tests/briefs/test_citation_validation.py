from fastapi.testclient import TestClient

from app.core.llm.exceptions import LLMMalformedOutputError
from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import BriefGeneratedItem, BriefGenerationResult
from tests.briefs.helpers import regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _setup(client: TestClient, email: str) -> tuple[str, dict]:
    token, _ = signup(client, email)
    pdf_bytes = build_native_text_pdf_bytes(["New contract signed for AED 250,000 with ACME LLC."])
    document = upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)
    return token, document


def _valid_result(ref: str = "1") -> BriefGenerationResult:
    return BriefGenerationResult(
        summary="One new contract.",
        items=[BriefGeneratedItem(category="new_information", text="New contract signed.", priority=2, source_ref=ref)],
        model_identifier="fake-llm-v1",
        input_tokens=20,
        output_tokens=6,
    )


def test_valid_item_is_accepted_and_persisted_with_source_document(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, document = _setup(client, "brief-cite-valid@example.com")
    fake_llm_provider.enqueue_brief(_valid_result(ref="1"))

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["source_document_id"] == document["id"]


def test_fabricated_source_ref_invalidates_whole_batch_then_safe_fallback(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _document = _setup(client, "brief-cite-fabricated@example.com")
    fake_llm_provider.enqueue_brief(
        BriefGenerationResult(
            summary="bad",
            items=[BriefGeneratedItem(category="new_information", text="x", priority=2, source_ref="999")],
            model_identifier="fake-llm-v1", input_tokens=1, output_tokens=1,
        )
    )
    fake_llm_provider.enqueue_brief_error(LLMMalformedOutputError("still bad"))

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["items"] == []
    # exactly one corrective retry -- two attempts total, never a loop
    assert len(fake_llm_provider.brief_calls) == 2
    assert fake_llm_provider.brief_calls[1].corrective_note is not None


def test_invalid_category_invalidates_whole_batch(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _document = _setup(client, "brief-cite-bad-category@example.com")
    fake_llm_provider.enqueue_brief(
        BriefGenerationResult(
            summary="bad",
            items=[BriefGeneratedItem(category="not_a_real_category", text="x", priority=2, source_ref="1")],
            model_identifier="fake-llm-v1", input_tokens=1, output_tokens=1,
        )
    )
    fake_llm_provider.enqueue_brief_error(LLMMalformedOutputError("still bad"))

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    assert response.json()["items"] == []


def test_out_of_range_priority_invalidates_whole_batch(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _document = _setup(client, "brief-cite-bad-priority@example.com")
    fake_llm_provider.enqueue_brief(
        BriefGenerationResult(
            summary="bad",
            items=[BriefGeneratedItem(category="new_information", text="x", priority=9, source_ref="1")],
            model_identifier="fake-llm-v1", input_tokens=1, output_tokens=1,
        )
    )
    fake_llm_provider.enqueue_brief_error(LLMMalformedOutputError("still bad"))

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    assert response.json()["items"] == []


def test_malformed_output_recovers_on_corrective_retry(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _document = _setup(client, "brief-cite-recover@example.com")
    fake_llm_provider.enqueue_brief_error(LLMMalformedOutputError("bad json"))
    fake_llm_provider.enqueue_brief(_valid_result(ref="1"))

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert len(fake_llm_provider.brief_calls) == 2


def test_retries_are_bounded_to_configured_maximum(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _document = _setup(client, "brief-cite-bounded@example.com")
    for _ in range(5):
        fake_llm_provider.enqueue_brief_error(LLMMalformedOutputError("always bad"))

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    assert response.json()["items"] == []
    # brief_max_citation_retries=1 by default -> exactly 2 attempts, not 5.
    assert len(fake_llm_provider.brief_calls) == 2

