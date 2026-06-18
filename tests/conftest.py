import pytest

from app import models  # noqa: F401  (register mappers)
from app.db.base import Base
from app.db.session import SessionLocal, engine


@pytest.fixture(autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def db(db_session):
    return db_session
