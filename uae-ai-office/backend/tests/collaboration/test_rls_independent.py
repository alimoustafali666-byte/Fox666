"""RLS tested independently of application filtering, per the spec's
explicit requirement: these tests issue raw SQL directly against the
database session, completely bypassing app.modules.collaboration.service
and repository, to prove tenant/membership isolation is enforced by
Postgres itself -- not merely by an application-layer WHERE clause that
a future bug could remove.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import set_company_context, set_user_context
from app.modules.auth.models import User
from app.modules.tenancy.models import CompanyMember


def _make_user(db_session: Session, email: str) -> User:
    user = User(email=email, password_hash=hash_password("x"), full_name="RLS Test")
    db_session.add(user)
    db_session.flush()
    return user


def test_raw_sql_cannot_read_cross_company_conversation(db_session: Session) -> None:
    from app.modules.tenancy.models import Company

    company_a = Company(name="Company A")
    company_b = Company(name="Company B")
    db_session.add_all([company_a, company_b])
    db_session.flush()

    alice = _make_user(db_session, "rls1a@example.com")
    eve = _make_user(db_session, "rls1e@example.com")

    set_company_context(db_session, company_a.id)
    set_user_context(db_session, alice.id)
    db_session.add(CompanyMember(company_id=company_a.id, user_id=alice.id, role="owner"))
    db_session.flush()

    conv_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO chat_conversations (id, company_id, type, created_by) "
            "VALUES (:id, :company_id, 'group', :created_by)"
        ),
        {"id": conv_id, "company_id": company_a.id, "created_by": alice.id},
    )
    db_session.execute(
        text(
            "INSERT INTO chat_conversation_active_members (id, company_id, conversation_id, user_id) "
            "VALUES (gen_random_uuid(), :company_id, :conversation_id, :user_id)"
        ),
        {"company_id": company_a.id, "conversation_id": conv_id, "user_id": alice.id},
    )

    # Switch to Eve, a member of a completely different company.
    set_company_context(db_session, company_b.id)
    set_user_context(db_session, eve.id)
    db_session.add(CompanyMember(company_id=company_b.id, user_id=eve.id, role="owner"))
    db_session.flush()

    rows = db_session.execute(text("SELECT id FROM chat_conversations WHERE id = :id"), {"id": conv_id}).fetchall()
    assert rows == []

    rows2 = db_session.execute(
        text("SELECT id FROM chat_conversation_active_members WHERE conversation_id = :id"), {"id": conv_id}
    ).fetchall()
    assert rows2 == []


def test_raw_sql_non_member_cannot_read_conversation_in_same_company(db_session: Session) -> None:
    from app.modules.tenancy.models import Company

    company = Company(name="Same Co")
    db_session.add(company)
    db_session.flush()

    alice = _make_user(db_session, "rls2a@example.com")
    mallory = _make_user(db_session, "rls2m@example.com")

    set_company_context(db_session, company.id)
    set_user_context(db_session, alice.id)
    db_session.add_all([
        CompanyMember(company_id=company.id, user_id=alice.id, role="owner"),
        CompanyMember(company_id=company.id, user_id=mallory.id, role="member"),
    ])
    db_session.flush()

    conv_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO chat_conversations (id, company_id, type, created_by) "
            "VALUES (:id, :company_id, 'direct', :created_by)"
        ),
        {"id": conv_id, "company_id": company.id, "created_by": alice.id},
    )
    db_session.execute(
        text(
            "INSERT INTO chat_conversation_active_members (id, company_id, conversation_id, user_id) "
            "VALUES (gen_random_uuid(), :company_id, :conversation_id, :user_id)"
        ),
        {"company_id": company.id, "conversation_id": conv_id, "user_id": alice.id},
    )
    msg_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO chat_messages (id, company_id, conversation_id, sender_id, content) "
            "VALUES (:id, :company_id, :conversation_id, :sender_id, 'secret')"
        ),
        {"id": msg_id, "company_id": company.id, "conversation_id": conv_id, "sender_id": alice.id},
    )

    # Mallory is a real member of the SAME company but was never added to
    # this specific conversation.
    set_user_context(db_session, mallory.id)

    rows = db_session.execute(text("SELECT id FROM chat_conversations WHERE id = :id"), {"id": conv_id}).fetchall()
    assert rows == []
    rows2 = db_session.execute(text("SELECT id FROM chat_messages WHERE conversation_id = :id"), {"id": conv_id}).fetchall()
    assert rows2 == []

    # Mallory also cannot forge an INSERT of a message into a conversation
    # she is not an active member of, even with correct company_id.
    forged_id = uuid.uuid4()
    from psycopg.errors import InsufficientPrivilege
    from sqlalchemy.exc import ProgrammingError

    try:
        db_session.execute(
            text(
                "INSERT INTO chat_messages (id, company_id, conversation_id, sender_id, content) "
                "VALUES (:id, :company_id, :conversation_id, :sender_id, 'forged')"
            ),
            {"id": forged_id, "company_id": company.id, "conversation_id": conv_id, "sender_id": mallory.id},
        )
        raise AssertionError("SECURITY BUG: mallory inserted a message into a conversation she is not a member of")
    except ProgrammingError as exc:
        assert isinstance(exc.orig, InsufficientPrivilege)
        db_session.rollback()


def test_raw_sql_cannot_read_another_users_notification(db_session: Session) -> None:
    from app.modules.tenancy.models import Company

    company = Company(name="Notif Co")
    db_session.add(company)
    db_session.flush()

    alice = _make_user(db_session, "rls3a@example.com")
    bob = _make_user(db_session, "rls3b@example.com")

    set_company_context(db_session, company.id)
    set_user_context(db_session, alice.id)
    db_session.add_all([
        CompanyMember(company_id=company.id, user_id=alice.id, role="owner"),
        CompanyMember(company_id=company.id, user_id=bob.id, role="member"),
    ])
    db_session.flush()

    notif_id = uuid.uuid4()
    db_session.execute(
        text(
            "INSERT INTO chat_notifications (id, company_id, user_id, type, title) "
            "VALUES (:id, :company_id, :user_id, 'new_message', 'secret title')"
        ),
        {"id": notif_id, "company_id": company.id, "user_id": bob.id},
    )

    # Alice (the actor who "sent" it) cannot read Bob's notification back.
    rows = db_session.execute(text("SELECT id FROM chat_notifications WHERE id = :id"), {"id": notif_id}).fetchall()
    assert rows == []

