from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey


class IdempotencyConflict(Exception):
    pass


def remember(db: Session, key: str, request_hash: str, response: dict) -> None:
    db.add(IdempotencyKey(key=key, request_hash=request_hash, response_json=response))
    db.commit()


def lookup(db: Session, key: str, request_hash: str) -> dict | None:
    row = db.get(IdempotencyKey, key)
    if row is None:
        return None
    if row.request_hash != request_hash:
        raise IdempotencyConflict(key)
    return row.response_json
