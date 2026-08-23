from fastapi.testclient import TestClient

from tests.support.helpers import auth_header, signup


# 1. user can open Help Center (list articles)
def test_user_can_list_help_articles(client: TestClient) -> None:
    token, _ = signup(client, "help-list@example.com")

    response = client.get("/v1/support/articles", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) > 0
    assert all("slug" in item and "title" in item and "body" in item for item in body["items"])


# 2. knowledge articles load (single article by slug)
def test_single_article_loads_by_slug(client: TestClient) -> None:
    token, _ = signup(client, "help-article@example.com")

    response = client.get(
        "/v1/support/articles/document-lifecycle-explained", headers=auth_header(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "document-lifecycle-explained"
    assert "Processing" in body["body"]


def test_unknown_article_slug_is_a_safe_400(client: TestClient) -> None:
    token, _ = signup(client, "help-unknown@example.com")

    response = client.get("/v1/support/articles/does-not-exist", headers=auth_header(token))

    assert response.status_code == 400
    assert "error" in response.json()


# 3. Arabic help content works
def test_article_locale_returns_arabic_content(client: TestClient) -> None:
    token, _ = signup(client, "help-arabic@example.com")

    en_response = client.get(
        "/v1/support/articles/document-lifecycle-explained?locale=en", headers=auth_header(token)
    )
    ar_response = client.get(
        "/v1/support/articles/document-lifecycle-explained?locale=ar", headers=auth_header(token)
    )

    assert en_response.status_code == 200
    assert ar_response.status_code == 200
    assert en_response.json()["title"] != ar_response.json()["title"]
    assert "قيد المعالجة" in ar_response.json()["body"]


def test_arabic_search_finds_arabic_articles(client: TestClient) -> None:
    token, _ = signup(client, "help-arabic-search@example.com")

    response = client.post(
        "/v1/support/search?locale=ar",
        json={"query": "لماذا مستندي غير جاهز"},
        headers=auth_header(token),
    )

    assert response.status_code == 200
    slugs = [item["slug"] for item in response.json()["items"]]
    assert "why-document-not-ready" in slugs


# 4. support search is bounded
def test_search_query_too_long_is_rejected(client: TestClient) -> None:
    token, _ = signup(client, "help-search-bound@example.com")

    response = client.post(
        "/v1/support/search",
        json={"query": "a" * 5000},
        headers=auth_header(token),
    )

    assert response.status_code == 422


def test_search_returns_bounded_result_count(client: TestClient) -> None:
    token, _ = signup(client, "help-search-count@example.com")

    # A very generic word likely to overlap several articles -- still must
    # never return more results than the endpoint's own bound (10).
    response = client.post(
        "/v1/support/search", json={"query": "document project"}, headers=auth_header(token)
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) <= 10


def test_categories_filter_returns_only_matching_category(client: TestClient) -> None:
    token, _ = signup(client, "help-category@example.com")

    response = client.get(
        "/v1/support/articles?category=roles_permissions", headers=auth_header(token)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) > 0
    assert all(item["category"] == "roles_permissions" for item in body["items"])


def test_unauthenticated_user_cannot_read_help_center(client: TestClient) -> None:
    response = client.get("/v1/support/articles")

    assert response.status_code == 401

