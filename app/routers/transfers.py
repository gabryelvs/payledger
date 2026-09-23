import hashlib
import json

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.errors import error_response
from app.models.user import User
from app.schemas.transfer import TransferIn
from app.services.idempotency import IdempotencyConflict, lookup, remember
from app.services.transfer_service import (
    CurrencyMismatch,
    InsufficientFunds,
    WalletNotFound,
    transfer,
)

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _hash(body: TransferIn) -> str:
    payload = json.dumps(body.model_dump(), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


@router.post("")
def make_transfer(
    body: TransferIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JSONResponse:
    req_hash = _hash(body)

    if idempotency_key:
        try:
            cached = lookup(db, idempotency_key, req_hash)
        except IdempotencyConflict:
            return error_response(
                409, "IDEMPOTENCY_CONFLICT", "key reused with a different request body"
            )
        if cached is not None:
            return JSONResponse(status_code=201, content=cached)

    try:
        txn = transfer(
            db,
            body.from_wallet_id,
            body.to_wallet_id,
            body.amount_minor,
            body.currency,
            idempotency_key,
            owner_user_id=user.id,
        )
    except InsufficientFunds:
        return error_response(
            422, "INSUFFICIENT_FUNDS", "source wallet has insufficient balance"
        )
    except CurrencyMismatch:
        return error_response(
            422, "CURRENCY_MISMATCH", "wallet currency does not match transfer"
        )
    except WalletNotFound:
        return error_response(404, "WALLET_NOT_FOUND", "wallet does not exist")

    result = {"transaction_id": txn.id, "status": txn.status}
    if idempotency_key:
        remember(db, idempotency_key, req_hash, result)
    return JSONResponse(status_code=201, content=result)
