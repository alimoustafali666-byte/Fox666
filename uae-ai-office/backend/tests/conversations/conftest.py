import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings import factory as embedding_factory
from app.core.llm import factory as llm_factory
from app.core.llm.fake_provider import FakeLLMProvider
from app.core.storage import factory as storage_factory
from app.db.session import get_db
from app.main import app
from app.modules.auth.rate_limit import login_rate_limiter

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://uae_app:uae_app@localhost:5432/uae_ai_office_test",
)


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Iterator[Session]:
    connection = db_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    login_rate_limiter.reset_all()
    yield
    login_rate_limiter.reset_all()


@pytest.fixture(autouse=True)
def _fake_storage_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "storage_provider", "fake")
    storage_factory.reset_storage_provider_cache()
    yield
    storage_factory.reset_storage_provider_cache()


@pytest.fixture(autouse=True)
def _fake_embedding_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    embedding_factory.reset_embedding_provider_cache()
    yield
    embedding_factory.reset_embedding_provider_cache()


@pytest.fixture()
def fake_llm_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeLLMProvider]:
    """Ask Your Business tests never talk to the real Anthropic API:
    LLM_PROVIDER is forced to "fake" (app.core.llm.fake_provider) and the
    process-wide provider singleton is reset before and after every test.
    Yields the FakeLLMProvider instance itself so a test can `.enqueue(...)`
    a scripted response/error, or inspect `.calls` to prove (or disprove)
    that the provider was invoked at all.
    """
    monkeypatch.setattr(settings, "llm_provider", "fake")
    llm_factory.reset_llm_provider_cache()
    provider = llm_factory.get_llm_provider()
    assert isinstance(provider, FakeLLMProvider)
    yield provider
    llm_factory.reset_llm_provider_cache()


@pytest.fixture()
def client(db_session: Session, fake_llm_provider: FakeLLMProvider) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app, base_url="https://testserver")
    finally:
        app.dependency_overrides.pop(get_db, None)

