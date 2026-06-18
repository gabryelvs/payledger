from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings

ALGO = "HS256"


class TokenError(Exception):
    pass


def _make(sub: int, ttl: timedelta, ttype: str) -> str:
    now = datetime.now(UTC)
    payload = {"sub": str(sub), "type": ttype, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def create_access_token(user_id: int) -> str:
    return _make(user_id, timedelta(minutes=settings.access_ttl_min), "access")


def create_refresh_token(user_id: int) -> str:
    return _make(user_id, timedelta(days=settings.refresh_ttl_days), "refresh")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
    except jwt.PyJWTError as e:
        raise TokenError(str(e)) from e
