from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import LoginIn, RefreshIn, RegisterIn, TokenPair, UserOut
from app.security.tokens import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.services.auth_service import (
    EmailTakenError,
    InvalidCredentials,
    authenticate,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> UserOut:
    try:
        user = register_user(db, body.email, body.password)
    except EmailTakenError:
        raise HTTPException(status_code=409, detail="email already registered") from None
    return UserOut(id=user.id, email=user.email)


@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = authenticate(db, body.email, body.password)
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="invalid credentials") from None
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn) -> TokenPair:
    try:
        claims = decode_token(body.refresh_token)
    except TokenError:
        raise HTTPException(status_code=401, detail="invalid token") from None
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="wrong token type")
    uid = int(claims["sub"])
    return TokenPair(
        access_token=create_access_token(uid),
        refresh_token=create_refresh_token(uid),
    )
