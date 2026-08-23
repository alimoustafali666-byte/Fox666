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
from app.modules.collaboration.rate_limit import ai_insights_rate_limiter, message_send_rate_limiter

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
def _reset_rate_limiters() -> Iterator[None]:
    login_rate_limiter.reset_all()
    message_send_rate_limiter.reset_all()
    ai_insights_rate_limiter.reset_all()
    yield
    login_rate_limiter.reset_all()
    message_send_rate_limiter.reset_all()
    ai_insights_rate_limiter.reset_all()


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
    monkeypatch.setattr(settings, "llm_provider", "fake")
    llm_factory.reset_llm_provider_cache()
    provider = llm_factory.get_llm_provider()
    assert isinstance(provider, FakeLLMProvider)
    yield provider
    llm_factory.reset_llm_provider_cache()


@pytest.fixture()
def client(db_session: Session, fake_llm_provider: FakeLLMProvider, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # app.modules.collaboration.ws opens its own short-lived sessions
    # directly (never via the get_db dependency, since a WebSocket
    # connection isn't a single per-request FastAPI dependency scope) --
    # each one would otherwise be a genuinely separate connection to the
    # real database and never see this test's uncommitted transaction.
    # Overridden the same way override_get_db above hands routers the
    # test's own session instead of a fresh one.
    #
    # A lock serializes access: TestClient runs each open WebSocket
    # connection on its own background thread, and a real test may hold
    # several open at once (e.g. to prove an event reaches one peer but
    # not another) -- SQLAlchemy Sessions are not safe for concurrent use
    # from multiple threads, and without this a genuinely simultaneous
    # request from two connections' receive loops can corrupt shared
    # connection/cursor state and hang. Production never shares a
    # session across connections this way (each gets its own short-lived
    # one against the real database), so this constraint is test-only.
    import threading
    from contextlib import contextmanager

    from app.modules.collaboration import ws as collaboration_ws

    lock = threading.Lock()

    @contextmanager
    def override_short_lived_session() -> Iterator[Session]:
        with lock:
            yield db_session

    monkeypatch.setattr(collaboration_ws, "_short_lived_session", override_short_lived_session)

    # Used as a context manager (not bare TestClient(app)) specifically
    # so TestClient.portal gets set once, up front: every
    # websocket_connect() call then shares that ONE portal (one
    # background thread, one event loop) instead of each spinning up its
    # own -- see TestClient._portal_factory. Without this, two
    # simultaneously-open WebSocket connections in the same test run on
    # DIFFERENT event loops, and this module's server-side code
    # `await`ing one connection's send from the coroutine handling
    # another's incoming message becomes a cross-event-loop await, which
    # hangs indefinitely rather than erroring -- confirmed by reproducing
    # exactly that hang before adding this.
    try:
        with TestClient(app, base_url="https://testserver") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)

