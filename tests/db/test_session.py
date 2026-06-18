from sqlalchemy import text

from app.db.session import SessionLocal


def test_session_executes_select_one():
    with SessionLocal() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1
