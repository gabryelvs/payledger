from pydantic import BaseModel, field_validator


class WalletIn(BaseModel):
    currency: str

    @field_validator("currency")
    @classmethod
    def upper3(cls, v: str) -> str:
        v = v.upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError("currency must be 3-letter ISO code")
        return v


class WalletOut(BaseModel):
    id: int
    currency: str
    balance_minor: int


class DemoDepositIn(BaseModel):
    amount_minor: int

    @field_validator("amount_minor")
    @classmethod
    def positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_minor must be positive")
        return v


class DemoDepositOut(BaseModel):
    transaction_id: int
    status: str
    balance_minor: int
