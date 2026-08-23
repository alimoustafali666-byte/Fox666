from fastapi.testclient import TestClient

from tests.documents.helpers import auth_header


def regenerate_brief(client: TestClient, token: str):
    return client.post("/v1/briefs/regenerate", headers=auth_header(token))


def get_brief(client: TestClient, token: str, brief_date: str = "latest"):
    return client.get(f"/v1/briefs/{brief_date}", headers=auth_header(token))


def list_briefs(client: TestClient, token: str, *, limit: int | None = None, cursor: str | None = None):
    params = {}
    if limit is not None:
        params["limit"] = limit
    if cursor is not None:
        params["cursor"] = cursor
    return client.get("/v1/briefs", params=params, headers=auth_header(token))

