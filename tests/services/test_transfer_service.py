import pytest

from app.models.wallet import Wallet
from app.services.account_service import create_account
from app.services.auth_service import register_user
from app.services.transfer_service import (
    CurrencyMismatch,
    InsufficientFunds,
    transfer,
)
from app.services.wallet_service import open_wallet


def _two_wallets(db, fund=1000):
    u = register_user(db, "t@x.com", "secret123")
    a1 = create_account(db, u.id, "Main")
    a2 = create_account(db, u.id, "Savings")
    w1 = open_wallet(db, a1.id, "GBP")
    w2 = open_wallet(db, a2.id, "GBP")
    w1.balance_minor = fund
    db.commit()
    return w1, w2


def test_transfer_moves_funds_and_balances_to_zero_sum(db):
    w1, w2 = _two_wallets(db)
    txn = transfer(db, w1.id, w2.id, 300, "GBP")
    assert db.get(Wallet, w1.id).balance_minor == 700
    assert db.get(Wallet, w2.id).balance_minor == 300
    assert txn.status == "completed"


def test_insufficient_funds_raises_and_no_change(db):
    w1, w2 = _two_wallets(db, fund=100)
    with pytest.raises(InsufficientFunds):
        transfer(db, w1.id, w2.id, 300, "GBP")
    assert db.get(Wallet, w1.id).balance_minor == 100


def test_currency_mismatch_raises(db):
    u = register_user(db, "c@x.com", "secret123")
    a = create_account(db, u.id, "Main")
    g = open_wallet(db, a.id, "GBP")
    usd = open_wallet(db, a.id, "USD")
    g.balance_minor = 1000
    db.commit()
    with pytest.raises(CurrencyMismatch):
        transfer(db, g.id, usd.id, 100, "GBP")
