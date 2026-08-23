"""Raw-SQL RLS/FK proof for Step 11's three new tables -- exercises the
database policies directly, the same way test_document_chunks_isolation.py
and test_pgvector_isolation.py do for earlier tables, independent of any
application-layer filtering.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.session import set_company_context, set_user_context
from tests.db.conftest import TwoTenantSeed


def _insert_conversation(db_session: Session, *, company_id, created_by, title="t"):
    return db_session.execute(
        text(
            "INSERT INTO conversations (company_id, created_by, title) "
            "VALUES (:company_id, :created_by, :title) RETURNING id"
        ),
        {"company_id": company_id, "created_by": created_by, "title": title},
    ).scalar_one()


def _insert_message(db_session: Session, *, company_id, conversation_id, role="user", content="hi"):
    return db_session.execute(
        text(
            "INSERT INTO messages (company_id, conversation_id, role, content) "
            "VALUES (:company_id, :conversation_id, :role, :content) RETURNING id"
        ),
        {"company_id": company_id, "conversation_id": conversation_id, "role": role, "content": content},
    ).scalar_one()


def _insert_chunk(db_session: Session, *, company_id, document_id, chunk_index=0):
    return db_session.execute(
        text(
            "INSERT INTO document_chunks "
            "(company_id, document_id, chunk_index, content, content_hash) "
            "VALUES (:company_id, :document_id, :chunk_index, 'chunk text', 'hash') "
            "RETURNING id"
        ),
        {"company_id": company_id, "document_id": document_id, "chunk_index": chunk_index},
    ).scalar_one()


def _second_user(db_session: Session, *, company_id, email: str) -> None:
    user_id = db_session.execute(
        text("INSERT INTO users (email, password_hash) VALUES (:email, 'x') RETURNING id"),
        {"email": email},
    ).scalar_one()
    db_session.execute(
        text(
            "INSERT INTO company_members (company_id, user_id, role) "
            "VALUES (:company_id, :user_id, 'member')"
        ),
        {"company_id": company_id, "user_id": user_id},
    )
    return user_id


# 1. conversation migrations work -- proven by every test in this file and
# by tests/db/test_migrations.py's EXPECTED_TABLES round trip.


# 2. RLS isolates conversations by company
def test_company_a_cannot_read_company_b_conversations(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    _insert_conversation(db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a)

    set_company_context(db_session, two_tenants.company_b)
    set_user_context(db_session, two_tenants.user_b)
    _insert_conversation(db_session, company_id=two_tenants.company_b, created_by=two_tenants.user_b)

    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    rows = db_session.execute(text("SELECT company_id FROM conversations")).all()
    assert {r[0] for r in rows} == {two_tenants.company_a}


# RLS isolates conversations by creator, within the SAME company -- the
# Step 11 creator-private requirement, enforced at the database level.
def test_conversation_is_private_to_its_creator_within_same_company(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    other_user = _second_user(db_session, company_id=two_tenants.company_a, email="other@company-a.test")

    conversation_id = _insert_conversation(
        db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a
    )

    set_user_context(db_session, other_user)
    rows = db_session.execute(text("SELECT id FROM conversations")).all()
    assert rows == []

    set_user_context(db_session, two_tenants.user_a)
    rows = db_session.execute(text("SELECT id FROM conversations")).all()
    assert {r[0] for r in rows} == {conversation_id}


def test_missing_user_context_fails_closed_for_conversations(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    _insert_conversation(db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a)

    set_user_context(db_session, None)
    assert db_session.execute(text("SELECT id FROM conversations")).all() == []


# 3. RLS isolates messages (via the conversation's creator, the same way)
def test_messages_are_private_to_the_conversations_creator(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    other_user = _second_user(db_session, company_id=two_tenants.company_a, email="other2@company-a.test")
    conversation_id = _insert_conversation(
        db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a
    )
    _insert_message(db_session, company_id=two_tenants.company_a, conversation_id=conversation_id)

    set_user_context(db_session, other_user)
    assert db_session.execute(text("SELECT id FROM messages")).all() == []

    set_user_context(db_session, two_tenants.user_a)
    assert len(db_session.execute(text("SELECT id FROM messages")).all()) == 1


def test_company_a_cannot_read_company_b_messages(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    conversation_a = _insert_conversation(
        db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a
    )
    _insert_message(db_session, company_id=two_tenants.company_a, conversation_id=conversation_a)

    set_company_context(db_session, two_tenants.company_b)
    set_user_context(db_session, two_tenants.user_b)
    conversation_b = _insert_conversation(
        db_session, company_id=two_tenants.company_b, created_by=two_tenants.user_b
    )
    _insert_message(db_session, company_id=two_tenants.company_b, conversation_id=conversation_b)

    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    rows = db_session.execute(text("SELECT company_id FROM messages")).all()
    assert {r[0] for r in rows} == {two_tenants.company_a}


def test_message_cannot_reference_another_companys_conversation(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    """The composite FK on messages(conversation_id, company_id) exists as
    a structural backstop, but in practice messages' own RLS policy (an
    EXISTS against conversations, itself RLS-filtered) is the layer that
    actually fires first here: querying company_b's conversation while
    company_a's context is active returns no rows at all under RLS, so
    the INSERT is rejected as a row-security violation before the FK is
    even evaluated -- a stronger result than a bare FK check alone, and
    still "rejected", just via a different DBAPI error class than
    document_chunks' equivalent test (IntegrityError) sees.
    """
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    conversation_a = _insert_conversation(
        db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a
    )

    with pytest.raises((IntegrityError, DBAPIError)), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO messages (company_id, conversation_id, role, content) "
                "VALUES (:company_id, :conversation_id, 'user', 'evil')"
            ),
            {"company_id": two_tenants.company_b, "conversation_id": conversation_a},
        )


# 4. RLS isolates citations (via the message's conversation's creator)
def test_message_citations_are_private_to_the_conversations_creator(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    other_user = _second_user(db_session, company_id=two_tenants.company_a, email="other3@company-a.test")
    conversation_id = _insert_conversation(
        db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a
    )
    message_id = _insert_message(
        db_session, company_id=two_tenants.company_a, conversation_id=conversation_id, role="assistant"
    )
    chunk_id = _insert_chunk(
        db_session, company_id=two_tenants.company_a, document_id=two_tenants.document_a
    )
    db_session.execute(
        text(
            "INSERT INTO message_citations (company_id, message_id, document_chunk_id, citation_index) "
            "VALUES (:company_id, :message_id, :chunk_id, 0)"
        ),
        {"company_id": two_tenants.company_a, "message_id": message_id, "chunk_id": chunk_id},
    )

    set_user_context(db_session, other_user)
    assert db_session.execute(text("SELECT id FROM message_citations")).all() == []

    set_user_context(db_session, two_tenants.user_a)
    assert len(db_session.execute(text("SELECT id FROM message_citations")).all()) == 1


def test_citation_cannot_reference_another_companys_chunk(
    db_session: Session, two_tenants: TwoTenantSeed
) -> None:
    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    conversation_a = _insert_conversation(
        db_session, company_id=two_tenants.company_a, created_by=two_tenants.user_a
    )
    message_a = _insert_message(
        db_session, company_id=two_tenants.company_a, conversation_id=conversation_a, role="assistant"
    )

    set_company_context(db_session, two_tenants.company_b)
    set_user_context(db_session, two_tenants.user_b)
    chunk_b = _insert_chunk(db_session, company_id=two_tenants.company_b, document_id=two_tenants.document_b)

    set_company_context(db_session, two_tenants.company_a)
    set_user_context(db_session, two_tenants.user_a)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            text(
                "INSERT INTO message_citations (company_id, message_id, document_chunk_id, citation_index) "
                "VALUES (:company_id, :message_id, :chunk_id, 0)"
            ),
            {"company_id": two_tenants.company_a, "message_id": message_a, "chunk_id": chunk_b},
        )

