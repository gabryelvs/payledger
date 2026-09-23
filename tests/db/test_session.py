from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.db.session import SessionLocal, engine_options


def test_session_executes_select_one():
    with SessionLocal() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1


def test_engine_options_on_vercel_uses_nullpool_and_disables_prepared_statements():
    opts = engine_options({"VERCEL": "1"})
    assert opts == {
        "poolclass": NullPool,
        "connect_args": {"prepare_threshold": None},
    }


def test_engine_options_off_vercel_keeps_default_pool_with_pre_ping():
    opts = engine_options({})
    assert opts == {"pool_pre_ping": True}
