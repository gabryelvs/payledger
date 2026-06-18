from app.models.wallet import Wallet
from app.services.account_service import create_account
from app.services.auth_service import register_user
from app.services.transfer_service import deposit
from app.services.wallet_service import open_wallet


def test_deposit_credits_wallet_and_stays_balanced(db):
    u = register_user(db, "d@x.com", "secret123")
    a = create_account(db, u.id, "Main")
    w = open_wallet(db, a.id, "GBP")
    deposit(db, w.id, 500, "GBP")
    assert db.get(Wallet, w.id).balance_minor == 500
