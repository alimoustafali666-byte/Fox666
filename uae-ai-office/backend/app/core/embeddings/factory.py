"""The only place application code should construct an EmbeddingProvider.
Business/domain code (Step 10's indexing and retrieval) depends on
get_embedding_provider() and the EmbeddingProvider interface -- never on
VoyageEmbeddingProvider, FakeEmbeddingProvider, or an HTTP client directly.
"""

from app.core.config import settings
from app.core.embeddings.exceptions import EmbeddingConfigurationError
from app.core.embeddings.fake_provider import FakeEmbeddingProvider
from app.core.embeddings.provider import EmbeddingProvider
from app.core.embeddings.voyage_provider import VoyageEmbeddingProvider
from app.modules.documents.models import EMBEDDING_VECTOR_DIMENSION

_provider: EmbeddingProvider | None = None


def _build_voyage_provider() -> VoyageEmbeddingProvider:
    if not settings.embedding_api_key:
        raise EmbeddingConfigurationError(
            "Embedding provider is 'voyage' but EMBEDDING_API_KEY is not configured."
        )
    return VoyageEmbeddingProvider(
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )


def _build_provider() -> EmbeddingProvider:
    if settings.embedding_provider == "voyage":
        provider: EmbeddingProvider = _build_voyage_provider()
    elif settings.embedding_provider == "fake":
        provider = FakeEmbeddingProvider(dimension=settings.embedding_dimension)
    else:
        raise EmbeddingConfigurationError(
            f"Unknown EMBEDDING_PROVIDER '{settings.embedding_provider}' (expected 'voyage' or 'fake')."
        )

    # The pgvector column width (EMBEDDING_VECTOR_DIMENSION, fixed by
    # migration 0012) is the real constraint; EMBEDDING_DIMENSION is
    # only used to *configure* a provider, so a mismatch between the two
    # is a deployment misconfiguration caught here, immediately, rather
    # than surfacing as a confusing database error the first time an
    # embedding is actually inserted.
    if provider.dimension != EMBEDDING_VECTOR_DIMENSION:
        raise EmbeddingConfigurationError(
            f"Configured embedding dimension ({provider.dimension}) does not match "
            f"the database column width ({EMBEDDING_VECTOR_DIMENSION}). Changing the "
            f"embedding model/provider dimension requires a new migration."
        )

    return provider


def get_embedding_provider() -> EmbeddingProvider:
    """Lazily constructs and caches a single provider instance for the
    process -- mirrors app.core.storage.factory.get_storage_provider.
    Constructed on first real use (Step 10's indexing/retrieval), not at
    app-boot time, so a deployment that never touches embeddings never
    needs one configured, and a misconfiguration fails clearly the first
    time it's actually needed.
    """
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def reset_embedding_provider_cache() -> None:
    """Test-only: allows a test to change settings and force the next
    get_embedding_provider() call to rebuild rather than reuse a cached
    instance from an earlier test/configuration.
    """
    global _provider
    _provider = None

