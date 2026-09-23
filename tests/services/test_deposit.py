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


def test_user_account_named_like_the_treasury_is_never_used_as_one(db):
    from app.services.transfer_service import TREASURY_ACCOUNT_NAME
    from app.services.wallet_service import list_wallets

    u = register_user(db, "sneaky@x.com", "secret123")
    decoy = create_account(db, u.id, TREASURY_ACCOUNT_NAME)  # any name is allowed
    w = open_wallet(db, create_account(db, u.id, "Main").id, "GBP")

    deposit(db, w.id, 500, "GBP")

    assert db.get(Wallet, w.id).balance_minor == 500
    # The treasury wallet (opening balance 10**18) must not be minted into the decoy.
    assert list_wallets(db, decoy.id) == []
