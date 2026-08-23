import ipaddress

from fastapi import Request

from app.core.config import settings


def _valid_ip_or_none(value: str | None) -> str | None:
    """audit_logs.ip_address is a Postgres INET column -- anything that
    isn't a real, parseable IP (a test client's placeholder hostname, a
    malformed proxy header) must become NULL, not a DB error on an
    otherwise-unrelated request.
    """
    if value is None:
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return None
    return value


def get_client_ip(request: Request) -> str | None:
    """See settings.trusted_proxy_hops for the reasoning. With hops=0
    (the default), this is just the direct TCP peer -- unspoofable by
    the client, but equal to a reverse proxy's own address in any
    deployment that has one in front of the app, which is why enabling
    trust requires an explicit, deployment-specific config choice.
    """
    if settings.trusted_proxy_hops > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
            index = len(hops) - settings.trusted_proxy_hops
            if 0 <= index < len(hops):
                return _valid_ip_or_none(hops[index])

    return _valid_ip_or_none(request.client.host if request.client else None)

