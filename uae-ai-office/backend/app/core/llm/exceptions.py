"""Typed exceptions for the LLM-provider abstraction. Mirrors
app.core.embeddings.exceptions' shape and rationale exactly: deliberately
NOT AppError subclasses (a lower-level infra concern), and no raise site
anywhere in this package or its provider implementations ever includes an
API key, an auth header, or a raw vendor response body in a message.
"""


class LLMError(Exception):
    error_code: str = "llm_failed"


class LLMUnavailable(LLMError):
    """Transient: connection/timeout/5xx-shaped failure, or a rate-limit
    response. The Anthropic SDK itself already retries connection errors
    and 429/5xx responses up to CLAUDE_MAX_RETRIES times before this is
    ever raised -- see anthropic_provider.py.
    """

    error_code = "llm_provider_unavailable"


class LLMAuthenticationError(LLMError):
    """The provider rejected the configured API key (401/403-shaped).
    Never retried -- a bad credential will fail identically every time.
    """

    error_code = "llm_provider_authentication_failed"


class LLMConfigurationError(LLMError):
    """Required configuration is missing or invalid (e.g. LLM_PROVIDER is
    'anthropic' but ANTHROPIC_API_KEY is not set)."""

    error_code = "llm_provider_misconfigured"


class LLMOperationError(LLMError):
    """Catch-all for a provider-reported failure that isn't authentication
    and isn't clearly transient -- e.g. a malformed/rejected request.
    """

    error_code = "llm_operation_failed"


class LLMMalformedOutputError(LLMError):
    """The provider responded, but its structured output did not parse
    into the required schema (invalid JSON, a missing/mismatched field, or
    a response truncated before valid structured output was produced).
    Distinct from LLMOperationError so callers can apply the Step 11
    at-most-once corrective retry specifically to this failure mode.
    """

    error_code = "llm_malformed_output"

