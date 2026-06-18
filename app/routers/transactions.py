from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.models.ledger import LedgerEntry, Transaction
from app.models.user import User

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/{txn_id}")
def get_txn(
    txn_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    txn = db.get(Transaction, txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="transaction not found")
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
