from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.errors import error_response
from app.models.ledger import LedgerEntry
from app.models.user import User
from app.schemas.wallet import DemoDepositIn, DemoDepositOut, WalletIn, WalletOut
from app.services.account_service import get_owned_account
from app.services.demo_deposits import (
    DEMO_DEPOSIT_MAX_MINOR,
    DemoDepositLimitExceeded,
    DemoDepositsDisabled,
    demo_deposit,
)
from app.services.transfer_service import WalletNotFound
from app.services.wallet_service import get_owned_wallet, list_wallets, open_wallet

router = APIRouter(prefix="/accounts/{account_id}/wallets", tags=["wallets"])


# Someone else's account or wallet gets the same 404 as a missing one, so ids
# belonging to other users cannot be discovered by probing.
def _account_not_found() -> JSONResponse:
    return error_response(404, "ACCOUNT_NOT_FOUND", "account does not exist")


def _wallet_not_found() -> JSONResponse:
    return error_response(404, "WALLET_NOT_FOUND", "wallet does not exist")


@router.post("", response_model=WalletOut, status_code=201)
def open_(
    account_id: int,
    body: WalletIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> WalletOut | JSONResponse:
    if get_owned_account(db, user.id, account_id) is None:
        return _account_not_found()
    w = open_wallet(db, account_id, body.currency)
    return WalletOut(id=w.id, currency=w.currency, balance_minor=w.balance_minor)


@router.get("", response_model=list[WalletOut])
def index(
    account_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[WalletOut] | JSONResponse:
    if get_owned_account(db, user.id, account_id) is None:
        return _account_not_found()
    return [
        WalletOut(id=w.id, currency=w.currency, balance_minor=w.balance_minor)
        for w in list_wallets(db, account_id)
    ]


@router.get("/{wallet_id}/statement", response_model=None)
def statement(
    account_id: int,
    wallet_id: int,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict] | JSONResponse:
    if get_owned_wallet(db, user.id, wallet_id, account_id=account_id) is None:
        return _wallet_not_found()
    rows = db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.wallet_id == wallet_id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    ).scalars()
    return [
        {
            "transaction_id": e.transaction_id,
            "amount_minor": e.amount_minor,
            "currency": e.currency,
        }
        for e in rows
    ]


@router.post(
    "/{wallet_id}/demo-deposit",
    response_model=DemoDepositOut,
    status_code=201,
    summary="Demo only: fund your own wallet from the treasury",
    description=(
        "Credits one of the caller's own wallets from the system treasury, as a "
        "normal balanced ledger transaction. Capped at "
        f"{DEMO_DEPOSIT_MAX_MINOR} minor units per call. Only available when the "
        "deployment sets DEMO_DEPOSITS_ENABLED=true; otherwise returns 403."
    ),
)
def demo_deposit_(
    account_id: int,
    wallet_id: int,
    body: DemoDepositIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> DemoDepositOut | JSONResponse:
    try:
        txn, balance = demo_deposit(db, user.id, account_id, wallet_id, body.amount_minor)
    except DemoDepositsDisabled:
        return error_response(
            403, "DEMO_DEPOSITS_DISABLED", "demo deposits are not enabled on this server"
        )
    except WalletNotFound:
        return _wallet_not_found()
    except DemoDepositLimitExceeded:
        return error_response(
            422,
            "DEMO_DEPOSIT_LIMIT_EXCEEDED",
            f"demo deposits are capped at {DEMO_DEPOSIT_MAX_MINOR} minor units per call",
        )
    return DemoDepositOut(transaction_id=txn.id, status=txn.status, balance_minor=balance)
