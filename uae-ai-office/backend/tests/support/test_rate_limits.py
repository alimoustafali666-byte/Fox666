"""MVP rate limits (Step 17 section 18) -- reuses the existing in-process,
single-instance fixed-window limiter (see app.modules.auth.rate_limit's
documented production limitation, which applies identically here).
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.support.helpers import auth_header, create_ticket, signup


def test_ticket_creation_is_rate_limited(client: TestClient) -> None:
    token, _ = signup(client, "rate-ticket@example.com")

    for _ in range(settings.support_ticket_create_rate_limit_max):
        create_ticket(client, token)

    response = client.post(
        "/v1/support/tickets",
        json={"category": "documents", "subject": "One too many", "description": "Should be limited."},
        headers=auth_header(token),
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "support_ticket_rate_limited"


def test_assistant_ask_is_rate_limited(client: TestClient) -> None:
    token, _ = signup(client, "rate-assistant@example.com")

    for _ in range(settings.support_assistant_rate_limit_max):
        response = client.post(
            "/v1/support/assistant/ask",
            json={"question": "How do I create a project?"},
            headers=auth_header(token),
        )
        assert response.status_code == 200

    limited = client.post(
        "/v1/support/assistant/ask",
        json={"question": "How do I create a project?"},
        headers=auth_header(token),
    )

    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "support_assistant_rate_limited"

