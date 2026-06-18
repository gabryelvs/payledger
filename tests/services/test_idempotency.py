import pytest

from app.services.idempotency import IdempotencyConflict, lookup, remember


def test_lookup_returns_stored_response(db):
    remember(db, "k1", "hashA", {"id": 7})
    assert lookup(db, "k1", "hashA") == {"id": 7}


def test_unknown_key_returns_none(db):
    assert lookup(db, "missing", "hashA") is None


def test_same_key_different_request_conflicts(db):
    remember(db, "k1", "hashA", {"id": 7})
    with pytest.raises(IdempotencyConflict):
        lookup(db, "k1", "hashB")
