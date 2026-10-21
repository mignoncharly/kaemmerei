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
    request_max_bytes: int = 32 * 1024 * 1024
    request_timeout_seconds: int = 30
    request_concurrency: int = 16
    upload_concurrency: int = 4
    form_max_fields: int = 40
    form_max_files: int = 5
    form_field_bytes: int = 64 * 1024
    trusted_proxy_networks: tuple[str, ...] = ()
    database_pool_size: int = 8
    database_pool_timeout: int = 5
    database_statement_timeout_ms: int = 15000
    document_storage_quota_bytes: int = 10 * 1024**3
    document_storage_reserve_bytes: int = 256 * 1024**2
    defer_document_scans: bool = False

    @property
    def queued_document_scans(self) -> bool:
        # Production never waits for antivirus in the HTTP worker. Development
        # preserves the existing immediate synthetic scanner workflow by default.
        return self.production or self.defer_document_scans

    @property
    def production(self) -> bool:
        return self.environment == "production"

    def validate(self) -> None:
        from ipaddress import ip_network
        for network in self.trusted_proxy_networks:
            if ip_network(network).prefixlen == 0:
                raise ValueError('Trust only explicit proxy networks, never all addresses')
        if not 1024 <= self.request_max_bytes <= 64 * 1024 * 1024:
            raise ValueError('Request byte limit must be between 1 KiB and 64 MiB')
        if not 1 <= self.request_timeout_seconds <= 120:
            raise ValueError('Request receive/parse deadline must be between 1 and 120 seconds')
        if not 1 <= self.upload_concurrency <= self.request_concurrency <= 64:
            raise ValueError('Concurrency must be bounded, with uploads <= all requests')
        if not 1<=self.database_pool_size<=32 or not 1<=self.database_pool_timeout<=30 or not 1000<=self.database_statement_timeout_ms<=120000:
            raise ValueError('Invalid bounded database pool/query settings')
        if self.document_storage_quota_bytes<1024 or self.document_storage_reserve_bytes<0:
            raise ValueError('Invalid private storage quota/reserve')
        if not 1 <= self.form_max_fields <= 100 or not 1 <= self.form_max_files <= 5 or not 1024 <= self.form_field_bytes <= 65536:
            raise ValueError('Invalid form limits')
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
            from sqlalchemy.engine import make_url
            for raw in (self.database_url, self.integration_database_url):
                url = make_url(raw)
                if url.query.get('sslmode')!='verify-full' or not url.query.get('sslrootcert'):
                    raise ValueError('Production database connections require sslmode=verify-full and sslrootcert')
                if not Path(url.query['sslrootcert']).is_absolute():
                    raise ValueError('Production database CA certificate must be an absolute path')
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
                        request_max_bytes=int(os.getenv('REQUEST_MAX_BYTES', str(32 * 1024 * 1024))),
                        request_timeout_seconds=int(os.getenv('REQUEST_TIMEOUT_SECONDS','30')),
                        request_concurrency=int(os.getenv('REQUEST_CONCURRENCY','16')),
                        upload_concurrency=int(os.getenv('UPLOAD_CONCURRENCY','4')),
                        form_max_fields=int(os.getenv('FORM_MAX_FIELDS','40')),
                        form_max_files=int(os.getenv('FORM_MAX_FILES','5')),
                        form_field_bytes=int(os.getenv('FORM_FIELD_BYTES','65536')),
                        trusted_proxy_networks=tuple(x.strip() for x in os.getenv('TRUSTED_PROXY_NETWORKS','').split(',') if x.strip()),
                        database_pool_size=int(os.getenv('DATABASE_POOL_SIZE','8')),
                        database_pool_timeout=int(os.getenv('DATABASE_POOL_TIMEOUT','5')),
                        database_statement_timeout_ms=int(os.getenv('DATABASE_STATEMENT_TIMEOUT_MS','15000')),
                        document_storage_quota_bytes=int(os.getenv('DOCUMENT_STORAGE_QUOTA_BYTES',str(10*1024**3))),
                        document_storage_reserve_bytes=int(os.getenv('DOCUMENT_STORAGE_RESERVE_BYTES',str(256*1024**2))),
                        defer_document_scans=os.getenv('DEFER_DOCUMENT_SCANS','0')=='1',
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
