from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent


def record_event(db: Session, type_: str, payload: dict) -> WebhookEvent:
    ev = WebhookEvent(type=type_, payload_json=payload)
    db.add(ev)
    return ev  # flushed/committed by the caller's transaction
