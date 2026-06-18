import pytest

from app.services.auth_service import EmailTakenError, register_user


def test_register_hashes_password_and_stores_user(db_session):
    user = register_user(db_session, "a@b.com", "secret123")
    assert user.id is not None
    assert user.email == "a@b.com"
    assert user.password_hash != "secret123"


def test_register_duplicate_email_raises(db_session):
    register_user(db_session, "a@b.com", "secret123")
    with pytest.raises(EmailTakenError):
        register_user(db_session, "a@b.com", "other123")
