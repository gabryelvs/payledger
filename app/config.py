from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://payledger:payledger@localhost:5432/payledger"
    jwt_secret: str = "change-me-in-prod"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 7
    # Demo only: lets users fund their own wallets from the treasury via
    # POST /accounts/{id}/wallets/{wid}/demo-deposit. Off unless the deployment
    # sets DEMO_DEPOSITS_ENABLED=true (the public demo does; see README).
    demo_deposits_enabled: bool = False

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """Neon (and most managed Postgres providers) hand out postgres:// or
        postgresql:// connection strings, but SQLAlchemy needs the psycopg3
        driver named explicitly to pick the right DBAPI. Rewrite only the
        scheme; leave the rest of the URL (host, query params like
        sslmode/channel_binding) untouched. A URL that already names the
        driver is returned as-is.
        """
        for scheme in ("postgres://", "postgresql://"):
            if v.startswith(scheme):
                return "postgresql+psycopg://" + v[len(scheme) :]
        return v


settings = Settings()
