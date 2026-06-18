from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import RegisterIn, UserOut
from app.services.auth_service import EmailTakenError, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)) -> UserOut:
    try:
        user = register_user(db, body.email, body.password)
    except EmailTakenError:
        raise HTTPException(status_code=409, detail="email already registered") from None
    return UserOut(id=user.id, email=user.email)
