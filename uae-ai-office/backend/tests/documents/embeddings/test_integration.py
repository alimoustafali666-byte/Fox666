import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import set_company_context
from app.modules.documents.models import DocumentChunk
from tests.documents.embeddings.helpers import search
from tests.documents.helpers import auth_header, create_project, signup, upload_file
from tests.documents.processing.helpers import build_boq_xlsx_bytes, build_native_text_pdf_bytes


def test_pdf_search_ranks_the_relevant_chunk_first_and_isolates_by_company(
    client: TestClient, db_session: Session
) -> None:
    # signup -> login -> create project
    token, claims = signup(client, "search-integration-pdf@example.com", "Search Integration Co")
    company_id = uuid.UUID(claims["company_id"])
    project = create_project(client, token, name="Search Integration Project")

    # -> upload native-text PDF
    pdf_bytes = build_native_text_pdf_bytes(
        [
            (
                "The concrete foundation specification requires grade 40 concrete "
                "poured in three stages according to the reinforcement schedule."
            ),
            "Unrelated administrative notes about parking permits and building access hours.",
        ]
    )
    upload_response = upload_file(
        client, token, filename="contract.pdf", content=pdf_bytes,
        project_id=project["id"], document_type="contract",
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    # -> process
    process_response = client.post(f"/v1/documents/{document_id}/process", headers=auth_header(token))
    assert process_response.status_code == 200, process_response.text

    # -> index
    index_response = client.post(f"/v1/documents/{document_id}/index", headers=auth_header(token))
    assert index_response.status_code == 200, index_response.text
    assert index_response.json()["indexing_status"] == "indexed"

    # -> search for a phrase semantically related to one chunk
    search_response = search(
        client, token, query="concrete foundation grade reinforcement schedule"
    )
    assert search_response.status_code == 200
    items = search_response.json()["items"]
    assert len(items) >= 1

    # -> expected chunk ranks first
    # (both short pages land in the same chunk at this content length --
    # chunking targets a token budget, not one chunk per page, per Step
    # 9 -- so this asserts the relevant content is present and ranked,
    # not that the two pages were split into separate chunks.)
    assert "concrete foundation" in items[0]["content"].lower()

    # -> source metadata returned
    assert items[0]["document_id"] == document_id
    assert items[0]["page_number"] is not None
    assert items[0]["source_location"] is not None

    # sanity: chunks really are in pgvector with embeddings
    set_company_context(db_session, company_id)
    chunks = list(
        db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(document_id))
        ).scalars()
    )
    assert all(c.embedding is not None for c in chunks)

    # -> Company B runs equivalent search -> receives none of Company A's chunks
    other_token, _ = signup(client, "search-integration-outsider@example.com", "Other Search Co")
    other_search_response = search(
        client, other_token, query="concrete foundation grade reinforcement schedule"
    )
    assert other_search_response.status_code == 200
    assert other_search_response.json()["items"] == []


def test_xlsx_boq_search_retrieves_correct_sheet_row_with_unchanged_numeric_values(
    client: TestClient,
) -> None:
    token, _ = signup(client, "search-integration-xlsx@example.com", "BOQ Search Co")

    # -> upload/process/index BOQ-like workbook
    upload_response = upload_file(
        client, token, filename="boq.xlsx", content=build_boq_xlsx_bytes(), document_type="boq"
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    process_response = client.post(f"/v1/documents/{document_id}/process", headers=auth_header(token))
    assert process_response.status_code == 200, process_response.text

    index_response = client.post(f"/v1/documents/{document_id}/index", headers=auth_header(token))
    assert index_response.status_code == 200, index_response.text

    # -> search for a known row/item
    search_response = search(client, token, query="Concrete quantity rate amount m3")

    assert search_response.status_code == 200
    items = search_response.json()["items"]
    assert len(items) >= 1

    # -> correct sheet/row chunk is retrieved
    top = items[0]
    assert top["sheet_name"] == "BOQ"
    assert "Concrete" in top["content"]

    # -> numeric values remain unchanged in returned content
    assert "Qty: 50" in top["content"]
    assert "Rate: 350" in top["content"]
    assert "Amount: 17500" in top["content"]

