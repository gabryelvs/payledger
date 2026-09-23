"""Demo-only funding, so visitors to the public demo can try real transfers.

Money comes from the treasury through the ordinary ``deposit`` path, so every demo
deposit is a normal balanced transaction (treasury debit + wallet credit) in the
ledger. Guard rails: off unless DEMO_DEPOSITS_ENABLED=true, only into the caller's
own wallet, and capped per call.
"""

from sqlalchemy.orm import Session

from app.config import settings
from app.models.ledger import Transaction
from app.services.transfer_service import WalletNotFound, deposit
from app.services.wallet_service import get_owned_wallet

DEMO_DEPOSIT_MAX_MINOR = 100_000  # 1,000.00 in the wallet's currency, per call


class DemoDepositsDisabled(Exception):
    pass


class DemoDepositLimitExceeded(Exception):
    pass


def demo_deposit(
    db: Session, user_id: int, account_id: int, wallet_id: int, amount_minor: int
) -> tuple[Transaction, int]:
    """Credit the caller's own wallet from the treasury. Returns (txn, new balance)."""
    if not settings.demo_deposits_enabled:
        raise DemoDepositsDisabled()
    wallet = get_owned_wallet(db, user_id, wallet_id, account_id=account_id)
    if wallet is None:
        raise WalletNotFound(wallet_id)
    if amount_minor > DEMO_DEPOSIT_MAX_MINOR:
        raise DemoDepositLimitExceeded(amount_minor)
    txn = deposit(db, wallet.id, amount_minor, wallet.currency)
    db.refresh(wallet)
    return txn, wallet.balance_minor
