from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(pw: str) -> str:
    return _ctx.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return _ctx.verify(pw, hashed)
