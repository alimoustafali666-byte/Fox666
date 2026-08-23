import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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
    """Same rolled-back-transaction pattern as tests/db/conftest.py, but
    with join_transaction_mode="create_savepoint": application code under
    test (the auth service) calls db.commit() for real, and that must not
    be allowed to escape this test's transaction. With this mode,
    session.commit()/rollback() operate on a SAVEPOINT nested inside the
    outer transaction, which is rolled back at teardown regardless of how
    many times the app "committed" during the test.
    """
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
    """login_rate_limiter is a process-wide singleton -- without this,
    failed-login attempts from one test would count against another.
    """
    login_rate_limiter.reset_all()
    yield
    login_rate_limiter.reset_all()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app, base_url="https://testserver")
    finally:
        app.dependency_overrides.pop(get_db, None)

