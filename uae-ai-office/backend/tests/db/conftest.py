import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.session import set_company_context

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
    """A session bound to its own transaction, rolled back after the test.

    Every table used in these tests has RLS FORCE-enabled, including for
    the owning role, so this deliberately does NOT connect as a superuser
    -- it exercises the exact policies the application will run under.
    """
    connection = db_engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@dataclass
class TwoTenantSeed:
    company_a: uuid.UUID
    company_b: uuid.UUID
    user_a: uuid.UUID
    user_b: uuid.UUID
    project_a: uuid.UUID
    project_b: uuid.UUID
    document_a: uuid.UUID
    document_b: uuid.UUID


@pytest.fixture()
def two_tenants(db_session: Session) -> TwoTenantSeed:
    """Seeds two independent companies, each with a user, a project, and a
    document attached to that project -- the baseline fixture every
    cross-tenant isolation test builds on.
    """
    company_a = db_session.execute(
        text("INSERT INTO companies (name) VALUES ('Company A') RETURNING id")
    ).scalar_one()
    company_b = db_session.execute(
        text("INSERT INTO companies (name) VALUES ('Company B') RETURNING id")
    ).scalar_one()

    # users has no RLS (global identity table) -- no context needed.
    user_a = db_session.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('a@company-a.test', 'x') RETURNING id"
        )
    ).scalar_one()
    user_b = db_session.execute(
        text(
            "INSERT INTO users (email, password_hash) "
            "VALUES ('b@company-b.test', 'x') RETURNING id"
        )
    ).scalar_one()

    set_company_context(db_session, company_a)
    project_a = db_session.execute(
        text(
            "INSERT INTO projects (company_id, name) "
            "VALUES (:company_id, 'Project A') RETURNING id"
        ),
        {"company_id": company_a},
    ).scalar_one()
    document_a = db_session.execute(
        text(
            "INSERT INTO documents "
            "(company_id, project_id, uploaded_by, file_name, file_type, "
            " file_size_bytes, storage_key, checksum_sha256) "
            "VALUES (:company_id, :project_id, :uploaded_by, 'a.pdf', 'pdf', "
            " 100, 'company-a/a.pdf', 'deadbeef') RETURNING id"
        ),
        {"company_id": company_a, "project_id": project_a, "uploaded_by": user_a},
    ).scalar_one()
    db_session.execute(
        text(
            "INSERT INTO company_members (company_id, user_id, role) "
            "VALUES (:company_id, :user_id, 'owner')"
        ),
        {"company_id": company_a, "user_id": user_a},
    )
    db_session.execute(
        text(
            "INSERT INTO audit_logs (company_id, actor_user_id, action, resource_type) "
            "VALUES (:company_id, :actor_user_id, 'document.upload', 'document')"
        ),
        {"company_id": company_a, "actor_user_id": user_a},
    )

    set_company_context(db_session, company_b)
    project_b = db_session.execute(
        text(
            "INSERT INTO projects (company_id, name) "
            "VALUES (:company_id, 'Project B') RETURNING id"
        ),
        {"company_id": company_b},
    ).scalar_one()
    document_b = db_session.execute(
        text(
            "INSERT INTO documents "
            "(company_id, project_id, uploaded_by, file_name, file_type, "
            " file_size_bytes, storage_key, checksum_sha256) "
            "VALUES (:company_id, :project_id, :uploaded_by, 'b.pdf', 'pdf', "
            " 100, 'company-b/b.pdf', 'cafebabe') RETURNING id"
        ),
        {"company_id": company_b, "project_id": project_b, "uploaded_by": user_b},
    ).scalar_one()
    db_session.execute(
        text(
            "INSERT INTO company_members (company_id, user_id, role) "
            "VALUES (:company_id, :user_id, 'owner')"
        ),
        {"company_id": company_b, "user_id": user_b},
    )
    db_session.execute(
        text(
            "INSERT INTO audit_logs (company_id, actor_user_id, action, resource_type) "
            "VALUES (:company_id, :actor_user_id, 'document.upload', 'document')"
        ),
        {"company_id": company_b, "actor_user_id": user_b},
    )

    db_session.flush()

    # Seeding is done as an internal setup step; hand the test a session
    # with NO company context active, exactly like a fresh request before
    # auth middleware has run. Tests that need a context set one
    # explicitly via set_company_context().
    set_company_context(db_session, None)

    return TwoTenantSeed(
        company_a=company_a,
        company_b=company_b,
        user_a=user_a,
        user_b=user_b,
        project_a=project_a,
        project_b=project_b,
        document_a=document_a,
        document_b=document_b,
    )

