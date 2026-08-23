from fastapi.testclient import TestClient

from app.core.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMOperationError,
    LLMUnavailable,
)
from app.core.llm.fake_provider import FakeLLMProvider
from tests.briefs.helpers import regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _setup(client: TestClient, email: str) -> str:
    token, _ = signup(client, email)
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(client, token, filename="terms.pdf", content=pdf_bytes)
    return token


def test_llm_unavailable_returns_safe_503_without_leaking_details(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token = _setup(client, "brief-provider-unavailable@example.com")
    fake_llm_provider.enqueue_brief_error(LLMUnavailable("simulated outage with vendor payload SECRET-9911"))

    response = regenerate_brief(client, token)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "brief_generation_unavailable"
    assert "SECRET-9911" not in response.text


def test_llm_authentication_failure_returns_safe_503(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token = _setup(client, "brief-provider-auth-fail@example.com")
    fake_llm_provider.enqueue_brief_error(LLMAuthenticationError("rejected key sk-ant-SECRET"))

    response = regenerate_brief(client, token)

    assert response.status_code == 503
    assert "sk-ant-SECRET" not in response.text


def test_llm_configuration_error_returns_safe_503(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token = _setup(client, "brief-provider-config-error@example.com")
    fake_llm_provider.enqueue_brief_error(LLMConfigurationError("missing ANTHROPIC_API_KEY"))

    response = regenerate_brief(client, token)

    assert response.status_code == 503


def test_llm_operation_error_returns_safe_503(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token = _setup(client, "brief-provider-op-error@example.com")
    fake_llm_provider.enqueue_brief_error(LLMOperationError("raw vendor response body leaked here"))

    response = regenerate_brief(client, token)

    assert response.status_code == 503
    assert "raw vendor response body" not in response.text


# unavailable/auth/config/operation failures are never retried -- only
# LLMMalformedOutputError gets the bounded corrective retry.
def test_provider_failure_is_not_retried(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token = _setup(client, "brief-provider-no-retry@example.com")
    fake_llm_provider.enqueue_brief_error(LLMUnavailable("outage"))

    response = regenerate_brief(client, token)

    assert response.status_code == 503
    assert len(fake_llm_provider.brief_calls) == 1

