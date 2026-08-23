from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.conversations.helpers import ask, create_conversation, get_conversation, list_messages
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def test_full_ask_flow_smoke(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "ask-smoke@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Contract Value: AED 125000 for the concrete works."])
    upload_process_and_index(client, token, filename="contract.pdf", content=pdf_bytes)

    conversation = create_conversation(client, token, title="Smoke test")
    response = ask(client, token, conversation_id=conversation["id"], question="What is the contract value?")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "assistant"
    assert body["is_sufficient"] is True
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["file_name"] == "contract.pdf"

    convo = get_conversation(client, token, conversation["id"])
    assert convo.status_code == 200

    messages = list_messages(client, token, conversation["id"])
    assert messages.status_code == 200
    items = messages.json()["items"]
    assert len(items) == 2

