from fastapi.testclient import TestClient

from tests.documents.helpers import auth_header
from tests.documents.processing.helpers import upload_and_get_document


def upload_process_and_index(
    client: TestClient, token: str, *, filename: str, content: bytes,
    document_type: str = "contract", project_id: str | None = None,
) -> dict:
    """Uploads, processes, and indexes a document in one call, returning
    the final document state. Fails the test immediately (via assert) if
    any step doesn't succeed -- most embeddings/search tests care about
    what happens *after* a document is fully indexed, not about
    re-testing upload/process themselves (already covered in Steps 8-9).
    """
    document = upload_and_get_document(
        client, token, filename=filename, content=content,
        document_type=document_type, project_id=project_id,
    )
    process_response = client.post(
        f"/v1/documents/{document['id']}/process", headers=auth_header(token)
    )
    assert process_response.status_code == 200, process_response.text

    index_response = client.post(
        f"/v1/documents/{document['id']}/index", headers=auth_header(token)
    )
    assert index_response.status_code == 200, index_response.text

    return index_response.json()


def search(
    client: TestClient, token: str, *, query: str, top_k: int | None = None,
    document_id: str | None = None, project_id: str | None = None,
    document_type: str | None = None,
):
    body: dict = {"query": query}
    if top_k is not None:
        body["top_k"] = top_k
    if document_id is not None:
        body["document_id"] = document_id
    if project_id is not None:
        body["project_id"] = project_id
    if document_type is not None:
        body["document_type"] = document_type
    return client.post("/v1/search", headers=auth_header(token), json=body)

