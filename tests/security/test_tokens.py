import pytest

from app.security.tokens import TokenError, create_access_token, decode_token


def test_roundtrip_access_token():
    tok = create_access_token(42)
    claims = decode_token(tok)
    assert claims["sub"] == "42"
    assert claims["type"] == "access"


def test_garbage_token_raises():
    with pytest.raises(TokenError):
        decode_token("not.a.token")
