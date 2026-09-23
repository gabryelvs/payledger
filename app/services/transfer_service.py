from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ledger import LedgerEntry, Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.security.passwords import hash_password
from app.services.events import record_event
from app.services.ledger import assert_balanced
from app.services.wallet_service import get_owned_wallet

TREASURY_ACCOUNT_NAME = "__treasury__"
TREASURY_OPENING_BALANCE = 10**18  # represents the money-supply source


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
    *,
    owner_user_id: int | None = None,
) -> Transaction:
    """Move money between two wallets as one balanced, committed transaction.

    ``owner_user_id`` is the caller for user-initiated transfers: the *source* wallet
    must belong to them (the destination may belong to anyone). A source they do not
    own raises ``WalletNotFound``, exactly like a missing one. System movements such
    as treasury deposits pass ``None``.
    """
    if amount_minor <= 0:
        raise ValueError("amount_minor must be positive")
    currency = currency.upper()

    if owner_user_id is not None and (
        get_owned_wallet(db, owner_user_id, from_wallet_id) is None
    ):
        raise WalletNotFound(from_wallet_id)

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

    record_event(
        db,
        "transfer.completed",
        {
            "transaction_id": txn.id,
            "from_wallet_id": src.id,
            "to_wallet_id": dst.id,
            "amount_minor": amount_minor,
            "currency": currency,
        },
    )

    db.commit()
    db.refresh(txn)
    return txn


def _ensure_system_user(db: Session) -> int:
    sys = db.execute(
        select(User).where(User.email == "system@payledger")
    ).scalar_one_or_none()
    if sys is None:
        sys = User(email="system@payledger", password_hash=hash_password("disabled"))
        db.add(sys)
        db.flush()
    return sys.id


def _treasury_wallet(db: Session, currency: str) -> Wallet:
    acc = db.execute(
        select(Account).where(Account.name == TREASURY_ACCOUNT_NAME)
    ).scalar_one_or_none()
    if acc is None:
        acc = Account(user_id=_ensure_system_user(db), name=TREASURY_ACCOUNT_NAME)
        db.add(acc)
        db.flush()
    w = db.execute(
        select(Wallet)
        .where(Wallet.account_id == acc.id, Wallet.currency == currency)
        .with_for_update()
    ).scalar_one_or_none()
    if w is None:
        w = Wallet(
            account_id=acc.id,
            currency=currency,
            balance_minor=TREASURY_OPENING_BALANCE,
        )
        db.add(w)
        db.flush()
    return w


def deposit(
    db: Session, wallet_id: int, amount_minor: int, currency: str
) -> Transaction:
    if amount_minor <= 0:
        raise ValueError("amount_minor must be positive")
    currency = currency.upper()
    treasury = _treasury_wallet(db, currency)
    return transfer(db, treasury.id, wallet_id, amount_minor, currency)
