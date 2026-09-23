import pytest
from alembic.config import Config


def test_percent_in_database_url_must_be_escaped_for_configparser():
    """configparser (which backs alembic.config.Config) treats a bare % as
    the start of interpolation syntax (e.g. %(name)s). A DATABASE_URL with
    a literal % (e.g. a URL-encoded password like p%40ss) raises unless
    migrations/env.py escapes it as %% before calling set_main_option, as
    that method's docstring documents. This proves both the failure and
    the fix, without importing migrations/env.py itself (which runs
    migrations as an import side effect).
    """
    url = "postgresql+psycopg://user:p%40ss@host/db"

    with pytest.raises(ValueError, match="interpolation"):
        Config().set_main_option("sqlalchemy.url", url)

    cfg = Config()
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    assert cfg.get_main_option("sqlalchemy.url") == url
