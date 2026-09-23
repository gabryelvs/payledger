from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
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


def get_owned_wallet(
    db: Session, user_id: int, wallet_id: int, account_id: int | None = None
) -> Wallet | None:
    """The wallet, or None if it does not exist or the user does not own it.

    With ``account_id`` the wallet must also sit in that account, so nested routes
    (``/accounts/{account_id}/wallets/{wallet_id}``) cannot mix one user's account
    id with another user's wallet id.
    """
    q = (
        select(Wallet)
        .join(Account, Account.id == Wallet.account_id)
        .where(Wallet.id == wallet_id, Account.user_id == user_id)
    )
    if account_id is not None:
        q = q.where(Wallet.account_id == account_id)
    return db.execute(q).scalar_one_or_none()
