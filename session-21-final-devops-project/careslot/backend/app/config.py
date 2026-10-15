"""Application settings, read from environment variables (Kubernetes ConfigMap + Secret)."""
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CareSlot API"
    app_version: str = "2.0.0"
    app_env: str = "local"
    log_level: str = "INFO"
    clinic_name: str = "CareSlot Clinic"
    # Comma-separated list of browser origins allowed by CORS (no wildcard - flagged by Semgrep).
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://careslot.local"
    # Either a full DATABASE_URL, or the individual DB_* parts (preferred in Kubernetes).
    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "careslot"
    db_user: str = "careslot"
    db_password: str = "careslot"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        # Credentials are URL-encoded: a password like "Saniya@123" would otherwise break host parsing.
        return (f"postgresql+psycopg://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}")

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
