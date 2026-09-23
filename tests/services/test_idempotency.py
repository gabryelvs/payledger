import pytest

from app.services.auth_service import register_user
from app.services.idempotency import IdempotencyConflict, claim, save_response


def _uid(db, email="idem@x.com"):
    return register_user(db, email, "secret123").id


def _complete(db, uid, key, request_hash, response):
    assert claim(db, uid, key, request_hash) is None
    save_response(db, uid, key, response)
    db.commit()


def test_unknown_key_is_claimed_by_the_caller(db):
    assert claim(db, _uid(db), "missing", "hashA") is None


def test_lookup_returns_stored_response(db):
    uid = _uid(db)
    _complete(db, uid, "k1", "hashA", {"id": 7})
    assert claim(db, uid, "k1", "hashA") == {"id": 7}


def test_same_key_different_request_conflicts(db):
    uid = _uid(db)
    _complete(db, uid, "k1", "hashA", {"id": 7})
    with pytest.raises(IdempotencyConflict):
        claim(db, uid, "k1", "hashB")


def test_rolled_back_claim_releases_the_key(db):
    uid = _uid(db)
    assert claim(db, uid, "k1", "hashA") is None
    db.rollback()  # e.g. the transfer failed: the key must not stay burned
    assert claim(db, uid, "k1", "hashA") is None


def test_keys_are_scoped_per_user(db):
    alice, bob = _uid(db, "alice@x.com"), _uid(db, "bob@x.com")
    _complete(db, alice, "shared-key", "hashA", {"id": 1})
    assert claim(db, bob, "shared-key", "hashB") is None
