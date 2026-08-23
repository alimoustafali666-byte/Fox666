"""Regression tests for the multi-commit RLS-context-loss defect.

Root cause: set_company_context/set_user_context apply `SET LOCAL`,
which is scoped to the Postgres transaction it runs in. Several request
handlers (document processing, document indexing, Ask Your Business)
call db.commit() more than once -- each commit ends the real transaction
and, before the fix in app.db.session (an `after_begin` listener that
reapplies the last-set context from Session.info at the start of every
new transaction the same Session begins), silently dropped RLS context
for the rest of the request. Every write after the first commit was then
rejected: `psycopg.errors.InsufficientPrivilege: new row violates row-
level security policy`.

This went completely undetected by the rest of the test suite because
every other fixture in this repo shares ONE Session for a whole test via
join_transaction_mode="create_savepoint" -- app.commit() there releases
a SAVEPOINT and starts a new one, but the real underlying transaction
(and the SET LOCAL context living in it) never actually ends. See
tests/regression/conftest.py for the fixtures that avoid that blind spot
by giving each HTTP request its own Session against a real, dedicated
scratch database -- exactly how app.db.session.get_db() behaves in
production.
"""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.briefs.helpers import regenerate_brief
from tests.conversations.helpers import ask, create_conversation
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import auth_header, signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes
from tests.regression.conftest import SingleConnectionClient


# document processing (mark_document_processing + commit, THEN
# replace_document_chunks + mark_document_processed + commit) and
# indexing (mark_document_indexing + commit, THEN
# persist_chunk_embeddings + mark_document_indexed + commit) each commit
# twice per request -- exactly the pattern that lost RLS context.
def test_upload_process_index_flow_succeeds_with_real_commits(real_client: TestClient) -> None:
    token, _ = signup(real_client, "regression-process-index@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])

    # upload_process_and_index asserts 200 on both the /process and
    # /index calls itself -- pre-fix, /process 500'd with the
    # document_chunks RLS violation reproduced live against this exact
    # scenario.
    document = upload_process_and_index(real_client, token, filename="terms.pdf", content=pdf_bytes)

    assert document["status"] == "processed"
    assert document["indexing_status"] == "indexed"


# ask_service.ask_question always commits once after persisting the
# user's question message, then commits again for whichever response it
# produces -- the insufficient-information path (no retrieval results)
# is the simplest repro of the exact failure reproduced live: the
# assistant's "I don't have enough information" message failed to insert
# with the same InsufficientPrivilege error.
def test_ask_insufficient_information_flow_succeeds_with_real_commits(real_client: TestClient) -> None:
    token, _ = signup(real_client, "regression-ask-insufficient@example.com")
    conversation = create_conversation(real_client, token)

    response = ask(real_client, token, conversation_id=conversation["id"], question="What is our revenue?")

    assert response.status_code == 201, response.text
    assert response.json()["is_sufficient"] is False


# The full grounded-answer path: retrieval succeeds, the (fake) LLM
# returns a valid structured answer, and message_citations rows are
# inserted alongside the assistant message -- all after the same first
# commit, so this exercises every write site in ask_question's success
# branch, not just the insufficient-information shortcut above.
def test_ask_grounded_answer_flow_succeeds_with_real_commits(real_client: TestClient) -> None:
    token, _ = signup(real_client, "regression-ask-grounded@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Payment terms: 30 days net from invoice date."])
    upload_process_and_index(real_client, token, filename="terms.pdf", content=pdf_bytes)
    conversation = create_conversation(real_client, token)

    response = ask(real_client, token, conversation_id=conversation["id"], question="What are the payment terms?")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_sufficient"] is True
    assert len(body["citations"]) >= 1


