from pydantic import BaseModel, field_validator


class TransferIn(BaseModel):
    from_wallet_id: int
    to_wallet_id: int
    amount_minor: int
    currency: str

    @field_validator("amount_minor")
    @classmethod
    def positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_minor must be positive")
        return v


class TransferOut(BaseModel):
    transaction_id: int
    status: str
