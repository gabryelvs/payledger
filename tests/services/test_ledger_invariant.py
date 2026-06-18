import pytest

from app.models.ledger import LedgerEntry
from app.services.ledger import UnbalancedTransaction, assert_balanced


def _e(wallet_id, amt):
    return LedgerEntry(wallet_id=wallet_id, amount_minor=amt, currency="GBP")


def test_balanced_pair_passes():
    assert_balanced([_e(1, -100), _e(2, 100)])  # no raise


def test_unbalanced_raises():
    with pytest.raises(UnbalancedTransaction):
        assert_balanced([_e(1, -100), _e(2, 90)])
