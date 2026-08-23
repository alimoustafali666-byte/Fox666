from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.briefs.helpers import get_brief, regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def test_full_brief_generation_smoke(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "brief-smoke@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["New contract signed for AED 250,000 with ACME LLC."])
    upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["summary"]
    assert len(body["items"]) >= 1
    assert body["items"][0]["source_document_id"] is not None

    fetched = get_brief(client, token)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_no_documents_returns_template_without_calling_llm(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "brief-empty@example.com")

    response = regenerate_brief(client, token)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["items"] == []
    assert fake_llm_provider.brief_calls == []

