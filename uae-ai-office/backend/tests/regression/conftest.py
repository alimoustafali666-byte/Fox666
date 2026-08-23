"""Fixtures for tests/regression/test_multi_commit_rls_context.py.

Every other test suite in this repo shares ONE Session, bound to one
already-open connection, for the whole test -- either directly
(tests/db/) or via join_transaction_mode="create_savepoint" (every
tests/<module>/conftest.py's `client` fixture). That is deliberate and
correct for testing business logic in isolation, but it means an
app-level db.commit() never actually ends the real Postgres transaction
-- SAVEPOINT RELEASE, not COMMIT -- so it can never reproduce (or prove
the fix for) a bug that only exists when a *real* commit clears
transaction-local RLS context. See app.db.session's after_begin listener
and tests/tenancy/test_rls_transaction_safety.py for the mechanism.

This module's fixtures instead give each HTTP request its own fresh
Session bound to a real engine -- exactly what app.db.session.get_db()
does in production -- against a dedicated scratch database so these
real commits never touch (or pollute) the shared dev/test database.
"""

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.embeddings import factory as embedding_factory
from app.core.llm import factory as llm_factory
from app.core.storage import factory as storage_factory
from app.db.session import get_db
from app.main import app
from app.modules.auth.rate_limit import login_rate_limiter

ADMIN_DATABASE_URL = os.environ.get(
    "TEST_ADMIN_DATABASE_URL",
    "postgresql+psycopg://uae_app:uae_app@localhost:5432/postgres",
)
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _run_alembic(*args: str, database_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env={"PATH": "/usr/bin:/bin", "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module")
def scratch_database_url() -> Iterator[str]:
    """A freshly-migrated, module-scoped scratch database -- created and
    dropped just for this test module, mirroring
    tests/db/test_migrations.py's pattern exactly (uae_app has CREATEDB
    for this reason). Nothing this module does is ever visible to, or
    left behind for, any other test file or a human inspecting the
    shared dev database afterward.
    """
    scratch_db = f"uae_ai_office_txtest_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{scratch_db}"'))

        scratch_url = f"postgresql+psycopg://uae_app:uae_app@localhost:5432/{scratch_db}"
        result = _run_alembic("upgrade", "head", database_url=scratch_url)
        assert result.returncode == 0, result.stderr

        yield scratch_url
    finally:
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": scratch_db},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
        admin_engine.dispose()


def _install_real_get_db(engine: Engine) -> None:
    """Overrides get_db with one that mirrors app.db.session.get_db()
    exactly -- a brand new Session per call, bound to a real engine, torn
    down with a real rollback()+close(). This is the one thing that
    matters: FastAPI invokes a Depends() callable fresh for every
    request, so every request in a test using this override gets its own
    Session, its own transaction, and its own real commit()/rollback()
    boundaries, precisely reproducing production request-handling instead
    of the shared-session fixtures used everywhere else in this suite.
    """
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.rollback()
            db.close()

    app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> Iterator[None]:
    login_rate_limiter.reset_all()
    yield
    login_rate_limiter.reset_all()


@pytest.fixture(autouse=True)
def _fake_providers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No real S3/Voyage/Anthropic calls -- same fake-provider posture as
    every other API-level test suite (tests/documents/conftest.py,
    tests/briefs/conftest.py, ...); this module is about the RLS/
    transaction bug, not provider behavior.
    """
    monkeypatch.setattr(settings, "storage_provider", "fake")
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    monkeypatch.setattr(settings, "llm_provider", "fake")
    storage_factory.reset_storage_provider_cache()
    embedding_factory.reset_embedding_provider_cache()
    llm_factory.reset_llm_provider_cache()
    yield
    storage_factory.reset_storage_provider_cache()
    embedding_factory.reset_embedding_provider_cache()
    llm_factory.reset_llm_provider_cache()


@pytest.fixture()
def real_client(scratch_database_url: str) -> Iterator[TestClient]:
    """Default pool sizing (i.e. more than one connection can exist) --
    use `real_client_single_connection` instead when a test specifically
    needs to force connection reuse across requests.
    """
    engine = create_engine(scratch_database_url, pool_pre_ping=True)
    _install_real_get_db(engine)
    try:
        yield TestClient(app, base_url="https://testserver")
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@dataclass
class SingleConnectionClient:
    client: TestClient
    # Exposed so a test can open its own probe Session directly against
    # this SAME engine after issuing HTTP requests -- with pool_size=1
    # that probe is GUARANTEED to reuse the exact physical connection the
    # app's requests just used, not merely "some fresh connection to the
    # same database" (a weaker check a separate engine could only offer).
    engine: Engine


@pytest.fixture()
def real_client_single_connection(scratch_database_url: str) -> Iterator[SingleConnectionClient]:
    """pool_size=1, max_overflow=0: only one underlying connection can
    ever exist, so any two sequential (non-overlapping) requests are
    GUARANTEED to reuse the exact same one -- proving "no leakage" means
    the checkin/checkout cycle itself is safe, not just that two requests
    happened to land on different connections. Mirrors
    tests/tenancy/test_rls_transaction_safety.py's engine config, applied
    here at the real HTTP/app layer instead of directly against
    app.db.session's functions.
    """
    engine = create_engine(scratch_database_url, pool_size=1, max_overflow=0)
    _install_real_get_db(engine)
    try:
        yield SingleConnectionClient(client=TestClient(app, base_url="https://testserver"), engine=engine)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()

