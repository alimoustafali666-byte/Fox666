"""Proves the Support Assistant's isolation from Ask Your Business/company
document context -- both statically (the module never imports the
retrieval/conversation code paths) and behaviorally (a document's real
content never reaches the provider through a support question, even when
the question's wording overlaps that content and the company has fully
indexed it).
"""

import ast
import inspect
import uuid

from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from app.modules.support import assistant_service
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.processing.helpers import build_native_text_pdf_bytes
from tests.support.helpers import auth_header, seed_member, signup


# 5a. static: the assistant module never imports the business-document
# retrieval or conversation code paths -- architectural isolation, not a
# runtime filter that could have a bug. Checks actual `import`/`from ...
# import` statements only (not the module's own docstring, which
# legitimately names these modules to explain what must never be
# imported).
def test_assistant_service_never_imports_business_ai_modules() -> None:
    tree = ast.parse(inspect.getsource(assistant_service))
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)

    forbidden = ["retrieval_service", "conversations", "embeddings"]
    for token in forbidden:
        assert not any(token in name for name in imported_names), (
            f"assistant_service.py must never import a module referencing {token!r}, "
            f"found: {[n for n in imported_names if token in n]}"
        )


# 5b. behavioral: a company's real, fully-indexed document content never
# reaches the Support Assistant's provider call, even when the support
# question's words overlap that content.
def test_assistant_never_receives_company_document_content(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "boundary-doc@example.com")
    secret_marker = "Zylophonic quandary contract value AED 999888."
    upload_process_and_index(
        client, token, filename="secret.pdf", content=build_native_text_pdf_bytes([secret_marker])
    )

    response = client.post(
        "/v1/support/assistant/ask",
        json={"question": "What is the Zylophonic quandary contract value?"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    for call in fake_llm_provider.calls:
        for item in call.document_context:
            assert "Zylophonic" not in item.content
            assert "999888" not in item.content


# 6. support AI cannot access another company's context, even indirectly
# via diagnostics -- a document_id from a different company simply
# doesn't resolve (company-scoped getter), so nothing about it can leak.
def test_assistant_diagnostics_cannot_reach_another_companys_document(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token_a, _ = signup(client, "boundary-company-a@example.com", "Company A")
    token_b, _ = signup(client, "boundary-company-b@example.com", "Company B")

    secret_marker = "Company A confidential figure 4471."
    doc_a = upload_process_and_index(
        client, token_a, filename="a.pdf", content=build_native_text_pdf_bytes([secret_marker])
    )

    response = client.post(
        "/v1/support/assistant/ask",
        json={
            "question": "Why is my document not ready?",
            "diagnostics": {"document_id": doc_a["id"]},
        },
        headers=auth_header(token_b),
    )

    assert response.status_code == 200
    for call in fake_llm_provider.calls:
        for item in call.document_context:
            assert "4471" not in item.content
            assert "Company A confidential" not in item.content


def test_blank_support_question_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "assistant-blank@example.com")

    response = client.post(
        "/v1/support/assistant/ask", json={"question": "   "}, headers=auth_header(token)
    )

    assert response.status_code == 400


def test_support_question_too_long_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "assistant-toolong@example.com")

    response = client.post(
        "/v1/support/assistant/ask", json={"question": "a" * 5000}, headers=auth_header(token)
    )

    assert response.status_code == 422


def test_assistant_answers_from_matching_kb_article(client: TestClient) -> None:
    token, _ = signup(client, "assistant-kb-match@example.com")

    response = client.post(
        "/v1/support/assistant/ask",
        json={"question": "What does Indexing mean and what comes after Processing?"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sufficient"] is True
    assert any(c["article_slug"] == "document-lifecycle-explained" for c in body["citations"])


def test_assistant_reports_insufficient_for_unrelated_question(client: TestClient) -> None:
    token, _ = signup(client, "assistant-unrelated@example.com")

    response = client.post(
        "/v1/support/assistant/ask",
        json={"question": "Qwzxjklv frobnicate splunge unrelated gibberish query"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sufficient"] is False
    assert body["citations"] == []


def test_assistant_uses_document_diagnostics_for_not_ready_question(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "assistant-diagnostics@example.com")
    doc = upload_process_and_index(
        client, token, filename="d.pdf", content=build_native_text_pdf_bytes(["Some contract text."])
    )

    response = client.post(
        "/v1/support/assistant/ask",
        json={
            "question": "Why is my document not ready?",
            "diagnostics": {"document_id": doc["id"], "page": "/documents"},
        },
        headers=auth_header(token),
    )

    assert response.status_code == 200
    saw_diagnostics_context = any(
        any(item.ref == "diagnostics" for item in call.document_context)
        for call in fake_llm_provider.calls
    )
    assert saw_diagnostics_context


def test_available_to_every_role(client: TestClient, db_session) -> None:
    _, owner_claims = signup(client, "assistant-role-owner@example.com")
    company_id = owner_claims["company_id"]
    for role in ("admin", "manager", "member"):
        role_token = seed_member(
            db_session,
            company_id=uuid.UUID(company_id),
            email=f"assistant-role-{role}@example.com",
            role=role,
        )
        response = client.post(
            "/v1/support/assistant/ask",
            json={"question": "How do I create a project?"},
            headers=auth_header(role_token),
        )
        assert response.status_code == 200, f"role={role}: {response.text}"

