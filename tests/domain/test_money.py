import pytest

from app.domain.money import Money


def test_add_same_currency():
    assert Money(100, "GBP") + Money(50, "GBP") == Money(150, "GBP")


def test_add_different_currency_raises():
    with pytest.raises(ValueError):
        Money(100, "GBP") + Money(50, "USD")


def test_negate():
    assert -Money(100, "GBP") == Money(-100, "GBP")


def test_rejects_float_amount():
    with pytest.raises(ValueError):
        Money(1.5, "GBP")  # type: ignore[arg-type]


def test_normalises_currency_case_and_length():
    assert Money(100, "gbp").currency == "GBP"
    with pytest.raises(ValueError):
        Money(100, "POUND")
