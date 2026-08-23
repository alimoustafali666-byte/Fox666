from fastapi.testclient import TestClient

from tests.documents.helpers import auth_header


def create_conversation(client: TestClient, token: str, *, title: str | None = None) -> dict:
    body = {} if title is None else {"title": title}
    response = client.post("/v1/conversations", json=body, headers=auth_header(token))
    assert response.status_code == 201, response.text
    return response.json()


def ask(
    client: TestClient,
    token: str,
    *,
    conversation_id: str,
    question: str,
    document_id: str | None = None,
    project_id: str | None = None,
    document_type: str | None = None,
    extra: dict | None = None,
):
    body: dict = {"question": question}
    if document_id is not None:
        body["document_id"] = document_id
    if project_id is not None:
        body["project_id"] = project_id
    if document_type is not None:
        body["document_type"] = document_type
    if extra:
        body.update(extra)
    return client.post(
        f"/v1/conversations/{conversation_id}/messages", json=body, headers=auth_header(token)
    )


def list_conversations(client: TestClient, token: str):
    return client.get("/v1/conversations", headers=auth_header(token))


def get_conversation(client: TestClient, token: str, conversation_id: str):
    return client.get(f"/v1/conversations/{conversation_id}", headers=auth_header(token))


def list_messages(client: TestClient, token: str, conversation_id: str):
    return client.get(f"/v1/conversations/{conversation_id}/messages", headers=auth_header(token))

