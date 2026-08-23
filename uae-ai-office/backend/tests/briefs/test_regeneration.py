from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.briefs.helpers import list_briefs, regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


# regenerating on the same day REPLACES the existing brief (same row,
# UNIQUE(company_id, brief_date)) rather than erroring or duplicating.
def test_regenerate_same_day_replaces_brief_atomically(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token, _ = signup(client, "brief-regen-replace@example.com")
    pdf_one = build_native_text_pdf_bytes(["First document about site inspection."])
    upload_process_and_index(client, token, filename="one.pdf", content=pdf_one)

    first = regenerate_brief(client, token)
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert len(first_body["items"]) == 1

    pdf_two = build_native_text_pdf_bytes(["Second document about a payment milestone."])
    upload_process_and_index(client, token, filename="two.pdf", content=pdf_two)

    second = regenerate_brief(client, token)
    assert second.status_code == 201, second.text
    second_body = second.json()

    # same brief id, same brief_date -- the row was updated, not duplicated
    assert second_body["id"] == first_body["id"]
    assert second_body["brief_date"] == first_body["brief_date"]
    # the window for a same-day regeneration still starts from the last
    # brief strictly before today (none exists), so both documents are
    # in scope again -- old items were replaced, not appended to.
    assert len(second_body["items"]) == 2

    listed = list_briefs(client, token)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1


def test_regenerate_updates_generated_at(client: TestClient, fake_llm_provider: FakeLLMProvider) -> None:
    token, _ = signup(client, "brief-regen-timestamp@example.com")
    pdf = build_native_text_pdf_bytes(["Document about a variation order."])
    upload_process_and_index(client, token, filename="doc.pdf", content=pdf)

    first = regenerate_brief(client, token)
    assert first.status_code == 201

    second = regenerate_brief(client, token)
    assert second.status_code == 201

    assert second.json()["generated_at"] > first.json()["generated_at"]

