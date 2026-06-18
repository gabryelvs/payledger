from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.security.tokens import TokenError, decode_token

bearer = HTTPBearer()


def current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        claims = decode_token(creds.credentials)
    except TokenError:
        raise HTTPException(status_code=401, detail="invalid token") from None
    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="wrong token type")
    user = db.get(User, int(claims["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    return user
