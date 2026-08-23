"""Proves the EmbeddingProvider abstraction is genuinely vendor-independent:
identical generic code, written only against the EmbeddingProvider
interface, works whether it runs against the fake provider or a
(respx-mocked) real Voyage provider. Nothing here imports
VoyageEmbeddingProvider or FakeEmbeddingProvider by name inside the
shared function -- only the abstract EmbeddingProvider type.
"""

import json

import httpx
import respx

from app.core.embeddings.fake_provider import FakeEmbeddingProvider
from app.core.embeddings.provider import EmbeddingProvider
from app.core.embeddings.voyage_provider import VoyageEmbeddingProvider


# 3. EmbeddingProvider abstraction is vendor-independent
def _round_trip(provider: EmbeddingProvider) -> bool:
    """Generic, provider-agnostic business logic: embed a batch, embed a
    single text, embed a query, and confirm every result matches the
    provider's declared dimension. Written purely against the
    EmbeddingProvider interface.
    """
    batch = provider.embed_batch(["first chunk", "second chunk"])
    single = provider.embed_text("a document")
    query = provider.embed_query("a search query")

    return (
        len(batch) == 2
        and all(len(v) == provider.dimension for v in batch)
        and len(single) == provider.dimension
        and len(query) == provider.dimension
        and isinstance(provider.model_identifier, str)
        and len(provider.model_identifier) > 0
    )


def test_generic_code_behaves_identically_against_the_fake_provider() -> None:
    provider: EmbeddingProvider = FakeEmbeddingProvider(dimension=16)

    assert _round_trip(provider) is True


@respx.mock
def test_generic_code_behaves_identically_against_a_mocked_voyage_provider() -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        n = len(body["input"])
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"object": "embedding", "embedding": [0.0] * 16, "index": i} for i in range(n)
                ],
                "model": "voyage-3",
            },
        )

    respx.post("https://api.voyageai.com/v1/embeddings").mock(side_effect=responder)

    provider: EmbeddingProvider = VoyageEmbeddingProvider(
        api_key="fake-key-for-vendor-independence-test", model="voyage-3", dimension=16
    )

    assert _round_trip(provider) is True

