import threading

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.account import Account
from app.models.ledger import LedgerEntry
from app.models.wallet import Wallet
from app.services.account_service import create_account
from app.services.auth_service import register_user
from app.services.transfer_service import (
    TREASURY_ACCOUNT_NAME,
    InsufficientFunds,
    deposit,
    transfer,
)
from app.services.wallet_service import open_wallet


def test_no_lost_updates_under_concurrency(db):
    u = register_user(db, "conc@x.com", "secret123")
    a1 = create_account(db, u.id, "Main")
    a2 = create_account(db, u.id, "Savings")
    src = open_wallet(db, a1.id, "GBP")
    dst = open_wallet(db, a2.id, "GBP")
    deposit(db, src.id, 1000, "GBP")  # exactly enough for 10 x 100
    src_id, dst_id = src.id, dst.id

    errors: list[Exception] = []

    def worker():
        try:
            with SessionLocal() as s:
                transfer(s, src_id, dst_id, 100, "GBP")
        except InsufficientFunds:
            pass
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    with SessionLocal() as s:
        sb = s.get(Wallet, src_id).balance_minor
        dbal = s.get(Wallet, dst_id).balance_minor
        assert sb >= 0  # source never overdrawn
        assert sb + dbal == 1000  # money conserved
        assert dbal == 1000  # all 10 fundable transfers succeeded


def test_no_deadlock_between_demo_deposits_and_transfers_to_treasury(db):
    """Demo deposits into a wallet, running alongside transfers from that wallet to the
    treasury, must not deadlock.

    ``_treasury_wallet`` used to lock the treasury row with ``with_for_update`` before
    ``_post_transfer``'s id-ordered locking ran. A deposit (which locks the treasury
    first, then the user's wallet, out of id order once the treasury is created after
    the wallet) and a direct transfer to the treasury (which locks both in id order)
    could then each hold the lock the other was waiting on: classic deadlock. This
    reproduces it by priming the wallet (lower id) and the treasury (created after,
    higher id) first, then racing deposits into the wallet against transfers out of it
    to the treasury.
    """
    u = register_user(db, "treasury-race@x.com", "secret123")
    a = create_account(db, u.id, "Main")
    w = open_wallet(db, a.id, "GBP")
    w_id = w.id

    # Prime the treasury wallet so it exists with a higher id than w_id -- the
    # ordering under which the old code deadlocked.
    deposit(db, w_id, 100_000, "GBP")
    treasury_id = db.execute(
        select(Wallet.id)
        .join(Account, Account.id == Wallet.account_id)
        .where(Account.name == TREASURY_ACCOUNT_NAME, Wallet.currency == "GBP")
    ).scalar_one()
    assert treasury_id > w_id  # the vulnerable ordering

    errors: list[Exception] = []

    def deposit_worker():
        try:
            with SessionLocal() as s:
                deposit(s, w_id, 100, "GBP")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def transfer_to_treasury_worker():
        try:
            with SessionLocal() as s:
                transfer(s, w_id, treasury_id, 10, "GBP")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=deposit_worker) for _ in range(20)] + [
        threading.Thread(target=transfer_to_treasury_worker) for _ in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, [repr(e) for e in errors]  # no 500s / DeadlockDetected

    with SessionLocal() as s:
        w_balance = s.get(Wallet, w_id).balance_minor
        w_ledger_sum = s.execute(
            select(func.sum(LedgerEntry.amount_minor)).where(
                LedgerEntry.wallet_id == w_id
            )
        ).scalar_one()
        assert w_balance == w_ledger_sum
        # 100_000 primer + 20 x 100 deposits - 20 x 10 transfers out
        assert w_balance == 100_000 + 20 * 100 - 20 * 10

        global_sum = s.execute(select(func.sum(LedgerEntry.amount_minor))).scalar_one()
        assert global_sum == 0
