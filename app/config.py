from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://payledger:payledger@localhost:5432/payledger"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-prod"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 7
    # Demo only: lets users fund their own wallets from the treasury via
    # POST /accounts/{id}/wallets/{wid}/demo-deposit. Off unless the deployment
    # sets DEMO_DEPOSITS_ENABLED=true (the public demo does; see README).
    demo_deposits_enabled: bool = False


settings = Settings()
