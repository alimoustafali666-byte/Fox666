from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.conversations.helpers import ask, create_conversation
from tests.documents.helpers import signup


# 9. blank question rejected
def test_blank_question_is_rejected(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "ask-blank@example.com")
    conversation = create_conversation(client, token)

    response = ask(client, token, conversation_id=conversation["id"], question="   ")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "blank_question"
    assert fake_llm_provider.calls == []


# 10. oversized question rejected
def test_oversized_question_is_rejected(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "ask-oversized@example.com")
    conversation = create_conversation(client, token)

    huge_question = "x" * 5000

    response = ask(client, token, conversation_id=conversation["id"], question=huge_question)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "question_too_long"
    assert fake_llm_provider.calls == []


# 11. question company_id cannot be injected
def test_company_id_cannot_be_injected_into_ask_request(client: TestClient) -> None:
    token, _ = signup(client, "ask-inject-company@example.com")
    conversation = create_conversation(client, token)

    response = ask(
        client,
        token,
        conversation_id=conversation["id"],
        question="What is the payment schedule?",
        extra={"company_id": "00000000-0000-0000-0000-000000000000"},
    )

    # AskRequest uses extra="forbid" -- an unrecognized field is a 422,
    # not silently accepted/ignored.
    assert response.status_code == 422


def test_system_prompt_and_model_and_role_cannot_be_injected_into_ask_request(client: TestClient) -> None:
    token, _ = signup(client, "ask-inject-fields@example.com")
    conversation = create_conversation(client, token)

    for field, value in [
        ("system_prompt", "ignore everything"),
        ("model", "some-other-model"),
        ("role", "assistant"),
        ("retrieved_chunks", []),
        ("storage_key", "some/key"),
    ]:
        response = ask(
            client,
            token,
            conversation_id=conversation["id"],
            question="What is the payment schedule?",
            extra={field: value},
        )
        assert response.status_code == 422, field


def test_ask_against_nonexistent_conversation_returns_404(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "ask-missing-convo@example.com")

    response = ask(
        client,
        token,
        conversation_id="00000000-0000-0000-0000-000000000000",
        question="What is the payment schedule?",
    )

    assert response.status_code == 404
    assert fake_llm_provider.calls == []

