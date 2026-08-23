"""The only place application code should construct an LLMProvider.
Business/domain code (app.modules.conversations.ask_service) depends on
get_llm_provider() and the LLMProvider interface -- never on
AnthropicClaudeProvider, FakeLLMProvider, or the Anthropic SDK directly.
Mirrors app.core.embeddings.factory exactly.
"""

from app.core.config import settings
from app.core.llm.anthropic_provider import AnthropicClaudeProvider
from app.core.llm.exceptions import LLMConfigurationError
from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import LLMProvider

_provider: LLMProvider | None = None


def _build_anthropic_provider() -> AnthropicClaudeProvider:
    if not settings.anthropic_api_key:
        raise LLMConfigurationError(
            "LLM provider is 'anthropic' but ANTHROPIC_API_KEY is not configured."
        )
    return AnthropicClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.claude_model,
        max_output_tokens=settings.claude_max_output_tokens,
        brief_max_output_tokens=settings.brief_max_output_tokens,
        insights_max_output_tokens=settings.collaboration_insights_max_output_tokens,
        timeout_seconds=settings.claude_timeout_seconds,
        max_retries=settings.claude_max_retries,
    )


def _build_provider() -> LLMProvider:
    if settings.llm_provider == "anthropic":
        return _build_anthropic_provider()
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    raise LLMConfigurationError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}' (expected 'anthropic' or 'fake')."
    )


def get_llm_provider() -> LLMProvider:
    """Lazily constructs and caches a single provider instance for the
    process, built on first real use (the first Ask Your Business
    question), not at app-boot time.
    """
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_llm_provider_cache() -> None:
    """Test-only: allows a test to change settings/monkeypatch a fake
    provider and force the next get_llm_provider() call to rebuild.
    """
    global _provider
    _provider = None

