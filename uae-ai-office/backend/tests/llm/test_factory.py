import pytest

from app.core.config import settings
from app.core.llm import factory
from app.core.llm.anthropic_provider import AnthropicClaudeProvider
from app.core.llm.exceptions import LLMConfigurationError
from app.core.llm.fake_provider import FakeLLMProvider


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    yield
    factory.reset_llm_provider_cache()


def test_fake_provider_is_constructed_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "fake")
    factory.reset_llm_provider_cache()

    provider = factory.get_llm_provider()

    assert isinstance(provider, FakeLLMProvider)


def test_anthropic_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    factory.reset_llm_provider_cache()

    with pytest.raises(LLMConfigurationError):
        factory.get_llm_provider()


def test_anthropic_provider_is_constructed_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-key")
    factory.reset_llm_provider_cache()

    provider = factory.get_llm_provider()

    assert isinstance(provider, AnthropicClaudeProvider)


def test_unknown_provider_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "not-a-real-provider")
    factory.reset_llm_provider_cache()

    with pytest.raises(LLMConfigurationError):
        factory.get_llm_provider()


def test_provider_is_cached_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "llm_provider", "fake")
    factory.reset_llm_provider_cache()

    assert factory.get_llm_provider() is factory.get_llm_provider()

