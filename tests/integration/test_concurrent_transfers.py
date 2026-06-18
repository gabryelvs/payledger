import threading

from app.db.session import SessionLocal
from app.models.wallet import Wallet
from app.services.account_service import create_account
from app.services.auth_service import register_user
from app.services.transfer_service import InsufficientFunds, deposit, transfer
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
