from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account


def create_account(db: Session, user_id: int, name: str) -> Account:
    acc = Account(user_id=user_id, name=name)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


def list_accounts(db: Session, user_id: int) -> list[Account]:
    return list(db.execute(select(Account).where(Account.user_id == user_id)).scalars())


def get_owned_account(db: Session, user_id: int, account_id: int) -> Account | None:
    """The account, or None if it does not exist *or* belongs to someone else.

    Callers turn None into a 404 either way, so a caller cannot probe which ids exist.
    """
    return db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    ).scalar_one_or_none()
