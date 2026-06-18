from app.services.account_service import create_account
from app.services.auth_service import register_user
from app.services.wallet_service import list_wallets, open_wallet


def test_open_wallet_starts_at_zero(db_session):
    u = register_user(db_session, "w@x.com", "secret123")
    a = create_account(db_session, u.id, "Main")
    w = open_wallet(db_session, a.id, "GBP")
    assert w.currency == "GBP"
    assert w.balance_minor == 0
    assert len(list_wallets(db_session, a.id)) == 1
