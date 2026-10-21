"""Safe operations: install schema, provision departments and individual users."""
import argparse
import json
from dataclasses import replace
from getpass import getpass
from datetime import timedelta
from sqlalchemy import select, delete, text
from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.models import Department, LoginAttempt, LoginSession, User, now_utc
from app.identity_service import audit, lock_identities, save_user, validate_department_name, validate_password


def ask_password() -> str:
    first = getpass("Passwort (mindestens 12 Zeichen): ")
    again = getpass("Passwort wiederholen: ")
    if first != again or len(first) < 12 or len(first) > 256:
        raise SystemExit("Passwörter stimmen nicht überein oder sind nicht 12–256 Zeichen lang")
    try:
        return validate_password(first)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


def main():
    parser = argparse.ArgumentParser(description="OPEN.HERZ Vertragsregister Verwaltung")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init-db", help="Datenbankschema auf aktuelle Migration bringen")
    subs.add_parser('schema-inventory', help='Read-only schema and legacy exception inventory')
    subs.add_parser('workflow-inventory', help='IDs requiring legacy approval/tax reconciliation')
    subs.add_parser('document-reconcile', help='Read-only IDs/keys for missing, orphan or mismatched storage')
    recovery=subs.add_parser('document-recover', help='Retry staged jobs or explicitly review legacy files; no deletion')
    recovery.add_argument('--document-id',required=True,type=int)
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
    # Privileged operator credentials are never inherited by the web engine.
    # Provisioning remains an explicit owner operation, not an RLS bypass grant.
    if settings.enforce_database_security:
        selected = settings.maintenance_database_url if args.command == 'purge-sessions' else settings.migration_database_url
        if not selected or not selected.startswith('postgresql+psycopg://'):
            raise SystemExit('Explicit MAINTENANCE_DATABASE_URL or MIGRATION_DATABASE_URL required for this operator command')
        settings = replace(settings, database_url=selected)
    engine = make_engine(settings)
    SessionFactory = make_session_factory(engine)
    try:
        if args.command == 'init-db':
            from app.migrations import upgrade_connection
            with engine.connect() as connection:
                upgrade_connection(connection)
            print('Migrationen angewandt')
            return
        if args.command == 'schema-inventory':
            from app.schema_inventory import compare_schema
            from app.schema_rules import inventory
            with engine.connect() as connection:
                print(json.dumps({'schema': compare_schema(connection), 'legacy': inventory(connection)}))
            return
        if args.command == 'workflow-inventory':
            with engine.connect() as connection:
                result={key:connection.execute(text(sql)).scalars().all() for key,sql in {
                    'legacy_active_contract_ids':"SELECT id FROM contracts WHERE status='active' AND approval_provenance='legacy_unverified' ORDER BY id",
                    'legacy_tax_contract_ids':"SELECT id FROM contracts WHERE tax_review_status='completed' AND tax_provenance='legacy_unverified' ORDER BY id",
                    'legacy_review_ids':"SELECT id FROM contract_reviews WHERE provenance='legacy_unverified' ORDER BY id"}.items()}
                print(json.dumps(result))
            return
        if args.command=='document-reconcile':
            from app.documents import reconcile
            with SessionFactory() as db:
                print(json.dumps(reconcile(db,settings.document_storage_dir)))
            return
        if args.command=='document-recover':
            from app.documents import process_document,ClamAVScanner
            with SessionFactory() as db:
                try:
                    state=process_document(db,settings,ClamAVScanner(settings),args.document_id)
                except Exception:
                    db.rollback()
                    raise SystemExit('Recovery failed safely; preserve storage and inspect reconciliation without exposing credentials') from None
                print(json.dumps({'document_id':args.document_id,'state':state}))
            return
        if args.command == 'purge-sessions' and settings.enforce_database_security:
            from app.db_roles import validate_runtime_engine
            validate_runtime_engine(engine, 'maintenance')
            with engine.begin() as connection:
                connection.execute(text('SELECT ohvr_security.purge_expired()'))
            print('Expired authentication records purged with maintenance privileges')
            return
        with SessionFactory() as db:
            if args.command == "add-department":
                lock_identities(db)
                try:
                    name = validate_department_name(args.name)
                except ValueError as exc:
                    raise SystemExit(str(exc)) from None
                if db.scalar(select(Department).where(Department.name == name)):
                    raise SystemExit("Fachbereich existiert bereits")
                department = Department(name=name)
                db.add(department)
                db.flush()
                audit(db, None, 'departments_created', f'departments:{department.id}', name=name)
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
                department = db.scalar(select(Department).where(Department.name == args.department)) if args.department else None
                if args.department and department is None:
                    raise SystemExit("Fachbereich nicht vorhanden")
                try:
                    save_user(db, dict(username=args.username, role=args.role,
                        department_id=department.id if department else '', is_active='1', password=ask_password()))
                except ValueError as exc:
                    raise SystemExit(str(exc)) from None
                db.commit()
                print("Benutzer angelegt; Startpasswort muss beim ersten Gebrauch geändert werden")
            elif args.command in ("change-password", "disable-user"):
                user = db.scalar(select(User).where(User.username == args.username.strip().casefold()))
                if user is None:
                    raise SystemExit("Benutzer nicht vorhanden")
                values = dict(username=user.username, role=user.role, department_id=user.department_id or '',
                    is_active='1' if user.is_active and args.command != 'disable-user' else '0',
                    can_approve='1' if user.can_approve else '0',
                    password=ask_password() if args.command == 'change-password' else '')
                try:
                    save_user(db, values, user_id=user.id)
                except ValueError as exc:
                    raise SystemExit(str(exc)) from None
                db.commit()
                print("Änderung gespeichert; alle Sitzungen beendet")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
