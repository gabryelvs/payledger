import os
from collections.abc import Iterator, Mapping

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings


def engine_options(environ: Mapping[str, str]) -> dict:
    """Pick SQLAlchemy engine kwargs for the environment we're running in.

    On Vercel each invocation is its own short-lived function instance, so a
    process-local connection pool buys nothing and risks handing out
    connections that Neon has already dropped (Neon suspends compute when
    idle). NullPool makes every invocation open and close its own
    connection instead, going through Neon's pgbouncer-based pooler, which
    does the real pooling. That pooler runs in transaction mode, and
    psycopg3's automatic server-side prepared statements aren't safe under
    transaction pooling — a statement prepared on one physical connection
    can be executed against another — so prepare_threshold=None disables
    them.

    Off Vercel (local dev, tests, CI) we keep the previous behaviour: a
    normal pool with pre-ping so stale connections are detected and
    replaced rather than surfacing as errors.
    """
    if environ.get("VERCEL"):
        return {"poolclass": NullPool, "connect_args": {"prepare_threshold": None}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, **engine_options(os.environ))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
