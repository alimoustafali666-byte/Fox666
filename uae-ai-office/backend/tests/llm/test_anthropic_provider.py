"""Unit tests for AnthropicClaudeProvider's request construction, response
parsing, and exception mapping.

This environment's `anthropic` SDK build talks over `httpx2` (a sandbox-
specific fork), not the plain `httpx` respx patches, and outbound HTTPS
in this sandbox goes through a proxy to the real API -- so transport-level
mocking (the pattern tests/embeddings/test_voyage_provider.py uses via
respx against Voyage's raw httpx calls) isn't available here without
depending on httpx2 internals. Instead, these tests monkeypatch
`client.messages.parse` directly (the one call this provider ever makes),
which still fully exercises this module's own logic: request construction
(what's sent), response extraction, and every typed-exception mapping --
everything this module is actually responsible for. What is NOT verified
here, disclosed explicitly (mirrors the Step 10 Voyage disclosure): the
real Anthropic API's actual request/response contract, since this
environment has no API key and no verified network path to it.
"""

import anthropic
import httpx2
import pytest
from pydantic import ValidationError

from app.core.llm.anthropic_provider import AnthropicClaudeProvider, _ClaudeStructuredAnswer
from app.core.llm.exceptions import (
    LLMAuthenticationError,
    LLMMalformedOutputError,
    LLMOperationError,
    LLMUnavailable,
)
from app.core.llm.provider import DocumentContextItem, GroundedAnswerRequest

API_KEY = "sk-ant-super-secret-key-should-never-leak-13579"


def _provider() -> AnthropicClaudeProvider:
    return AnthropicClaudeProvider(
        api_key=API_KEY, model="claude-sonnet-5", max_output_tokens=200, brief_max_output_tokens=400,
        insights_max_output_tokens=400,
        timeout_seconds=5.0, max_retries=0,
    )


def _request() -> GroundedAnswerRequest:
    return GroundedAnswerRequest(
        question="What is the contract value?",
        document_context=[DocumentContextItem(ref="1", content="Contract Value: AED 125000.")],
    )


def _fake_response(*, answer: str, sufficient: bool, refs: list[str], model="claude-sonnet-5"):
    class _Usage:
        input_tokens = 42
        output_tokens = 8

    class _Response:
        pass

    parsed = _ClaudeStructuredAnswer(
        answer=answer, sufficient=sufficient, citations=[{"ref": r} for r in refs]
    )
    response = _Response()
    response.parsed_output = parsed
    response.model = model
    response.usage = _Usage()
    return response


def _status_error(cls, status_code: int, body: dict) -> Exception:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status_code, request=request, json=body)
    return cls(f"Error {status_code}", response=response, body=body)


def test_successful_structured_response_is_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    monkeypatch.setattr(
        provider._client.messages,
        "parse",
        lambda **_: _fake_response(answer="AED 125,000.", sufficient=True, refs=["1"]),
    )

    result = provider.generate_grounded_answer(_request())

    assert result.answer == "AED 125,000."
    assert result.sufficient is True
    assert result.citations[0].ref == "1"
    assert result.model_identifier == "claude-sonnet-5"
    assert result.input_tokens == 42
    assert result.output_tokens == 8


def test_authentication_failure_maps_to_llm_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    error = _status_error(
        anthropic.AuthenticationError, 401, {"error": {"type": "authentication_error", "message": "bad key"}}
    )

    def boom(**_):
        raise error

    monkeypatch.setattr(provider._client.messages, "parse", boom)

    with pytest.raises(LLMAuthenticationError):
        provider.generate_grounded_answer(_request())


def test_rate_limit_maps_to_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    error = _status_error(
        anthropic.RateLimitError, 429, {"error": {"type": "rate_limit_error", "message": "slow down"}}
    )

    def boom(**_):
        raise error

    monkeypatch.setattr(provider._client.messages, "parse", boom)

    with pytest.raises(LLMUnavailable):
        provider.generate_grounded_answer(_request())


def test_server_error_maps_to_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    error = _status_error(
        anthropic.InternalServerError, 500, {"error": {"type": "api_error", "message": "oops"}}
    )

    def boom(**_):
        raise error

    monkeypatch.setattr(provider._client.messages, "parse", boom)

    with pytest.raises(LLMUnavailable):
        provider.generate_grounded_answer(_request())


def test_bad_request_maps_to_llm_operation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    error = _status_error(
        anthropic.BadRequestError, 400, {"error": {"type": "invalid_request_error", "message": "bad"}}
    )

    def boom(**_):
        raise error

    monkeypatch.setattr(provider._client.messages, "parse", boom)

    with pytest.raises(LLMOperationError):
        provider.generate_grounded_answer(_request())


def test_timeout_maps_to_llm_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

    def boom(**_):
        raise anthropic.APITimeoutError(request=request)

    monkeypatch.setattr(provider._client.messages, "parse", boom)

    with pytest.raises(LLMUnavailable):
        provider.generate_grounded_answer(_request())


def test_schema_validation_failure_maps_to_malformed_output_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()

    def boom(**_):
        raise ValidationError.from_exception_data("test", [])

    monkeypatch.setattr(provider._client.messages, "parse", boom)

    with pytest.raises(LLMMalformedOutputError):
        provider.generate_grounded_answer(_request())


def test_none_parsed_output_maps_to_malformed_output_error(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider()

    class _Response:
        parsed_output = None

    monkeypatch.setattr(provider._client.messages, "parse", lambda **_: _Response())

    with pytest.raises(LLMMalformedOutputError):
        provider.generate_grounded_answer(_request())


def test_request_sends_question_and_document_context_as_a_user_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider()
    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return _fake_response(answer="AED 125,000.", sufficient=True, refs=["1"])

    monkeypatch.setattr(provider._client.messages, "parse", capture)

    provider.generate_grounded_answer(_request())

    assert captured["model"] == "claude-sonnet-5"
    assert captured["max_tokens"] == 200
    assert "system" in captured  # separate from the user message
    user_message = captured["messages"][0]
    assert user_message["role"] == "user"
    assert "Contract Value: AED 125000" in user_message["content"]
    assert "What is the contract value?" in user_message["content"]
    # the system prompt itself never appears inside the user content
    assert captured["system"] not in user_message["content"]


def test_api_key_never_appears_in_repr() -> None:
    provider = _provider()
    assert API_KEY not in repr(provider)
    assert API_KEY not in str(provider)

