"""Idempotency keys, claimed atomically inside the caller's database transaction.

Why claim first
---------------
The old flow was: look the key up, do the transfer and commit, then insert the key
in a second commit. Two concurrent requests with the same key could both miss the
lookup and both transfer, and the loser's insert then hit the primary key (a 500).

Now the key row is inserted *first*, in the same transaction as the transfer, with
``INSERT ... ON CONFLICT DO NOTHING``. On PostgreSQL (READ COMMITTED) that gives:

* No competitor: the insert wins, the caller does the work, stores the response on
  the row and commits. Key and transfer become visible together.
* A competitor that already committed: the insert does nothing, and a fresh SELECT
  (READ COMMITTED takes a new snapshot per statement) returns its stored response.
* A competitor still in flight: the insert *waits* on the unique index until that
  transaction ends. If it commits we get the case above; if it rolls back (e.g. the
  transfer failed) our insert goes through and we do the work ourselves.

So the unique index serialises duplicates. There is never a second transfer, never a
primary-key error, and a failed transfer rolls its key back with it (the key is not
burned). Keys are scoped per user: (user_id, key) is the primary key.
"""

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyKey


class IdempotencyConflict(Exception):
    """The key was already used by this user for a different request body."""


def claim(db: Session, user_id: int, key: str, request_hash: str) -> dict | None:
    """Claim ``key`` for ``user_id`` in the caller's open transaction.

    Returns ``None`` if this request now owns the key: the caller must do its work,
    call :func:`save_response` and commit (or roll back, which releases the key).
    Returns the stored response if an earlier request with the same body completed.
    Raises :class:`IdempotencyConflict` if the key was used with a different body.
    """
    claimed = db.execute(
        insert(IdempotencyKey)
        .values(user_id=user_id, key=key, request_hash=request_hash)
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
        .returning(IdempotencyKey.key)
    ).first()
    if claimed is not None:
        return None

    # Someone else holds the key, and their transaction has committed (otherwise the
    # insert above would still be waiting), so their row is complete.
    row = db.execute(
        select(IdempotencyKey.request_hash, IdempotencyKey.response_json).where(
            IdempotencyKey.user_id == user_id, IdempotencyKey.key == key
        )
    ).one()
    if row.request_hash != request_hash:
        raise IdempotencyConflict(key)
    return row.response_json


def save_response(db: Session, user_id: int, key: str, response: dict) -> None:
    """Attach the response to a key claimed in this transaction. Does not commit."""
    db.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
        .values(response_json=response)
    )
