import math

from app.core.embeddings.fake_provider import FakeEmbeddingProvider


def test_dimension_matches_configured_value() -> None:
    provider = FakeEmbeddingProvider(dimension=1024)

    assert provider.dimension == 1024
    assert len(provider.embed_text("hello")) == 1024


def test_model_identifier_is_stable() -> None:
    provider = FakeEmbeddingProvider(dimension=8)

    assert provider.model_identifier == "fake-embedding-v1"


def test_embed_batch_returns_one_vector_per_input_in_order() -> None:
    provider = FakeEmbeddingProvider(dimension=16)

    vectors = provider.embed_batch(["concrete foundation", "steel beam", "concrete foundation"])

    assert len(vectors) == 3
    assert all(len(v) == 16 for v in vectors)
    # deterministic: identical text produces an identical vector
    assert vectors[0] == vectors[2]


def test_embed_text_is_deterministic() -> None:
    provider = FakeEmbeddingProvider(dimension=32)

    assert provider.embed_text("concrete") == provider.embed_text("concrete")


def test_similar_text_scores_higher_than_dissimilar_text() -> None:
    """Sanity check on the fake provider's own bag-of-words scheme: two
    texts sharing distinctive words must be closer (higher cosine
    similarity) than two texts sharing none -- this is what lets the
    rest of the suite assert real ranking behavior deterministically.
    """
    provider = FakeEmbeddingProvider(dimension=256)

    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    query = provider.embed_query("concrete foundation schedule")
    related = provider.embed_text("The concrete foundation was poured on schedule.")
    unrelated = provider.embed_text("Steel beam delivery invoice payment terms.")

    assert cosine(query, related) > cosine(query, unrelated)
    # vectors are unit-normalized
    assert math.isclose(sum(x * x for x in query), 1.0, abs_tol=1e-9)


def test_text_with_no_alphanumeric_content_produces_a_well_defined_unit_vector() -> None:
    provider = FakeEmbeddingProvider(dimension=8)

    vector = provider.embed_text("... !!! ???")

    assert len(vector) == 8
    assert sum(x * x for x in vector) > 0  # never an all-zero vector

