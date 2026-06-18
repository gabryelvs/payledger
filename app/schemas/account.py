from pydantic import BaseModel


class AccountIn(BaseModel):
    name: str


class AccountOut(BaseModel):
    id: int
    name: str
