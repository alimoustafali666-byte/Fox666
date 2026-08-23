from fastapi.testclient import TestClient

from app.core.llm.exceptions import (
    LLMAuthenticationError,
    LLMOperationError,
    LLMUnavailable,
)
from app.core.llm.fake_provider import FakeLLMProvider
from tests.conversations.helpers import ask, create_conversation
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _setup(client: TestClient, email: str):
    token, _ = signup(client, email)
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(client, token)
    return token, conversation


# 42. provider failure handled safely
def test_llm_unavailable_returns_safe_503_without_leaking_details(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, conversation = _setup(client, "provider-unavailable@example.com")
    fake_llm_provider.enqueue_error(LLMUnavailable("simulated outage with vendor payload SECRET-9911"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ask_unavailable"
    assert "SECRET-9911" not in response.text


def test_llm_authentication_failure_returns_safe_503(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, conversation = _setup(client, "provider-auth-fail@example.com")
    fake_llm_provider.enqueue_error(LLMAuthenticationError("rejected key sk-ant-SECRET"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 503
    assert "sk-ant-SECRET" not in response.text


def test_llm_operation_error_returns_safe_503(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, conversation = _setup(client, "provider-op-error@example.com")
    fake_llm_provider.enqueue_error(LLMOperationError("raw vendor response body leaked here"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 503
    assert "raw vendor response body" not in response.text


# 43. provider timeout bounded -- the timeout itself is enforced by the
# Anthropic SDK client construction (claude_timeout_seconds, passed
# through in AnthropicClaudeProvider.__init__), not re-implemented here;
# this proves a timeout-shaped failure is handled exactly like any other
# LLMUnavailable, never left to hang or surfaced as a raw exception.
def test_llm_timeout_is_handled_as_unavailable(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, conversation = _setup(client, "provider-timeout@example.com")
    fake_llm_provider.enqueue_error(LLMUnavailable("request timed out"))

    response = ask(client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 503


def test_claude_timeout_seconds_configures_anthropic_client() -> None:
    from app.core.llm.anthropic_provider import AnthropicClaudeProvider

    provider = AnthropicClaudeProvider(
        api_key="sk-ant-irrelevant",
        model="claude-sonnet-5",
        max_output_tokens=100,
        brief_max_output_tokens=200,
        insights_max_output_tokens=200,
        timeout_seconds=12.5,
        max_retries=1,
    )
    assert provider._client.timeout == 12.5
    assert provider._client.max_retries == 1

