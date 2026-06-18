from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.security.passwords import hash_password, verify_password


class EmailTakenError(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if exists:
        raise EmailTakenError(email)
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return user
