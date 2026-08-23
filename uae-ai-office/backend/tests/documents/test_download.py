from fastapi.testclient import TestClient

from tests.documents.helpers import PDF_BYTES, auth_header, signup, upload_file


# 44. signed URL is generated only after tenant authorization
def test_download_requires_authentication(client: TestClient) -> None:
    token, _ = signup(client, "download-auth-required@example.com")
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.get(f"/v1/documents/{document['id']}/download")

    assert response.status_code == 401
    assert "download_url" not in response.text


def test_download_succeeds_for_the_owning_company_after_authorization(client: TestClient) -> None:
    token, _ = signup(client, "download-authorized@example.com")
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.get(f"/v1/documents/{document['id']}/download", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["download_url"]
    assert body["expires_in_seconds"] > 0


# 45. arbitrary object key cannot be supplied for signing
def test_no_generic_arbitrary_key_signing_endpoint_exists(client: TestClient) -> None:
    token, _ = signup(client, "download-no-arbitrary-key@example.com")

    response = client.get(
        "/v1/documents/download?key=companies/other/documents/other/original",
        headers=auth_header(token),
    )

    # There is no generic /download route. "/documents/download" only
    # matches the tenant-scoped /{document_id} pattern with document_id
    # literally "download", which isn't a valid UUID -- so this fails
    # request validation rather than ever reaching a key-signing code
    # path. A key query parameter is never read by any route in this API.
    assert response.status_code == 422


def test_extra_key_query_param_is_ignored_not_honored(client: TestClient) -> None:
    """The download route takes no key/object_key parameter of any kind
    -- an extra, irrelevant query string must have zero effect; the
    signed URL is still generated strictly from the resolved document's
    own server-side storage_key.
    """
    token, _ = signup(client, "download-ignores-key-param@example.com")
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    response = client.get(
        f"/v1/documents/{document['id']}/download"
        "?key=companies/other-company/documents/other-document/original&object_key=whatever",
        headers=auth_header(token),
    )

    assert response.status_code == 200
    assert response.json()["download_url"]


# 46. storage_key is never exposed in API response
def test_storage_key_never_appears_in_upload_response(client: TestClient) -> None:
    token, _ = signup(client, "no-leak-upload@example.com")

    response = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES)

    assert "storage_key" not in response.json()


def test_storage_key_never_appears_in_get_or_list_or_download_response(client: TestClient) -> None:
    token, _ = signup(client, "no-leak-get-list-download@example.com")
    document = upload_file(client, token, filename="doc.pdf", content=PDF_BYTES).json()

    get_response = client.get(f"/v1/documents/{document['id']}", headers=auth_header(token))
    list_response = client.get("/v1/documents", headers=auth_header(token))
    download_response = client.get(
        f"/v1/documents/{document['id']}/download", headers=auth_header(token)
    )

    assert "storage_key" not in get_response.json()
    assert "storage_key" not in list_response.text
    assert "storage_key" not in download_response.json()

