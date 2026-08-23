"""User-entered ticket text (subject/description/comment) is untrusted
data. The backend's job is data-integrity only -- store and return it
verbatim, byte-for-byte, never attempt HTML sanitization or mangling of
it. The XSS-inertness guarantee itself comes from the frontend always
rendering this text as plain React text content (never
dangerouslySetInnerHTML -- see the Step 16/17 frontend code), which
these backend tests can't exercise directly; what they CAN and do prove
is that the payload survives the round trip completely unexecuted and
unmodified, ready for that safe rendering.
"""

from fastapi.testclient import TestClient

from tests.support.helpers import auth_header, signup

_XSS_PAYLOAD = "<script>alert('xss')</script>"
_HTML_INJECTION_PAYLOAD = "<img src=x onerror=alert(1)>"


# 20 & 21. ticket text is rendered safely / XSS payload is inert
def test_xss_payload_in_subject_is_stored_and_returned_verbatim(client: TestClient) -> None:
    token, _ = signup(client, "xss-subject@example.com")

    created = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": _XSS_PAYLOAD, "description": "Description"},
        headers=auth_header(token),
    )
    assert created.status_code == 201
    assert created.json()["subject"] == _XSS_PAYLOAD

    fetched = client.get(f"/v1/support/tickets/{created.json()['id']}", headers=auth_header(token))
    assert fetched.status_code == 200
    assert fetched.json()["subject"] == _XSS_PAYLOAD


def test_xss_payload_in_description_is_stored_and_returned_verbatim(client: TestClient) -> None:
    token, _ = signup(client, "xss-description@example.com")

    created = client.post(
        "/v1/support/tickets",
        json={
            "category": "documents",
            "subject": "Subject",
            "description": _HTML_INJECTION_PAYLOAD,
        },
        headers=auth_header(token),
    )

    assert created.status_code == 201
    assert created.json()["description"] == _HTML_INJECTION_PAYLOAD


def test_xss_payload_in_comment_is_stored_and_returned_verbatim(client: TestClient) -> None:
    token, _ = signup(client, "xss-comment@example.com")
    ticket = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": "Subject", "description": "Description"},
        headers=auth_header(token),
    ).json()

    reply = client.post(
        f"/v1/support/tickets/{ticket['id']}/comments",
        json={"body": _XSS_PAYLOAD},
        headers=auth_header(token),
    )

    assert reply.status_code == 201
    assert reply.json()["body"] == _XSS_PAYLOAD


def test_response_body_is_json_not_executable_html(client: TestClient) -> None:
    """The API response itself is application/json, never text/html --
    an XSS payload embedded in a JSON string value has no way to execute
    from this response even before it reaches the (already-safe) React
    renderer.
    """
    token, _ = signup(client, "xss-content-type@example.com")

    response = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": _XSS_PAYLOAD, "description": "Description"},
        headers=auth_header(token),
    )

    assert response.headers["content-type"].startswith("application/json")

