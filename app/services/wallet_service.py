from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.wallet import Wallet


def open_wallet(db: Session, account_id: int, currency: str) -> Wallet:
    w = Wallet(account_id=account_id, currency=currency.upper(), balance_minor=0)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def list_wallets(db: Session, account_id: int) -> list[Wallet]:
    return list(
        db.execute(select(Wallet).where(Wallet.account_id == account_id)).scalars()
    )
