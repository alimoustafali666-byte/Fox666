from fastapi.testclient import TestClient

from app.core.llm.fake_provider import FakeLLMProvider
from tests.briefs.helpers import get_brief, list_briefs, regenerate_brief
from tests.documents.embeddings.helpers import upload_process_and_index
from tests.documents.helpers import signup
from tests.documents.processing.helpers import build_native_text_pdf_bytes


def test_company_b_cannot_receive_company_a_secret_via_brief(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token_a, _ = signup(client, "brief-cross-a@example.com")
    secret_a_pdf = build_native_text_pdf_bytes(["The confidential project code word is FALCON-ALPHA-771."])
    upload_process_and_index(client, token_a, filename="company-a-secret.pdf", content=secret_a_pdf)
    response_a = regenerate_brief(client, token_a)
    assert response_a.status_code == 201, response_a.text

    token_b, _ = signup(client, "brief-cross-b@example.com")
    secret_b_pdf = build_native_text_pdf_bytes(["The confidential project code word is FALCON-BETA-992."])
    upload_process_and_index(client, token_b, filename="company-b-secret.pdf", content=secret_b_pdf)
    response_b = regenerate_brief(client, token_b)

    assert response_b.status_code == 201, response_b.text
    assert "FALCON-ALPHA-771" not in response_b.text
    assert "company-a-secret.pdf" not in response_b.text

    # the provider was only ever handed company B's content on company B's call
    request = fake_llm_provider.brief_calls[-1]
    for item in request.new_documents:
        assert "FALCON-ALPHA-771" not in item.content


def test_company_b_cannot_view_company_a_brief_via_get_endpoints(
    client: TestClient, fake_llm_provider: FakeLLMProvider
) -> None:
    token_a, _ = signup(client, "brief-cross-get-a@example.com")
    pdf_a = build_native_text_pdf_bytes(["Company A confidential contract detail."])
    upload_process_and_index(client, token_a, filename="a.pdf", content=pdf_a)
    brief_a = regenerate_brief(client, token_a)
    assert brief_a.status_code == 201
    brief_a_date = brief_a.json()["brief_date"]

    token_b, _ = signup(client, "brief-cross-get-b@example.com")

    latest_b = get_brief(client, token_b, brief_date="latest")
    assert latest_b.status_code == 404

    by_date_b = get_brief(client, token_b, brief_date=brief_a_date)
    assert by_date_b.status_code == 404

    list_b = list_briefs(client, token_b)
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

