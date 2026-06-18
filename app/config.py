from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://payledger:payledger@localhost:5432/payledger"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-prod"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 7


settings = Settings()
