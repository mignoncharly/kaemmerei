"""Manage only a dedicated, marked native PostgreSQL test cluster.

No Windows service registration, existing-cluster adoption, or data deletion.
Credentials stay in ignored owner-only passfiles; stdout contains no password.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PURPOSE = "open-herz-native-verification-v1"
BOOTSTRAP = "ohvr_bootstrap"
TEST_USER = "ohvr_verify"


class SetupError(RuntimeError):
    pass


def checked_home(value: Path) -> Path:
    if value.is_symlink():
        raise SetupError("Native test storage must not be a symbolic link")
    value = value.resolve()
    allowed = ROOT / ".local-postgres"
    scratch = ROOT / ".verification"
    if not scratch.resolve().is_relative_to(ROOT):
        raise SetupError("Verification storage resolves outside the project")
    if value != allowed or allowed.is_symlink():
        if not value.is_relative_to(scratch.resolve()) or value == scratch.resolve():
            raise SetupError("Native test storage must be .local-postgres or a child of .verification")
    return value


def run_command(arguments, *, accepted=(0,), timeout=45):
    result = subprocess.run([str(a) for a in arguments], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode not in accepted:
        message = (result.stderr or result.stdout).strip()
        if "restricted token" in message:
            message += ("\nRun this native setup once from a normal authorized PowerShell terminal. "
                        "This session cannot initialize PostgreSQL's Windows process token; "
                        "do not disable PostgreSQL token checks.")
        raise SetupError(f"{Path(arguments[0]).name} exited {result.returncode}: {message}")
    return result


def secure_directory(directory: Path):
    if os.name == "nt":
        # Protect credentials for the actual current Windows identity. Do not
        # depend on Python's mkdtemp private ACL, which failed in this sandbox.
        identity = run_command(["whoami", "/user", "/fo", "csv", "/nh"]).stdout
        rows = list(csv.reader(identity.strip().splitlines()))
        sid = rows[-1][-1] if rows else ""
        if not re.fullmatch(r"S-1-[0-9-]+", sid):
            raise SetupError("Could not establish the Windows SID for private native test storage")
        try:
            run_command(["icacls", directory, "/inheritance:r", "/grant:r", f"*{sid}:(OI)(CI)F"])
        except SetupError:
            raise SetupError("Windows denied owner-only permissions for native test storage. "
                             "Retry setup from a normal authorized PowerShell terminal; "
                             "no new credentials were written and no existing PostgreSQL service was changed.") from None
    else:
        directory.chmod(0o700)


def write_secret(path: Path, value: str):
    # Parent is owner-only before a credential is written.
    with path.open("x", encoding="ascii") as handle:
        handle.write(value)
    if os.name != "nt":
        path.chmod(0o600)


@contextmanager
def setup_lock(home: Path):
    lock = home / ".setup.lock"
    try:
        with lock.open("x", encoding="ascii") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError:
        raise SetupError("Native setup is already locked. Check the recorded PID before removing a stale .setup.lock.") from None
    try:
        yield
    finally:
        lock.unlink()


class NativeCluster:
    def __init__(self, home: Path, binaries: Path, port: int = 55432):
        self.home = checked_home(home)
        self.binaries = binaries.resolve()
        if not 1024 <= port <= 65535:
            raise SetupError("Use an unprivileged native test port between 1024 and 65535")
        self.port = port
        self.data = self.home / "data"
        self.marker = self.home / "cluster.json"

    def executable(self, name):
        path = self.binaries / (name + (".exe" if os.name == "nt" else ""))
        if not path.is_file():
            raise SetupError(f"PostgreSQL executable missing: {path}. Set -PostgresBin to the installed bin directory.")
        return path

    def metadata(self):
        if not self.marker.is_file():
            raise SetupError("Refusing to adopt unmarked PostgreSQL storage; existing application services are never reused")
        try:
            marker = json.loads(self.marker.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            raise SetupError("Native test cluster marker is unreadable") from None
        if (marker.get("purpose") != PURPOSE or marker.get("port") != self.port or
                marker.get("home") != str(self.home) or self.data.is_symlink()):
            raise SetupError("Native test cluster ownership/path/port does not match this request")
        return marker

    def prepare_home(self):
        self.executable("initdb")
        self.executable("pg_ctl")
        if self.home.exists():
            self.metadata()
        else:
            self.home.mkdir(parents=True)
            self.marker.write_text(json.dumps({"purpose": PURPOSE, "home": str(self.home),
                                               "port": self.port}, indent=2), encoding="utf-8")
        # The marker has no credentials. Lock down the directory before creating
        # any passfile, including on retry after a failed host initialization.
        secure_directory(self.home)

    def passfile(self, user):
        return self.home / ("bootstrap.pgpass" if user == BOOTSTRAP else "test.pgpass")

    def secret(self, user):
        path = self.passfile(user)
        if not path.exists():
            password = secrets.token_hex(32)
            write_secret(path, f"127.0.0.1:{self.port}:*:{user}:{password}\n")
            return password
        prefix = f"127.0.0.1:{self.port}:*:{user}:"
        value = path.read_text(encoding="ascii").strip()
        if not value.startswith(prefix) or not re.fullmatch(r"[0-9a-f]{64}", value[len(prefix):]):
            raise SetupError("Native test passfile does not match this dedicated endpoint/identity")
        if os.name != "nt":
            path.chmod(0o600)
        return value[len(prefix):]

    def initialize(self):
        if (self.data / "PG_VERSION").is_file():
            version = run_command([self.executable("initdb"), "--version"]).stdout
            match = re.search(r"PostgreSQL\)\s+(\d+)", version)
            if not match or match.group(1) != (self.data / "PG_VERSION").read_text().strip():
                raise SetupError("Native binaries and existing test cluster have different major versions")
            return
        if self.data.exists() and any(self.data.iterdir()):
            raise SetupError("Incomplete native cluster retained for inspection; no existing data will be overwritten or deleted")
        password = self.secret(BOOTSTRAP)
        self.secret(TEST_USER)
        password_input = self.home / "init-password.input"
        if password_input.exists():
            raise SetupError("Stale initialization input exists; inspect prior interrupted setup before retrying")
        write_secret(password_input, password + "\n")
        try:
            run_command([self.executable("initdb"), "-D", self.data, f"--username={BOOTSTRAP}",
                         "--encoding=UTF8", "--locale=C", "--auth-host=scram-sha-256",
                         "--auth-local=reject", f"--pwfile={password_input}"])
        finally:
            password_input.unlink(missing_ok=True)

    def status(self):
        self.metadata()
        if not (self.data / "PG_VERSION").is_file():
            return "not_initialized"
        result = run_command([self.executable("pg_ctl"), "-D", self.data, "status"], accepted=(0, 3))
        return "running" if result.returncode == 0 else "stopped"

    def configure(self):
        # Persist these settings before the FIRST start. Never silently restart
        # a running server or borrow the endpoint of another PostgreSQL instance.
        target = self.data / "postgresql.auto.conf"
        target.write_text("# Dedicated OPEN.HERZ synthetic verification cluster\n"
                          f"listen_addresses = '127.0.0.1'\nport = {self.port}\n"
                          "unix_socket_directories = ''\n", encoding="utf-8")

    def assert_port_free(self):
        try:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", self.port))
        except OSError:
            raise SetupError(f"Port {self.port} is occupied. Refusing to stop or reuse its existing service.") from None

    def provision_role(self):
        import psycopg
        from psycopg import sql
        try:
            with psycopg.connect(host="127.0.0.1", port=self.port, dbname="postgres", user=BOOTSTRAP,
                                 password=self.secret(BOOTSTRAP), connect_timeout=5, autocommit=True) as connection:
                actual = connection.execute("SHOW data_directory").fetchone()[0]
                if Path(actual).resolve() != self.data.resolve():
                    raise SetupError("Connected PostgreSQL data directory is not this marked test cluster")
                exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (TEST_USER,)).fetchone()
                operation = "ALTER" if exists else "CREATE"
                statement = sql.SQL(operation + " ROLE ohvr_verify LOGIN CREATEDB NOSUPERUSER NOCREATEROLE "
                                    "NOREPLICATION NOBYPASSRLS PASSWORD {}").format(sql.Literal(self.secret(TEST_USER)))
                connection.execute(statement)
            with psycopg.connect(host="127.0.0.1", port=self.port, dbname="postgres", user=TEST_USER,
                                 password=self.secret(TEST_USER), connect_timeout=5) as connection:
                attributes = connection.execute("SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                                                "FROM pg_roles WHERE rolname = current_user").fetchone()
                if tuple(attributes) != (False, True, False, False, False):
                    raise SetupError("Dedicated test role attributes do not match the restricted policy")
        except psycopg.Error:
            # Do not print queries/literals containing generated credentials.
            raise SetupError("Dedicated native PostgreSQL connection/role provisioning failed; inspect its server.log") from None

    def start(self):
        self.prepare_home()
        with setup_lock(self.home):
            self.initialize()
            if self.status() != "running":
                self.assert_port_free()
                self.configure()
                run_command([self.executable("pg_ctl"), "-D", self.data, "-l", self.home / "server.log",
                             "-w", "-t", "30", "start"])
            self.provision_role()
        return self.connection_info()

    def stop(self):
        self.metadata()
        with setup_lock(self.home):
            if self.status() == "running":
                run_command([self.executable("pg_ctl"), "-D", self.data, "-m", "fast", "-w", "-t", "30", "stop"])
        return {"status": "stopped", "home": str(self.home), "data_preserved": True}

    def connection_info(self):
        return {"backend": "native", "status": "running", "home": str(self.home), "port": self.port,
                "url": f"postgresql+psycopg://{TEST_USER}@127.0.0.1:{self.port}/postgres",
                "passfile": str(self.passfile(TEST_USER))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop", "status"))
    parser.add_argument("--home", type=Path, default=ROOT / ".local-postgres")
    parser.add_argument("--bin", type=Path, default=Path(r"C:\Program Files\PostgreSQL\18\bin"))
    parser.add_argument("--port", type=int, default=55432)
    args = parser.parse_args()
    try:
        cluster = NativeCluster(args.home, args.bin, args.port)
        if args.action == "start":
            result = cluster.start()
        elif args.action == "stop":
            result = cluster.stop()
        else:
            result = {"status": cluster.status(), "home": str(cluster.home), "port": cluster.port}
        print(json.dumps(result))
        return 0
    except (SetupError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Native PostgreSQL setup failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
