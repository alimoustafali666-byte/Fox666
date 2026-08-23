"""Source traceability: source_type/source_id must be re-validated
against the real owning module at creation time -- never trusted
blindly, and a stale/foreign/forged reference must be rejected the same
IDOR-safe way as every other cross-tenant lookup in this app.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.collaboration.helpers import create_direct, send_message
from tests.documents.helpers import PDF_BYTES, upload_file
from tests.tasks.helpers import auth_header, create_task, seed_brief_item, seed_member, signup


def test_manual_source_ignores_source_id(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "src1@example.com")
    task = create_task(client, token, title="x", source_type="manual", source_id="11111111-1111-1111-1111-111111111111")
    assert task["source_type"] == "manual"


def test_document_source_valid(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "src2@example.com")
    upload_resp = upload_file(client, token, filename="quote.pdf", content=PDF_BYTES, content_type="application/pdf")
    assert upload_resp.status_code == 201
    document_id = upload_resp.json()["id"]

    task = create_task(client, token, title="Review quote", source_type="document", source_id=document_id)
    assert task["source_type"] == "document"
    assert task["source_id"] == document_id


def test_document_source_forged_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "src3@example.com")
    resp = client.post(
        "/v1/tasks", json={"title": "x", "source_type": "document", "source_id": "11111111-1111-1111-1111-111111111111"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


def test_document_source_from_another_company_rejected(client: TestClient, db_session: Session) -> None:
    token_a, _claims_a = signup(client, "src4a@example.com")
    upload_resp = upload_file(client, token_a, filename="quote.pdf", content=PDF_BYTES, content_type="application/pdf")
    document_id = upload_resp.json()["id"]

    token_b, _claims_b = signup(client, "src4b@example.com", company_name="Other Co")
    resp = client.post(
        "/v1/tasks", json={"title": "x", "source_type": "document", "source_id": document_id}, headers=auth_header(token_b)
    )
    assert resp.status_code == 400


def test_message_source_valid_and_traceable(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "src5@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=claims["company_id"], email="src5b@example.com", role="member")
    conv = create_direct(client, token, bob_id)
    msg = send_message(client, token, conv["id"], content="Please send the revised quotation by Thursday")

    task = create_task(client, token, title="Send revised quotation", source_type="message", source_id=msg["id"])
    assert task["source_type"] == "message"
    assert task["source_id"] == msg["id"]


def test_message_source_nonmember_rejected(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "src6@example.com")
    bob_token, bob_id = seed_member(db_session, company_id=claims["company_id"], email="src6b@example.com", role="member")
    _carol_token, carol_id = seed_member(db_session, company_id=claims["company_id"], email="src6c@example.com", role="member")
    conv = create_direct(client, token, bob_id)
    msg = send_message(client, token, conv["id"], content="private")

    # Carol is a company member but not in this direct conversation.
    resp = client.post(
        "/v1/tasks", json={"title": "x", "source_type": "message", "source_id": msg["id"]},
        headers=auth_header(_carol_token),
    )
    assert resp.status_code == 400
    assert carol_id  # sanity: carol really exists and is company-scoped, not the failure reason
    assert bob_token  # bob's token isn't used here -- only his membership matters for creating the conversation


def test_conversation_source_valid(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "src7@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=claims["company_id"], email="src7b@example.com", role="member")
    conv = create_direct(client, token, bob_id)

    task = create_task(client, token, title="x", source_type="conversation", source_id=conv["id"])
    assert task["source_id"] == conv["id"]


def test_daily_brief_source_valid(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "src8@example.com")
    item = seed_brief_item(db_session, company_id=claims["company_id"], generated_by=claims["sub"])

    task = create_task(client, token, title="Follow up", source_type="daily_brief", source_id=str(item.id))
    assert task["source_id"] == str(item.id)


def test_daily_brief_source_forged_rejected(client: TestClient, db_session: Session) -> None:
    token, _claims = signup(client, "src9@example.com")
    resp = client.post(
        "/v1/tasks", json={"title": "x", "source_type": "daily_brief", "source_id": "11111111-1111-1111-1111-111111111111"},
        headers=auth_header(token),
    )
    assert resp.status_code == 400


def test_ai_suggestion_source_uses_message_validation(client: TestClient, db_session: Session) -> None:
    token, claims = signup(client, "src10@example.com")
    _bob_token, bob_id = seed_member(db_session, company_id=claims["company_id"], email="src10b@example.com", role="member")
    conv = create_direct(client, token, bob_id)
    msg = send_message(client, token, conv["id"], content="Ahmed, please send the revised quotation by Thursday")

    task = create_task(client, token, title="Send revised quotation", source_type="ai_suggestion", source_id=msg["id"])
    assert task["source_type"] == "ai_suggestion"
    assert task["source_id"] == msg["id"]

