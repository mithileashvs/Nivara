"""Password hashing and JWT helpers."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings
from app.core.errors import UnauthorizedError

# bcrypt only uses the first 72 bytes; schemas reject longer passwords instead
# of silently truncating them.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:MAX_PASSWORD_BYTES], password_hash.encode("utf-8"))
    except ValueError:
        return False


def burn_password_check(password: str, rounds: int = 12) -> None:
    """Spend roughly the same time as a real verification (login for unknown email)."""
    verify_password(password, hash_password(secrets.token_hex(8), rounds))


def create_access_token(*, user_id: str, role: str, settings: Settings) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``."""
    now = datetime.now(timezone.utc)
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    claims: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires,
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)
    return token, int(expires.total_seconds())


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],  # pinned: prevents alg-confusion / "none"
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired", code="token_expired") from None
    except jwt.PyJWTError:
        raise UnauthorizedError("Invalid authentication token", code="invalid_token") from None
    if claims.get("type") != "access":
        raise UnauthorizedError("Invalid authentication token", code="invalid_token")
    return claims
