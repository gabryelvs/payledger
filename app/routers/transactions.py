from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.errors import error_response
from app.models.account import Account
from app.models.ledger import LedgerEntry, Transaction
from app.models.user import User
from app.models.wallet import Wallet

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _touches_user(db: Session, txn_id: int, user_id: int) -> bool:
    """A transaction is the user's if any of its entries hits one of their wallets."""
    hit = db.execute(
        select(LedgerEntry.id)
        .join(Wallet, Wallet.id == LedgerEntry.wallet_id)
        .join(Account, Account.id == Wallet.account_id)
        .where(LedgerEntry.transaction_id == txn_id, Account.user_id == user_id)
        .limit(1)
    ).first()
    return hit is not None


@router.get("/{txn_id}", response_model=None)
def get_txn(
    txn_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict | JSONResponse:
    txn = db.get(Transaction, txn_id)
    # Same 404 for "missing" and "not yours", so transaction ids can't be probed.
    if txn is None or not _touches_user(db, txn_id, user.id):
        return error_response(404, "TRANSACTION_NOT_FOUND", "transaction does not exist")
    entries = db.execute(
        select(LedgerEntry).where(LedgerEntry.transaction_id == txn_id)
    ).scalars()
    return {
        "id": txn.id,
        "type": txn.type,
        "status": txn.status,
        "entries": [
            {
                "wallet_id": e.wallet_id,
                "amount_minor": e.amount_minor,
                "currency": e.currency,
            }
            for e in entries
        ],
    }
