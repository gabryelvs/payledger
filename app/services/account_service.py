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
