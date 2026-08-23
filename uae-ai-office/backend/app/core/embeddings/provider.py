"""The abstraction every future module needing text embeddings depends
on. Business/domain code (Step 10's indexing and retrieval, and
whatever needs embeddings after it) must never import a vendor SDK or
call a vendor HTTP API directly -- only this interface and the factory
that resolves it from configuration (app.core.embeddings.factory.
get_embedding_provider).

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Every string passed to
embed_text/embed_batch/embed_query is untrusted content (extracted
document text, or a user's search query) -- embedding it is a pure,
side-effect-free transformation into a vector; it must never be
interpreted as an instruction by this layer or by any provider
implementation.
"""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        """The fixed length of every vector this provider returns.
        Validated against app.modules.documents.models.
        EMBEDDING_VECTOR_DIMENSION (the actual pgvector column width) at
        construction time -- a provider/model whose dimension doesn't
        match is a configuration error, not something silently coerced.
        """

    @property
    @abstractmethod
    def model_identifier(self) -> str:
        """The exact model name/version, stored per-chunk
        (DocumentChunk.embedding_model) so a future model change is
        detectable rather than silently mixing incompatible vector
        spaces.
        """

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embeds `texts` for later retrieval (i.e. as *documents*, for
        providers that distinguish document vs. query encoding).
        Returns exactly one vector per input text, in the same order,
        each of length `dimension` -- callers must validate both; a
        provider implementation that can't guarantee this raises
        EmbeddingOperationError rather than let a caller receive a
        mismatched response silently. Bounded by the caller into batches
        (see app.core.config.settings.embedding_batch_size); this method
        itself does not chunk an oversized list further.
        """

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Single-text convenience form of embed_batch."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embeds a *search query* -- kept distinct from embed_text/
        embed_batch because some providers (Voyage included) use
        asymmetric encoding that measurably improves retrieval quality
        when queries and documents are embedded with different input
        modes, even though both still produce a `dimension`-length
        vector in the same space and are safe to compare against each
        other. A provider that has no such distinction can simply alias
        this to embed_text.
        """

