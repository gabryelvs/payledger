from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        # At most one "__treasury__" account per owner. Scoped to that one name, not a
        # general per-user uniqueness rule on (user_id, name): ordinary users keep
        # being able to name an account "__treasury__" (see
        # app/services/transfer_service.py, which matches on owner + name so a user's
        # account named "__treasury__" is never mistaken for the real one). This is
        # what lets the treasury account's lazy creation use
        # INSERT ... ON CONFLICT DO NOTHING to stay race-safe under concurrent first
        # deposits. The literal must match TREASURY_ACCOUNT_NAME in
        # app/services/transfer_service.py.
        Index(
            "uq_treasury_account_per_owner",
            "user_id",
            unique=True,
            postgresql_where=text("name = '__treasury__'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
