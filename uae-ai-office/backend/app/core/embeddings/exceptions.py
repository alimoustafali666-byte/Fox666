"""Typed exceptions for the embedding-provider abstraction. Mirrors
app.core.storage.exceptions' shape and rationale: these are deliberately
NOT AppError subclasses (a lower-level infra concern), and no raise site
anywhere in this package or its provider implementations ever includes
an API key, an auth header, or a raw vendor response body in a message.
"""


class EmbeddingError(Exception):
    error_code: str = "embedding_failed"


class EmbeddingUnavailable(EmbeddingError):
    """Transient: connection/timeout/5xx-shaped failure, or a rate-limit
    response worth one bounded retry. Never raised for an authentication
    or malformed-request failure -- see EmbeddingAuthenticationError and
    EmbeddingOperationError instead, neither of which is retried.
    """

    error_code = "embedding_provider_unavailable"


class EmbeddingAuthenticationError(EmbeddingError):
    """The provider rejected the configured API key (401/403-shaped).
    Never retried -- a bad credential will fail identically every time.
    """

    error_code = "embedding_provider_authentication_failed"


class EmbeddingConfigurationError(EmbeddingError):
    """Required configuration is missing or invalid -- including a
    configured/provider dimension that doesn't match
    app.modules.documents.models.EMBEDDING_VECTOR_DIMENSION, the fixed
    schema column width.
    """

    error_code = "embedding_provider_misconfigured"


class EmbeddingOperationError(EmbeddingError):
    """Catch-all for a provider-reported failure that isn't
    authentication and isn't clearly transient -- e.g. a malformed
    request, an unexpected response shape, or a returned vector count/
    dimension that doesn't match what was asked for.
    """

    error_code = "embedding_operation_failed"

