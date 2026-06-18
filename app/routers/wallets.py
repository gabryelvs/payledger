from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.models.user import User
from app.schemas.wallet import WalletIn, WalletOut
from app.services.wallet_service import list_wallets, open_wallet

router = APIRouter(prefix="/accounts/{account_id}/wallets", tags=["wallets"])


@router.post("", response_model=WalletOut, status_code=201)
def open_(
    account_id: int,
    body: WalletIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> WalletOut:
    w = open_wallet(db, account_id, body.currency)
    return WalletOut(id=w.id, currency=w.currency, balance_minor=w.balance_minor)


@router.get("", response_model=list[WalletOut])
def index(
    account_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[WalletOut]:
    return [
        WalletOut(id=w.id, currency=w.currency, balance_minor=w.balance_minor)
        for w in list_wallets(db, account_id)
    ]
