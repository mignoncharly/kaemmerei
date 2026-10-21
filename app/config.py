"""Explicit configuration; production fails closed for unsafe defaults."""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    database_url: str = "sqlite:///./data/vertragsregister.sqlite3"
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    session_hours: int = 8
    document_storage_dir: Path = Path(__file__).resolve().parent.parent / "data" / "documents"

    @property
    def production(self) -> bool:
        return self.environment == "production"

    def validate(self) -> None:
        if self.environment not in ("development", "production"):
            raise ValueError("APP_ENV muss development oder production sein")
        if not self.allowed_hosts or any(x in ("*", "") for x in self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS muss konkrete Hostnamen enthalten")
        if self.production:
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Produktion erfordert PostgreSQL via psycopg")
            if "testserver" in self.allowed_hosts or "localhost" in self.allowed_hosts:
                raise ValueError("Produktion erfordert ausdrücklich konfigurierte Hostnamen")


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/vertragsregister.sqlite3")
    defaults = "localhost,127.0.0.1" if environment == "development" else ""
    hosts = tuple(x.strip() for x in os.getenv("ALLOWED_HOSTS", defaults).split(",") if x.strip())
    storage = Path(os.getenv("DOCUMENT_STORAGE_DIR", str(Settings.document_storage_dir))).expanduser().resolve()
    settings = Settings(environment=environment, database_url=db_url, allowed_hosts=hosts,
                        document_storage_dir=storage)
    settings.validate()
    return settings
