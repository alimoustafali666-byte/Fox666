import httpx
import pytest
import respx

from app.core.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingOperationError,
    EmbeddingUnavailable,
)
from app.core.embeddings.voyage_provider import VoyageEmbeddingProvider

API_KEY = "voyage-super-secret-key-should-never-leak-98765"


def _make_provider(dimension: int = 4) -> VoyageEmbeddingProvider:
    return VoyageEmbeddingProvider(api_key=API_KEY, model="voyage-3", dimension=dimension)


def _embedding_response(vectors: list[list[float]]) -> dict:
    return {
        "object": "list",
        "data": [{"object": "embedding", "embedding": v, "index": i} for i, v in enumerate(vectors)],
        "model": "voyage-3",
        "usage": {"total_tokens": 12},
    }


@respx.mock
def test_embed_batch_returns_vectors_in_request_order() -> None:
    provider = _make_provider()
    route = respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json=_embedding_response([[1, 0, 0, 0], [0, 1, 0, 0]]))
    )

    vectors = provider.embed_batch(["first", "second"])

    assert vectors == [[1, 0, 0, 0], [0, 1, 0, 0]]
    request_body = route.calls[0].request.content
    assert b"first" in request_body
    assert b"second" in request_body
    assert b"document" in request_body  # input_type for embed_batch/embed_text


@respx.mock
def test_embed_text_uses_document_input_type() -> None:
    provider = _make_provider()
    route = respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json=_embedding_response([[1, 0, 0, 0]]))
    )

    vector = provider.embed_text("a single document chunk")

    assert vector == [1, 0, 0, 0]
    assert b'"input_type":"document"' in route.calls[0].request.content


@respx.mock
def test_embed_query_uses_query_input_type() -> None:
    provider = _make_provider()
    route = respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json=_embedding_response([[0, 0, 1, 0]]))
    )

    vector = provider.embed_query("what is the concrete quantity")

    assert vector == [0, 0, 1, 0]
    assert b'"input_type":"query"' in route.calls[0].request.content


@respx.mock
def test_response_order_is_resorted_by_index_not_trusted() -> None:
    """Defends against a provider returning results out of order --
    the response's own `index` field is authoritative, not array position.
    """
    provider = _make_provider()
    out_of_order = {
        "object": "list",
        "data": [
            {"object": "embedding", "embedding": [0, 1, 0, 0], "index": 1},
            {"object": "embedding", "embedding": [1, 0, 0, 0], "index": 0},
        ],
        "model": "voyage-3",
    }
    respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json=out_of_order)
    )

    vectors = provider.embed_batch(["first", "second"])

    assert vectors == [[1, 0, 0, 0], [0, 1, 0, 0]]


# 18. provider response wrong vector count rejected
@respx.mock
def test_wrong_vector_count_in_response_is_rejected() -> None:
    provider = _make_provider()
    respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json=_embedding_response([[1, 0, 0, 0]]))  # only 1, asked for 2
    )

    with pytest.raises(EmbeddingOperationError):
        provider.embed_batch(["first", "second"])


# 19. provider response wrong dimension rejected
@respx.mock
def test_wrong_vector_dimension_in_response_is_rejected() -> None:
    provider = _make_provider(dimension=4)
    respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json=_embedding_response([[1, 0, 0]]))  # length 3, expected 4
    )

    with pytest.raises(EmbeddingOperationError):
        provider.embed_text("short vector")


@respx.mock
def test_authentication_failure_is_not_retried() -> None:
    provider = _make_provider()
    route = respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(401, json={"error": "invalid api key"})
    )

    with pytest.raises(EmbeddingAuthenticationError):
        provider.embed_text("anything")

    assert route.call_count == 1


@respx.mock
def test_transient_failure_is_retried_and_can_succeed() -> None:
    provider = _make_provider()
    respx.post("https://api.voyageai.com/v1/embeddings").mock(
        side_effect=[
            httpx.Response(503, json={"error": "temporarily unavailable"}),
            httpx.Response(200, json=_embedding_response([[1, 0, 0, 0]])),
        ]
    )

    vector = provider.embed_text("retry me")

    assert vector == [1, 0, 0, 0]


@respx.mock
def test_transient_failure_is_bounded_not_retried_forever() -> None:
    provider = _make_provider()
    route = respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(503, json={"error": "down"})
    )

    with pytest.raises(EmbeddingUnavailable):
        provider.embed_text("always down")

    assert route.call_count == 3  # bounded, not unlimited


@respx.mock
def test_malformed_request_failure_is_not_retried() -> None:
    provider = _make_provider()
    route = respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(400, json={"error": "bad request"})
    )

    with pytest.raises(EmbeddingOperationError):
        provider.embed_text("malformed")

    assert route.call_count == 1


# 6. API key never appears in logs/errors
@respx.mock
def test_api_key_never_appears_in_exception_text() -> None:
    provider = _make_provider()
    respx.post("https://api.voyageai.com/v1/embeddings").mock(
        return_value=httpx.Response(401, json={"error": "invalid api key"})
    )

    with pytest.raises(EmbeddingAuthenticationError) as excinfo:
        provider.embed_text("anything")

    assert API_KEY not in str(excinfo.value)
    assert API_KEY not in repr(excinfo.value)


def test_api_key_never_appears_in_provider_repr() -> None:
    provider = _make_provider()

    text = repr(provider)

    assert API_KEY not in text

