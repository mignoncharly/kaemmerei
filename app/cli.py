"""Safe operations: install schema, provision departments and individual users."""
import argparse
from getpass import getpass
from datetime import timedelta
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select, delete
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Department, LoginAttempt, LoginSession, User, now_utc
from app.security import ph


def ask_password() -> str:
    first = getpass("Passwort (mindestens 12 Zeichen): ")
    again = getpass("Passwort wiederholen: ")
    if first != again or len(first) < 12 or len(first) > 256:
        raise SystemExit("Passwörter stimmen nicht überein oder sind nicht 12–256 Zeichen lang")
    return first


def main():
    parser = argparse.ArgumentParser(description="OPEN.HERZ Vertragsregister Verwaltung")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init-db", help="Datenbankschema auf aktuelle Migration bringen")
    d = subs.add_parser("add-department", help="Fachbereich anlegen")
    d.add_argument("name")
    subs.add_parser("list-departments")
    subs.add_parser("purge-sessions", help="Abgelaufene Sitzungen und alte Anmeldeversuche löschen")
    u = subs.add_parser("add-user", help="Benutzer mit Passwortabfrage anlegen")
    u.add_argument("username")
    u.add_argument("--role", required=True, choices=["admin", "department", "reviewer"])
    u.add_argument("--department", help="Exakter Fachbereichsname, erforderlich bei role=department")
    c = subs.add_parser("change-password")
    c.add_argument("username")
    x = subs.add_parser("disable-user")
    x.add_argument("username")
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "init-db":
        cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
        command.upgrade(cfg, "head")
        print("Migrationen angewandt")
        return
    engine = make_engine(settings)
    SessionFactory = make_session_factory(engine)
    with SessionFactory() as db:
        if args.command == "add-department":
            name = args.name.strip()
            if not name or len(name) > 150:
                raise SystemExit("Fachbereich muss 1–150 Zeichen haben")
            if db.scalar(select(Department).where(Department.name == name)):
                raise SystemExit("Fachbereich existiert bereits")
            db.add(Department(name=name))
            db.commit()
            print("Fachbereich angelegt")
        elif args.command == "list-departments":
            for row in db.scalars(select(Department).order_by(Department.name)):
                print(f"{row.id}: {row.name}")
        elif args.command == "purge-sessions":
            db.execute(delete(LoginSession).where(LoginSession.expires_at <= now_utc()))
            db.execute(delete(LoginAttempt).where(LoginAttempt.created_at < now_utc() - timedelta(days=7)))
            db.commit()
            print("Abgelaufene Sitzungen und alte Anmeldeversuche gelöscht")
        elif args.command == "add-user":
            username = args.username.strip().casefold()
            if not username or len(username) > 80:
                raise SystemExit("Benutzername muss 1–80 Zeichen lang sein")
            if db.scalar(select(User).where(User.username == username)):
                raise SystemExit("Benutzername bereits vorhanden")
            department_id = None
            if args.role == "department":
                if not args.department:
                    raise SystemExit("Fachbereichsbenutzer benötigen --department")
                dept = db.scalar(select(Department).where(Department.name == args.department,
                                                          Department.is_active.is_(True)))
                if not dept:
                    raise SystemExit("Fachbereich nicht vorhanden")
                department_id = dept.id
            elif args.department:
                raise SystemExit("--department ist nur für role=department erlaubt")
            db.add(User(username=username, password_hash=ph.hash(ask_password()),
                        role=args.role, department_id=department_id))
            db.commit()
            print("Benutzer angelegt")
        elif args.command in ("change-password", "disable-user"):
            username = args.username.strip().casefold()
            user = db.scalar(select(User).where(User.username == username))
            if not user:
                raise SystemExit("Benutzer nicht vorhanden")
            if args.command == "change-password":
                user.password_hash = ph.hash(ask_password())
                db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))
            else:
                if user.role == "admin" and user.is_active:
                    active_admins = list(db.scalars(select(User).where(User.role == "admin", User.is_active.is_(True))))
                    if len(active_admins) <= 1:
                        raise SystemExit("Letzter aktiver Administrator darf nicht deaktiviert werden")
                user.is_active = False
                db.query(LoginSession).filter(LoginSession.user_id == user.id).delete()
            db.commit()
            print("Änderung gespeichert")
    engine.dispose()


if __name__ == "__main__":
    main()
