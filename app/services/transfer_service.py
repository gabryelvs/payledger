from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger import LedgerEntry, Transaction
from app.models.wallet import Wallet
from app.services.ledger import assert_balanced


class WalletNotFound(Exception):
    pass


class CurrencyMismatch(Exception):
    pass


class InsufficientFunds(Exception):
    pass


def _lock_wallet(db: Session, wallet_id: int) -> Wallet:
    w = db.execute(
        select(Wallet).where(Wallet.id == wallet_id).with_for_update()
    ).scalar_one_or_none()
    if w is None:
        raise WalletNotFound(wallet_id)
    return w


def transfer(
    db: Session,
    from_wallet_id: int,
    to_wallet_id: int,
    amount_minor: int,
    currency: str,
    idempotency_key: str | None = None,
) -> Transaction:
    if amount_minor <= 0:
        raise ValueError("amount_minor must be positive")
    currency = currency.upper()

    # Lock wallet rows in a deterministic order to avoid deadlocks.
    first, second = sorted([from_wallet_id, to_wallet_id])
    locked = {first: _lock_wallet(db, first), second: _lock_wallet(db, second)}
    src, dst = locked[from_wallet_id], locked[to_wallet_id]

    if src.currency != currency or dst.currency != currency:
        raise CurrencyMismatch()
    if src.balance_minor < amount_minor:
        raise InsufficientFunds()

    txn = Transaction(
        type="transfer", status="completed", idempotency_key=idempotency_key
    )
    db.add(txn)
    db.flush()  # assign txn.id

    debit = LedgerEntry(
        transaction_id=txn.id,
        wallet_id=src.id,
        amount_minor=-amount_minor,
        currency=currency,
    )
    credit = LedgerEntry(
        transaction_id=txn.id,
        wallet_id=dst.id,
        amount_minor=amount_minor,
        currency=currency,
    )
    assert_balanced([debit, credit])
    db.add_all([debit, credit])

    src.balance_minor -= amount_minor
    dst.balance_minor += amount_minor

    db.commit()
    db.refresh(txn)
    return txn
