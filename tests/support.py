"""Synthetic resources shared by pytest and the stdlib verification runner.

PostgreSQL fixtures create a random database; no supplied business DB is migrated.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy.engine import make_url

from app.config import Settings
from app.migrations import upgrade_connection
from app.models import Department, User
from app.security import ph

PASSWORD = "NurZumTesten-Starkes-Passwort-2026"


def database_identity(control, name):
    return control.execute(
        "SELECT oid, pg_get_userbyid(datdba), shobj_description(oid, 'pg_database') "
        "FROM pg_database WHERE datname = %s", (name,)).fetchone()


def require_database_identity(control, name, expected):
    if (not re.fullmatch(r"ohvr_test_[0-9a-f]{32}", name) or
            database_identity(control, name) != expected):
        raise RuntimeError("Refusing operation: disposable database identity changed")


def drop_disposable_database(control, name, expected):
    from psycopg import sql
    require_database_identity(control, name, expected)
    # Engines must be closed by their owners. Do not terminate other-role
    # connections/background workers or require pg_signal_backend privileges.
    control.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


@contextmanager
def scratch_directory(prefix="ohvr-"):
    # Inherit workspace ACLs: Python 3.14's private mkdtemp ACL is inaccessible
    # to this managed Windows runner. Never use a business-data directory.
    scratch = Path(__file__).resolve().parent.parent / ".verification" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    directory = scratch / (prefix + uuid4().hex)
    directory.mkdir()
    try:
        yield str(directory)
    finally:
        resolved = directory.resolve()
        if resolved.parent != scratch.resolve() or directory.is_symlink():
            raise RuntimeError("Refusing cleanup outside disposable verification storage")
        shutil.rmtree(resolved)


@contextmanager
def disposable_database(backend: str, root: Path):
    if backend == "sqlite":
        yield f"sqlite:///{(root / 'test.sqlite3').as_posix()}"
        return
    if backend != "postgresql":
        raise ValueError("Unsupported verification backend")
    raw = os.environ.get("TEST_POSTGRES_ADMIN_URL")
    if not raw:
        raise RuntimeError("PostgreSQL verification requires TEST_POSTGRES_ADMIN_URL; no fallback")
    admin_url = make_url(raw)
    if (admin_url.drivername != "postgresql+psycopg" or
            admin_url.username != "ohvr_verify" or
            admin_url.host not in ("127.0.0.1", "localhost", "::1") or
            admin_url.database != "postgres" or
            set(admin_url.query) - {"sslmode", "connect_timeout"}):
        raise ValueError("Use a loopback PostgreSQL administrative URL to database postgres")
    import psycopg
    from psycopg import sql
    db_name = "ohvr_test_" + uuid4().hex
    connect_url = admin_url.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(connect_url, autocommit=True, connect_timeout=5) as control:
        attributes = control.execute(
            "SELECT current_database(), current_user, rolsuper, rolcreatedb, rolcreaterole, "
            "rolreplication, rolbypassrls FROM pg_roles WHERE rolname = current_user").fetchone()
        if attributes != ("postgres", "ohvr_verify", False, True, False, False, False):
            raise RuntimeError("Verification requires the restricted dedicated test role")
        control.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(db_name)))
        oid, owner, _ = database_identity(control, db_name)
        marker = "ohvr-disposable:" + uuid4().hex
        expected = (oid, owner, marker)
        try:
            control.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                sql.Identifier(db_name), sql.Literal(marker)))
            require_database_identity(control, db_name, expected)
            target = admin_url.set(database=db_name)
            with psycopg.connect(target.set(drivername="postgresql").render_as_string(hide_password=False),
                                 connect_timeout=5) as isolated:
                if isolated.execute("SELECT current_database(), current_user").fetchone() != (db_name, owner):
                    raise RuntimeError("Unexpected disposable connection identity")
                require_database_identity(isolated, db_name, expected)
                if isolated.execute("SELECT count(*) FROM information_schema.tables "
                                    "WHERE table_schema = 'public'").fetchone()[0]:
                    raise RuntimeError("Disposable database is not clean")
            yield target.render_as_string(hide_password=False)
        finally:
            # The live control connection, OID, owner and random database comment
            # must all match. Never drop a replacement DB merely sharing a name.
            drop_disposable_database(control, db_name, expected)


@contextmanager
def environment_context(backend: str = "sqlite"):
    with scratch_directory(prefix="ohvr-test-") as directory:
        root = Path(directory)
        with disposable_database(backend, root) as database_url:
            documents = root / "documents"
            isolated_env = {"APP_ENV": "development", "DATABASE_URL": database_url,
                            "DOCUMENT_STORAGE_DIR": str(documents), "ALLOWED_HOSTS": "testserver,localhost"}
            # Isolate the module-level default ASGI app on its first import too.
            with patch.dict(os.environ, isolated_env):
                from app.main import create_app
                from fastapi.testclient import TestClient
                settings = Settings(database_url=database_url, allowed_hosts=("testserver", "localhost"),
                                    document_storage_dir=documents)
                app = create_app(settings)
                from tests.scanner_support import CleanScanner
                app.state.document_scanner=CleanScanner()
                try:
                    with app.state.engine.connect() as connection:
                        upgrade_connection(connection)
                    with app.state.session_factory() as db:
                        first, second = Department(name="Kultur"), Department(name="Bauamt")
                        db.add_all([first, second])
                        db.flush()
                        password_hash = ph.hash(PASSWORD)
                        db.add_all([
                            User(username="admin", password_hash=password_hash, role="admin"),
                            User(username="kultur", password_hash=password_hash, role="department", department_id=first.id),
                            User(username="bau", password_hash=password_hash, role="department", department_id=second.id),
                            User(username="pruefer", password_hash=password_hash, role="reviewer"),
                            User(username="inactive", password_hash=password_hash, role="department", department_id=first.id, is_active=False),
                        ])
                        db.commit()
                    with TestClient(app) as client:
                        yield client, app
                finally:
                    app.state.engine.dispose()


def csrf_from(html):
    found = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert found, html[:500]
    return found.group(1)


def login(client, username, password=PASSWORD):
    result = client.get("/login")
    assert result.status_code == 200
    return client.post("/login", data={"username": username, "password": password,
                                      "csrf_token": csrf_from(result.text)}, follow_redirects=False)


def contract_payload(department_id="1", designation="Mietvertrag Sporthalle"):
    return {"designation": designation, "contract_type": "Miete", "relevant_date": "2026-01-10",
            "date_description": "Vertragsbeginn", "department_id": department_id,
            "contact_person": "Dienststelle"}


def create_contract(client, department_id="1", designation="Mietvertrag Sporthalle"):
    result = client.get("/contracts/new")
    assert result.status_code == 200
    data = contract_payload(department_id, designation)
    data["csrf_token"] = csrf_from(result.text)
    response = client.post("/contracts/new", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    return int(urlsplit(response.headers["location"]).path.rstrip("/").rsplit("/", 1)[-1])


def workflow_payload(client,path,data):
    """Legacy behavior tests submit the current rendered workflow form fields.

    Phase 4 conflict/missing-field tests deliberately bypass this helper.
    Explicit versions/IDs are preserved so stale submissions remain testable.
    """
    from uuid import uuid4
    if not re.fullmatch(r'/contracts/\d+/(?:tasks|reviews|documents)(?:/.*)?',str(path)):
        return data
    result=dict(data)
    result.setdefault('request_id',str(uuid4()))
    if re.fullmatch(r'/contracts/\d+/(?:tasks|reviews)/\d+(?:/assignment)?',str(path)) and 'version' not in result:
        page=client.get('/'.join(path.split('/')[:3]))
        found=re.search(r'action="'+re.escape(path)+r'"[^>]*>.*?name="version" value="(\d+)"',page.text,re.S)
        result['version']=found.group(1) if found else '1'
    return result
