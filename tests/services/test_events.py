from sqlalchemy import select

from app.models.webhook_event import WebhookEvent
from app.services.account_service import create_account
from app.services.auth_service import register_user
from app.services.transfer_service import deposit, transfer
from app.services.wallet_service import open_wallet


def test_transfer_records_completed_event(db):
    u = register_user(db, "ev@x.com", "secret123")
    a1 = create_account(db, u.id, "Main")
    a2 = create_account(db, u.id, "Savings")
    w1 = open_wallet(db, a1.id, "GBP")
    w2 = open_wallet(db, a2.id, "GBP")
    deposit(db, w1.id, 500, "GBP")
    transfer(db, w1.id, w2.id, 100, "GBP")
    events = db.execute(
        select(WebhookEvent).where(WebhookEvent.type == "transfer.completed")
    ).scalars().all()
    assert len(events) >= 1
