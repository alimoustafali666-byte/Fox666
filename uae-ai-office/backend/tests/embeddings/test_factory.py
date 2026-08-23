import pytest

from app.core.config import settings
from app.core.embeddings import factory
from app.core.embeddings.exceptions import EmbeddingConfigurationError
from app.core.embeddings.fake_provider import FakeEmbeddingProvider
from app.core.embeddings.voyage_provider import VoyageEmbeddingProvider
from app.modules.documents.models import EMBEDDING_VECTOR_DIMENSION


@pytest.fixture(autouse=True)
def _reset_provider_cache():
    factory.reset_embedding_provider_cache()
    yield
    factory.reset_embedding_provider_cache()


# 5. missing API configuration fails safely
def test_voyage_provider_with_no_api_key_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "voyage")
    monkeypatch.setattr(settings, "embedding_api_key", None)

    with pytest.raises(EmbeddingConfigurationError) as excinfo:
        factory.get_embedding_provider()

    assert "EMBEDDING_API_KEY" in str(excinfo.value)


# 4. configured provider created safely
def test_voyage_provider_with_full_config_builds_successfully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "voyage")
    monkeypatch.setattr(settings, "embedding_api_key", "a-real-key")
    monkeypatch.setattr(settings, "embedding_model", "voyage-3")
    monkeypatch.setattr(settings, "embedding_dimension", EMBEDDING_VECTOR_DIMENSION)

    provider = factory.get_embedding_provider()

    assert isinstance(provider, VoyageEmbeddingProvider)
    assert provider.dimension == EMBEDDING_VECTOR_DIMENSION


def test_fake_provider_selection_needs_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    monkeypatch.setattr(settings, "embedding_api_key", None)
    monkeypatch.setattr(settings, "embedding_dimension", EMBEDDING_VECTOR_DIMENSION)

    provider = factory.get_embedding_provider()

    assert isinstance(provider, FakeEmbeddingProvider)


def test_unknown_provider_name_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "openai")

    with pytest.raises(EmbeddingConfigurationError):
        factory.get_embedding_provider()


# 2. embedding dimension enforced correctly
def test_dimension_mismatch_against_schema_column_fails_safely(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "voyage")
    monkeypatch.setattr(settings, "embedding_api_key", "a-real-key")
    monkeypatch.setattr(settings, "embedding_dimension", EMBEDDING_VECTOR_DIMENSION + 1)

    with pytest.raises(EmbeddingConfigurationError) as excinfo:
        factory.get_embedding_provider()

    assert str(EMBEDDING_VECTOR_DIMENSION) in str(excinfo.value)


def test_get_embedding_provider_caches_the_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    monkeypatch.setattr(settings, "embedding_dimension", EMBEDDING_VECTOR_DIMENSION)

    first = factory.get_embedding_provider()
    second = factory.get_embedding_provider()

    assert first is second


def test_api_key_never_appears_in_configuration_error_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_provider", "voyage")
    monkeypatch.setattr(settings, "embedding_api_key", "a-real-key")
    monkeypatch.setattr(settings, "embedding_dimension", 1)

    with pytest.raises(EmbeddingConfigurationError) as excinfo:
        factory.get_embedding_provider()

    assert "a-real-key" not in str(excinfo.value)

