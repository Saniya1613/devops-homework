from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All settings come from environment variables (Kubernetes ConfigMap + Secret)."""
    app_name: str = "TaskBoard API"
    app_env: str = "local"
    log_level: str = "INFO"
    # Either give a full DATABASE_URL, or the individual DB_* parts (preferred in Kubernetes).
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "taskboard"
    db_user: str = "taskboard"
    db_password: str = "taskboard"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        # URL-encode credentials: a password such as "Saniya@123" contains "@", which would otherwise
        # be parsed as the user/host separator (found when the CI deploy job crashed with
        # "Name or service not known").
        return (f"postgresql+psycopg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")


settings = Settings()
