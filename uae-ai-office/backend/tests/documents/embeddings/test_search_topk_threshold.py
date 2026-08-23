import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.embeddings.exceptions import EmbeddingUnavailable
from app.core.embeddings.factory import get_embedding_provider
from tests.documents.embeddings.helpers import search, upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def _index_n_matching_documents(client: TestClient, token: str, n: int, keyword: str) -> None:
    for i in range(n):
        pdf_bytes = build_native_text_pdf_bytes([f"{keyword} entry number {i} details here."])
        upload_process_and_index(client, token, filename=f"doc-{i}.pdf", content=pdf_bytes)


# 30. default top_k enforced
def test_default_top_k_is_enforced(client: TestClient) -> None:
    token, _ = signup(client, "search-topk-default@example.com")
    _index_n_matching_documents(client, token, settings.retrieval_top_k_default + 5, "widget")

    response = search(client, token, query="widget entry details")

    assert response.status_code == 200
    assert len(response.json()["items"]) == settings.retrieval_top_k_default


# 31. maximum top_k enforced
def test_explicit_top_k_up_to_maximum_is_honored(client: TestClient) -> None:
    token, _ = signup(client, "search-topk-max@example.com")
    _index_n_matching_documents(client, token, settings.retrieval_top_k_max + 5, "gadget")

    response = search(client, token, query="gadget entry details", top_k=settings.retrieval_top_k_max)

    assert response.status_code == 200
    assert len(response.json()["items"]) == settings.retrieval_top_k_max


# 32. excessive top_k rejected/clamped safely
def test_top_k_above_maximum_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "search-topk-excessive@example.com")

    response = search(client, token, query="anything", top_k=settings.retrieval_top_k_max + 1)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "bad_request"


def test_top_k_of_zero_is_rejected_by_schema_validation(client: TestClient) -> None:
    token, _ = signup(client, "search-topk-zero@example.com")

    response = client.post(
        "/v1/search", headers={"Authorization": f"Bearer {token}"}, json={"query": "x", "top_k": 0}
    )

    assert response.status_code == 422


def test_custom_top_k_smaller_than_default_is_honored(client: TestClient) -> None:
    token, _ = signup(client, "search-topk-small@example.com")
    _index_n_matching_documents(client, token, 5, "sprocket")

    response = search(client, token, query="sprocket entry details", top_k=2)

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


# 33. similarity threshold removes low-relevance chunks
def test_similarity_threshold_excludes_unrelated_content(client: TestClient) -> None:
    token, _ = signup(client, "search-threshold-excludes@example.com")
    unrelated_pdf = build_native_text_pdf_bytes(
        ["Xylophone quokka umbrella zeppelin marmalade jigsaw puzzle festival."]
    )
    upload_process_and_index(client, token, filename="unrelated.pdf", content=unrelated_pdf)

    response = search(client, token, query="concrete foundation steel reinforcement schedule")

    assert response.status_code == 200
    assert response.json()["items"] == []


# deleted-document retrieval (security review): an already-indexed
# document's chunks must stop being searchable the moment the document
# is soft-deleted, exactly like it stops appearing in GET/list/download.
def test_soft_deleted_document_chunks_are_excluded_from_search(client: TestClient) -> None:
    token, _ = signup(client, "search-excludes-deleted@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification unique wording."])
    document = upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)

    before = search(client, token, query="concrete foundation specification unique wording")
    assert len(before.json()["items"]) >= 1

    delete_response = client.delete(
        f"/v1/documents/{document['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_response.status_code == 200

    after = search(client, token, query="concrete foundation specification unique wording")
    assert after.json()["items"] == []


# 34. no relevant chunks returns empty results
def test_no_indexed_content_returns_empty_results_not_an_error(client: TestClient) -> None:
    token, _ = signup(client, "search-no-content@example.com")

    response = search(client, token, query="anything at all")

    assert response.status_code == 200
    assert response.json()["items"] == []


# 35. ranked results ordered correctly
def test_results_are_ordered_by_descending_relevance(client: TestClient) -> None:
    token, _ = signup(client, "search-ranking@example.com")
    highly_relevant = build_native_text_pdf_bytes(
        ["concrete foundation reinforcement steel rebar schedule specification"]
    )
    somewhat_relevant = build_native_text_pdf_bytes(["concrete pouring schedule for site access"])
    upload_process_and_index(client, token, filename="high.pdf", content=highly_relevant)
    upload_process_and_index(client, token, filename="mid.pdf", content=somewhat_relevant)

    response = search(
        client, token, query="concrete foundation reinforcement steel rebar schedule specification"
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 1
    scores = [item["score"] for item in items]
    assert scores == sorted(scores, reverse=True)
    if len(items) >= 2:
        assert "foundation reinforcement" in items[0]["content"] or "rebar" in items[0]["content"]


# 36. retrieval returns source metadata
def test_search_returns_page_source_metadata(client: TestClient) -> None:
    token, _ = signup(client, "search-source-metadata@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification on page one."])
    upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)

    response = search(client, token, query="concrete foundation specification")

    items = response.json()["items"]
    assert len(items) >= 1
    assert items[0]["page_number"] == 1
    assert items[0]["source_location"] is not None


# 37. retrieval never returns vector values
def test_search_response_never_contains_a_raw_vector(client: TestClient) -> None:
    token, _ = signup(client, "search-no-vector@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification content."])
    upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)

    response = search(client, token, query="concrete foundation specification")

    assert "embedding" not in response.text
    body = response.json()
    for item in body["items"]:
        assert "embedding" not in item


# 38. retrieval never returns storage_key
def test_search_response_never_contains_storage_key(client: TestClient) -> None:
    token, _ = signup(client, "search-no-storage-key@example.com")
    pdf_bytes = build_native_text_pdf_bytes(["Concrete foundation specification content."])
    upload_process_and_index(client, token, filename="doc.pdf", content=pdf_bytes)

    response = search(client, token, query="concrete foundation specification")

    assert "storage_key" not in response.text


# 39. provider error does not expose raw vendor response
def test_search_provider_failure_does_not_expose_raw_vendor_response(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, _ = signup(client, "search-provider-failure@example.com")
    provider = get_embedding_provider()

    def boom(text: str):
        raise EmbeddingUnavailable("simulated outage with vendor payload SECRET-PAYLOAD-771")

    monkeypatch.setattr(provider, "embed_query", boom)

    response = search(client, token, query="anything")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "search_unavailable"
    assert "SECRET-PAYLOAD-771" not in response.text

