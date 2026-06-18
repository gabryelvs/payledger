from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise ValueError("amount_minor must be an int (minor units)")
        cur = self.currency.upper()
        if len(cur) != 3 or not cur.isalpha():
            raise ValueError("currency must be a 3-letter ISO 4217 code")
        object.__setattr__(self, "currency", cur)

    def is_same_currency(self, other: "Money") -> bool:
        return self.currency == other.currency

    def __add__(self, other: "Money") -> "Money":
        if not self.is_same_currency(other):
            raise ValueError("currency mismatch")
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount_minor, self.currency)
