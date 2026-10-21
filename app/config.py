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
    integration_database_url: str | None = None
    migration_database_url: str | None = None
    maintenance_database_url: str | None = None
    enforce_database_security: bool = False
    mandatory_review_recipients: tuple[str, ...] = ('Kämmerei',)
    clamav_executable: Path | None = None
    clamav_database_dir: Path | None = None
    scanner_timeout: int = 60
    scanner_max_age_hours: int = 72
    dms_allowed_hosts: tuple[str,...] = ()

    @property
    def production(self) -> bool:
        return self.environment == "production"

    def validate(self) -> None:
        from app.documents import validate_storage_setting
        validate_storage_setting(self.document_storage_dir)
        if self.clamav_executable is not None and not self.clamav_executable.is_absolute():
            raise ValueError('CLAMAV_EXECUTABLE must be an absolute administrator-controlled path')
        if self.clamav_database_dir is not None and not self.clamav_database_dir.is_absolute():
            raise ValueError('CLAMAV_DATABASE_DIR must be an absolute administrator-controlled path')
        if not 1 <= self.scanner_timeout <= 300 or not 1 <= self.scanner_max_age_hours <= 168:
            raise ValueError('Scanner timeout/freshness settings outside supported bounds')
        from app.options import REVIEW_RECIPIENTS
        if not self.mandatory_review_recipients or any(not x.strip() for x in self.mandatory_review_recipients):
            raise ValueError('At least one mandatory approval recipient must be configured')
        if any(x not in REVIEW_RECIPIENTS for x in self.mandatory_review_recipients):
            raise ValueError('Mandatory approval recipients must use configured review catalog values')
        if self.environment not in ("development", "production"):
            raise ValueError("APP_ENV muss development oder production sein")
        if not self.allowed_hosts or any(x in ("*", "") for x in self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS muss konkrete Hostnamen enthalten")
        if self.production:
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Produktion erfordert PostgreSQL via psycopg")
            if "testserver" in self.allowed_hosts or "localhost" in self.allowed_hosts:
                raise ValueError("Produktion erfordert ausdrücklich konfigurierte Hostnamen")
            if not self.enforce_database_security or not self.integration_database_url:
                raise ValueError('Production requires restricted web/integration database connections and RLS validation')
        if self.enforce_database_security and (not self.database_url.startswith('postgresql+psycopg://') or
                not self.integration_database_url or not self.integration_database_url.startswith('postgresql+psycopg://')):
            raise ValueError('Database security requires PostgreSQL web and integration URLs')


def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "development").strip().lower()
    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/vertragsregister.sqlite3")
    defaults = "localhost,127.0.0.1" if environment == "development" else ""
    hosts = tuple(x.strip() for x in os.getenv("ALLOWED_HOSTS", defaults).split(",") if x.strip())
    storage = Path(os.getenv("DOCUMENT_STORAGE_DIR", str(Settings.document_storage_dir))).expanduser()
    settings = Settings(environment=environment, database_url=db_url, allowed_hosts=hosts,
                        document_storage_dir=storage,
                        clamav_executable=Path(os.environ['CLAMAV_EXECUTABLE']) if os.getenv('CLAMAV_EXECUTABLE') else None,
                        clamav_database_dir=Path(os.environ['CLAMAV_DATABASE_DIR']) if os.getenv('CLAMAV_DATABASE_DIR') else None,
                        scanner_timeout=int(os.getenv('SCANNER_TIMEOUT','60')),
                        scanner_max_age_hours=int(os.getenv('SCANNER_MAX_AGE_HOURS','72')),
                        dms_allowed_hosts=tuple(x.strip().casefold() for x in os.getenv('DMS_ALLOWED_HOSTS','').split(',') if x.strip()),
                        mandatory_review_recipients=tuple(x.strip() for x in os.getenv('MANDATORY_REVIEW_RECIPIENTS','Kämmerei').split(',') if x.strip()),
                        integration_database_url=os.getenv('INTEGRATION_DATABASE_URL') or None,
                        migration_database_url=os.getenv('MIGRATION_DATABASE_URL') or None,
                        maintenance_database_url=os.getenv('MAINTENANCE_DATABASE_URL') or None,
                        enforce_database_security=os.getenv('ENFORCE_DATABASE_SECURITY', '1' if environment=='production' else '0')=='1')
    settings.validate()
    return settings
