from starlette.requests import Request

from app.core.config import settings
from app.core.request_ip import get_client_ip


def _make_request(*, client_host: str | None, headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": (client_host, 12345) if client_host is not None else None,
    }
    return Request(scope)


def test_default_never_trusts_x_forwarded_for(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    request = _make_request(
        client_host="203.0.113.9", headers={"x-forwarded-for": "9.9.9.9"}
    )

    assert get_client_ip(request) == "203.0.113.9"


def test_default_returns_none_when_there_is_no_direct_peer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    request = _make_request(client_host=None, headers={"x-forwarded-for": "9.9.9.9"})

    assert get_client_ip(request) is None


def test_non_ip_direct_peer_becomes_none_not_a_db_error(monkeypatch) -> None:
    """Exactly the shape FastAPI's own TestClient uses by default
    ("testclient", not a real IP) -- this must never reach the database
    as a value for an INET column.
    """
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    request = _make_request(client_host="testclient", headers={})

    assert get_client_ip(request) is None


def test_trusted_single_hop_extracts_the_real_client_ignoring_a_spoofed_prefix(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    # "1.2.3.4" is an attacker-supplied prefix an untrusted client could
    # set; "5.6.7.8" is what our one trusted proxy actually appended (the
    # real peer address it saw) -- taking the *first* entry would have
    # returned the attacker's forged value instead.
    request = _make_request(
        client_host="10.0.0.1", headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
    )

    assert get_client_ip(request) == "5.6.7.8"


def test_trusted_hops_falls_back_to_direct_peer_when_header_is_absent(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    request = _make_request(client_host="203.0.113.9", headers={})

    assert get_client_ip(request) == "203.0.113.9"


def test_trusted_hops_with_malformed_entry_returns_none_not_a_wrong_ip(monkeypatch) -> None:
    monkeypatch.setattr(settings, "trusted_proxy_hops", 1)
    request = _make_request(
        client_host="10.0.0.1", headers={"x-forwarded-for": "not-an-ip, also-not-an-ip"}
    )

    assert get_client_ip(request) is None


def test_trusted_hops_configured_deeper_than_the_chain_falls_back_to_direct_peer(
    monkeypatch,
) -> None:
    """A misconfiguration (more trusted hops than the header actually has)
    degrades safely to the unspoofable direct peer rather than indexing
    into attacker-controlled data or guessing.
    """
    monkeypatch.setattr(settings, "trusted_proxy_hops", 5)
    request = _make_request(client_host="10.0.0.1", headers={"x-forwarded-for": "1.2.3.4"})

    assert get_client_ip(request) == "10.0.0.1"