# brief_orchestrator commits exactly once per request and was never
# affected -- included so this module verifies all four listed request
# paths end-to-end against real commits, not just the three that were
# actually broken.
def test_daily_brief_generation_succeeds_with_real_commits(real_client: TestClient) -> None:
    token, _ = signup(real_client, "regression-brief@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["New contract signed for AED 250,000 with ACME LLC."])
    upload_process_and_index(real_client, token, filename="contract.pdf", content=pdf_bytes)

    response = regenerate_brief(real_client, token)

    assert response.status_code == 201, response.text
    assert len(response.json()["items"]) >= 1


# Fixing the context-loss bug must never come at the cost of tenant
# isolation: proves company B still cannot see any of company A's
# documents, conversations, or content -- via the actual documents/
# conversations endpoints -- after company A's flow made several real
# commits.
def test_cross_tenant_isolation_holds_after_multiple_real_commits(real_client: TestClient) -> None:
    token_a, _ = signup(real_client, "regression-cross-a@example.com")
    secret_pdf = build_native_text_pdf_bytes(["The confidential project code word is FALCON-771."])
    document_a = upload_process_and_index(real_client, token_a, filename="secret-a.pdf", content=secret_pdf)
    conversation_a = create_conversation(real_client, token_a)
    ask(real_client, token_a, conversation_id=conversation_a["id"], question="What is the code word?")

    token_b, _ = signup(real_client, "regression-cross-b@example.com")

    doc_response = real_client.get(f"/v1/documents/{document_a['id']}", headers=auth_header(token_b))
    assert doc_response.status_code == 404

    docs_list = real_client.get("/v1/documents", headers=auth_header(token_b))
    assert docs_list.json()["items"] == []

    conv_response = real_client.get(f"/v1/conversations/{conversation_a['id']}", headers=auth_header(token_b))
    assert conv_response.status_code == 404

    # company B, with zero documents of its own, asking the identical
    # question must get an honest "insufficient information" -- never
    # company A's secret, which would prove a context leak rather than
    # just a permissions check.
    conversation_b = create_conversation(real_client, token_b)
    ask_response = ask(real_client, token_b, conversation_id=conversation_b["id"], question="What is the code word?")
    assert ask_response.status_code == 201
    body = ask_response.json()
    assert body["is_sufficient"] is False
    assert "FALCON-771" not in body["content"]


# Complements tests/tenancy/test_rls_transaction_safety.py (which proves
# this directly against app.db.session's functions) at the actual HTTP/
# app layer: two different companies' real requests, sequentially,
# GUARANTEED to reuse the one pooled connection, must never see each
# other's context -- proving the fix (context durable across a Session's
# own commits) does not weaken the pre-existing guarantee (context never
# survives onto a DIFFERENT Session reusing the same connection).
def test_connection_pool_reuse_does_not_leak_tenant_context_across_real_requests(
    real_client_single_connection: SingleConnectionClient,
) -> None:
    client = real_client_single_connection.client

    token_a, _ = signup(client, "regression-pool-a@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Company A confidential contract detail."])
    upload_process_and_index(client, token_a, filename="a.pdf", content=pdf_bytes)

    token_b, _ = signup(client, "regression-pool-b@example.com")
    docs_b = client.get("/v1/documents", headers=auth_header(token_b))
    assert docs_b.status_code == 200
    assert docs_b.json()["items"] == []

    # A fresh Session on the SAME single-connection engine, opened after
    # both companies' requests completed and returned it to the pool --
    # if either company's context (or the reapply-on-begin listener
    # itself) had leaked onto the underlying connection rather than
    # staying scoped to its own Session, this would see it.
    probe = Session(bind=real_client_single_connection.engine)
    try:
        leaked_company = probe.execute(
            text("SELECT current_setting('app.current_company_id', true)")
        ).scalar_one()
        leaked_user = probe.execute(text("SELECT current_setting('app.current_user_id', true)")).scalar_one()
        probe.rollback()
    finally:
        probe.close()

    assert leaked_company in (None, ""), f"company context leaked onto the connection: {leaked_company!r}"
    assert leaked_user in (None, ""), f"user context leaked onto the connection: {leaked_user!r}"

