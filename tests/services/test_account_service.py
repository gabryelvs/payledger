from app.services.account_service import create_account, list_accounts
from app.services.auth_service import register_user


def test_create_and_list_accounts(db_session):
    u = register_user(db_session, "acc@x.com", "secret123")
    a = create_account(db_session, u.id, "Main")
    assert a.id is not None
    assert [x.id for x in list_accounts(db_session, u.id)] == [a.id]
