from app.config import Settings


def test_database_url_rewrites_postgres_scheme():
    s = Settings(database_url="postgres://user:pass@host/db?sslmode=require")
    assert s.database_url == "postgresql+psycopg://user:pass@host/db?sslmode=require"


def test_database_url_rewrites_postgresql_scheme():
    s = Settings(database_url="postgresql://user:pass@host/db?sslmode=require")
    assert s.database_url == "postgresql+psycopg://user:pass@host/db?sslmode=require"


def test_database_url_leaves_psycopg_scheme_untouched():
    url = "postgresql+psycopg://user:pass@host/db?sslmode=require"
    s = Settings(database_url=url)
    assert s.database_url == url
