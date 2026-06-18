from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import current_user
from app.models.user import User
from app.schemas.account import AccountIn, AccountOut
from app.services.account_service import create_account, list_accounts

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut, status_code=201)
def create(
    body: AccountIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AccountOut:
    acc = create_account(db, user.id, body.name)
    return AccountOut(id=acc.id, name=acc.name)


@router.get("", response_model=list[AccountOut])
def index(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[AccountOut]:
    return [AccountOut(id=a.id, name=a.name) for a in list_accounts(db, user.id)]
