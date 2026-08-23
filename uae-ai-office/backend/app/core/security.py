import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Argon2id, explicit parameters (not library defaults) so the cost is a
# deliberate, documented choice: ~64 MiB memory, 3 passes, 4 lanes -- in
# line with OWASP's Argon2id guidance for an interactive login path.
password_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__type="ID",
    argon2__time_cost=3,
    argon2__memory_cost=65536,
    argon2__parallelism=4,
)

# Used only to keep failed-login timing uniform when the email doesn't
# match any user (see verify_password_or_dummy below) -- never a real
# credential.
_DUMMY_PASSWORD_HASH = password_context.hash(secrets.token_urlsafe(32))

ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    """Always run a real Argon2 verify, even when no user matched the
    submitted email, so a login attempt against a nonexistent account takes
    approximately the same time as one against a real account with the
    wrong password. Returns False either way when password_hash is None.
    """
    verified = password_context.verify(password, password_hash or _DUMMY_PASSWORD_HASH)
    return verified and password_hash is not None


def create_access_token(*, user_id: uuid.UUID, company_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "role": role,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


class InvalidTokenError(Exception):
    pass


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "company_id", "role", "type", "iat", "exp"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError("unexpected token type")

    return payload


def generate_refresh_token() -> str:
    """A high-entropy opaque token -- NOT a JWT. Its only job is to be
    unguessable and to be looked up by hash server-side; it carries no
    claims of its own, so there is nothing in it to decode or forge.
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    """SHA-256 is intentionally fast here, unlike Argon2 for passwords:
    the token already has ~256 bits of entropy from secrets.token_urlsafe,
    so there is no low-entropy secret to slow down an offline guessing
    attack against -- a fast hash is the standard, correct choice for
    looking up high-entropy bearer tokens (the same pattern most API-key
    systems use).
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

