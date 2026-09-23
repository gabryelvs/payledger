from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.ledger import LedgerEntry, Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.security.passwords import hash_password
from app.services.events import record_event
from app.services.idempotency import claim, save_response
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
    # populate_existing: if this session already holds the Wallet object (loaded
    # before the lock, e.g. by an ownership check), SQLAlchemy would otherwise keep
    # its old attribute values and we would debit a stale balance (a lost update).
    w = db.execute(
        select(Wallet)
        .where(Wallet.id == wallet_id)
        .with_for_update()
        .execution_options(populate_existing=True)
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
    txn = _post_transfer(
        db,
        from_wallet_id,
        to_wallet_id,
        amount_minor,
        currency,
        idempotency_key,
        owner_user_id=owner_user_id,
    )
    db.commit()
    db.refresh(txn)
    return txn


def submit_transfer(
    db: Session,
    user_id: int,
    from_wallet_id: int,
    to_wallet_id: int,
    amount_minor: int,
    currency: str,
    idempotency_key: str | None,
    request_hash: str,
) -> dict:
    """A user's transfer request, made idempotent when a key is supplied.

    The key claim, the ledger entries, the balance updates, the event and the stored
    response all commit (or roll back) as ONE database transaction. See
    app/services/idempotency.py for why that makes concurrent retries safe.
    Returns the response body; a replay returns the original body.
    """
    try:
        if idempotency_key:
            cached = claim(db, user_id, idempotency_key, request_hash)
            if cached is not None:
                db.rollback()  # nothing was written; just end the transaction
                return cached
        txn = _post_transfer(
            db,
            from_wallet_id,
            to_wallet_id,
            amount_minor,
            currency,
            idempotency_key,
            owner_user_id=user_id,
        )
        result = {"transaction_id": txn.id, "status": txn.status}
        if idempotency_key:
            save_response(db, user_id, idempotency_key, result)
        db.commit()
        return result
    except Exception:
        # Undo the partial transfer and release the key claim together, promptly, so a
        # concurrent duplicate waiting on the key can proceed.
        db.rollback()
        raise


def _post_transfer(
    db: Session,
    from_wallet_id: int,
    to_wallet_id: int,
    amount_minor: int,
    currency: str,
    idempotency_key: str | None,
    *,
    owner_user_id: int | None,
) -> Transaction:
    """Write a balanced transfer into the caller's open transaction. Does not commit."""
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

    db.flush()
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
    # Match on the owner as well as the name: users may name their own accounts
    # anything, including "__treasury__". The system user's address has no dot in
    # its domain, so it cannot be registered through the API.
    system_user_id = _ensure_system_user(db)
    acc = db.execute(
        select(Account).where(
            Account.name == TREASURY_ACCOUNT_NAME, Account.user_id == system_user_id
        )
    ).scalar_one_or_none()
    if acc is None:
        acc = Account(user_id=system_user_id, name=TREASURY_ACCOUNT_NAME)
        db.add(acc)
        db.flush()
    # No with_for_update here: locking the treasury row before _post_transfer's
    # id-ordered locking ran could deadlock against a direct transfer to the treasury
    # (which locks both wallets in id order from the start) -- one holding the
    # treasury lock and waiting on the wallet, the other holding the wallet lock and
    # waiting on the treasury. _lock_wallet below locks this row again, in order, once
    # _post_transfer runs, so an unlocked read here is enough: only .id is used before
    # that point.
    w = db.execute(
        select(Wallet).where(Wallet.account_id == acc.id, Wallet.currency == currency)
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
