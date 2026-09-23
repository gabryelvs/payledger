from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyKey(Base):
    """A client-supplied Idempotency-Key and the response it produced.

    Keys are scoped per user, so the primary key is (user_id, key). That unique index
    is also what makes claiming a key atomic: see app/services/idempotency.py.
    """

    __tablename__ = "idempotency_keys"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    # NULL only inside the transaction that claimed the key; it is filled in before
    # that transaction commits, so other transactions only ever see it populated.
    response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
