import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.llm.fake_provider import FakeLLMProvider
from app.db.session import set_company_context
from app.modules.briefs import repository as briefs_repository
from tests.briefs.helpers import get_brief, list_briefs, regenerate_brief
from tests.documents.helpers import signup


def test_latest_returns_404_when_no_brief_exists(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "brief-dates-no-latest@example.com")

    response = get_brief(client, token, brief_date="latest")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "brief_not_found"


def test_invalid_date_format_returns_400(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "brief-dates-invalid-format@example.com")

    response = get_brief(client, token, brief_date="not-a-date")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_brief_date"


def test_valid_but_nonexistent_date_returns_404(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "brief-dates-nonexistent@example.com")

    response = get_brief(client, token, brief_date="2020-01-01")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "brief_not_found"


def test_latest_returns_the_most_recently_generated_brief(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "brief-dates-latest@example.com")
    generated = regenerate_brief(client, token)
    assert generated.status_code == 201

    response = get_brief(client, token, brief_date="latest")

    assert response.status_code == 200
    assert response.json()["id"] == generated.json()["id"]


def test_pagination_is_bounded(
    client: TestClient, fake_llm_provider: FakeLLMProvider, db_session: Session
) -> None:
    token, claims = signup(client, "brief-pagination@example.com")
    company_id = uuid.UUID(claims["company_id"])
    user_id = uuid.UUID(claims["sub"])

    set_company_context(db_session, company_id)
    base_date = date(2026, 1, 1)
    for i in range(15):
        briefs_repository.create_daily_brief(
            db_session, id=uuid.uuid4(), company_id=company_id, generated_by=user_id,
            brief_date=base_date + timedelta(days=i), summary=f"brief {i}",
        )

    response = list_briefs(client, token, limit=10)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["next_cursor"] is not None

    second_page = list_briefs(client, token, limit=10, cursor=body["next_cursor"])
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 5
    assert second_page.json()["next_cursor"] is None

    first_ids = {item["id"] for item in body["items"]}
    second_ids = {item["id"] for item in second_page.json()["items"]}
    assert first_ids.isdisjoint(second_ids)

