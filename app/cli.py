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
    import os
    import sys
    from app.operational_status import JOBS, tracked_job
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    directory = os.getenv('OPS_STATUS_DIRECTORY')
    if command in JOBS and directory:
        with tracked_job(directory, command, production=os.getenv('APP_ENV') == 'production'):
            return execute()
    return execute()


def execute():
    parser = argparse.ArgumentParser(description="OPEN.HERZ Vertragsregister Verwaltung")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init-db", help="Datenbankschema auf aktuelle Migration bringen")
    subs.add_parser('schema-inventory', help='Read-only schema and legacy exception inventory')
    subs.add_parser('workflow-inventory', help='IDs requiring legacy approval/tax reconciliation')
    subs.add_parser('document-reconcile', help='Read-only IDs/keys for missing, orphan or mismatched storage')
    subs.add_parser('integration-status', help='Read-only outbox, publication, snapshot/cursor and legacy-token counts')
    events = subs.add_parser('events-publish', help='Bounded owner-only event publication; no retention deletion')
    events.add_argument('--limit', type=int, default=500)
    monitor = subs.add_parser('operations-health', help='Local read-only health JSON; no external delivery')
    for option in ('status-directory', 'verifier'):
        monitor.add_argument('--'+option, required=True)
    source = monitor.add_mutually_exclusive_group(required=True)
    source.add_argument('--receipt')
    source.add_argument('--backup-directory')
    monitor.add_argument('--reserve-bytes', type=int, default=256*1024**2)
    monitor.add_argument('--maximum-backup-hours', type=int, default=24)
    monitor.add_argument('--security-threshold', type=int, default=100)
    recovery=subs.add_parser('document-recover', help='Retry staged jobs or explicitly review legacy files; no deletion')
    recovery.add_argument('--document-id',required=True,type=int)
    scans=subs.add_parser('scan-pending', help='Bounded durable PostgreSQL scan retries; explicit schema operator')
    scans.add_argument('--limit',type=int,default=10)
    scans.add_argument('--seconds',type=int,default=120)
    backup=subs.add_parser('backup-create',help='Owner-only encrypted DB/private-file snapshot; no deletion or deployment')
    backup.add_argument('--database',required=True,help='Exact non-default application database identity')
    backup.add_argument('--directory',required=True)
    backup.add_argument('--age',required=True)
    backup.add_argument('--age-sha256',required=True)
    backup.add_argument('--recipients',required=True,help='Public native age recipients file')
    backup.add_argument('--signing-key',required=True,help='Protected Ed25519 key file path, never key contents')
    backup.add_argument('--pg-dump',required=True)
    backup.add_argument('--seconds',type=int,default=1800)
    restore=subs.add_parser('backup-prepare-restore',help='Verify and extract into a NEW private bundle; never import or overwrite a database')
    for option in ('receipt','verifier','identity','directory','age','age-sha256'):
        restore.add_argument('--'+option,required=True)
    restore.add_argument('--seconds',type=int,default=1800)
    restore.add_argument('--production',action='store_true',help='Require production private ACL validation')
    keys=subs.add_parser('mfa-key-create',help='Create a new key file in a separately provisioned private directory; never print key')
    keys.add_argument('--output',required=True)
    for command in ('mfa-enroll-authorize','mfa-recover'):
        mfa=subs.add_parser(command,help='Owner-only verified enrollment/recovery, no bypass session')
        mfa.add_argument('username')
        mfa.add_argument('--reference',required=True)
        mfa.add_argument('--identity-verified',action='store_true',required=True)
    mfa=subs.add_parser('mfa-enforce',help='Require MFA and revoke all human/guest sessions; service tokens unchanged')
    mfa.add_argument('--reference',required=True)
    mfa.add_argument('--confirm-session-revocation',action='store_true',required=True)
    rotation=subs.add_parser('mfa-key-rotate',help='Re-encrypt a bounded credential batch using the configured keyring primary key')
    rotation.add_argument('--after-user-id',type=int,default=0)
    rotation.add_argument('--limit',type=int,default=100)
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
    if args.command=='backup-prepare-restore':
        from pathlib import Path
        from app.backup_restore import prepare_restore
        try:
            job=prepare_restore(Path(args.receipt),Path(args.verifier),Path(args.identity),Path(args.directory),
                Path(args.age),args.age_sha256,seconds=args.seconds,production=args.production)
        except Exception:
            raise SystemExit('Recovery preparation failed; no ready bundle accepted. Inspect private staging locally; no database imported.') from None
        print(json.dumps({'status':'verified-bundle-only','job':job.name,'database_imported':False}))
        return
    if args.command=='mfa-key-create':
        import os
        from pathlib import Path
        from cryptography.fernet import Fernet
        from app.documents import reject_links,verify_private_acl
        try:
            output=Path(args.output)
            if not output.is_absolute() or (os.name=='nt' and str(output).startswith('\\\\')):
                raise ValueError('Explicit local key path required')
            reject_links(output)
            verify_private_acl(output.parent)
            data=(json.dumps([Fernet.generate_key().decode('ascii')])+'\n').encode('ascii')
            fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_BINARY',0),0o600)
            with os.fdopen(fd,'wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
        except Exception:
            raise SystemExit('Key creation failed safely; use a new local file in a provisioned private directory') from None
        print('Private MFA key created; arrange separate protected recovery escrow before enabling MFA')
        return
    settings = get_settings()
    # Privileged operator credentials are never inherited by the web engine.
    # Provisioning remains an explicit owner operation, not an RLS bypass grant.
    if settings.enforce_database_security:
        selected = settings.maintenance_database_url if args.command == 'purge-sessions' else settings.migration_database_url
        if not selected or not selected.startswith('postgresql+psycopg://'):
            raise SystemExit('Explicit MAINTENANCE_DATABASE_URL or MIGRATION_DATABASE_URL required for this operator command')
        settings = replace(settings, database_url=selected)
        settings.validate()
    engine = make_engine(settings)
    SessionFactory = make_session_factory(engine)
    try:
        if settings.production and args.command != 'operations-health':
            from app.server_security import validate_server_security
            try:
                validate_server_security(engine)
            except Exception:
                raise SystemExit('Production database security baseline validation failed; use a reviewed patched server and protected connection configuration') from None
        if args.command == 'operations-health':
            from pathlib import Path
            from app.monitoring import operational_health
            result = operational_health(engine, settings.document_storage_dir,
                Path(args.status_directory), Path(args.receipt) if args.receipt else None, Path(args.verifier),
                reserve_bytes=args.reserve_bytes, maximum_backup_hours=args.maximum_backup_hours,
                security_threshold=args.security_threshold, production=settings.production,
                backup_directory=Path(args.backup_directory) if args.backup_directory else None)
            print(json.dumps(result))
            if not result['healthy']:
                raise SystemExit(2)
            return
        if args.command == 'events-publish':
            from app.operations import publish_events
            try:
                result = publish_events(engine, limit=args.limit)
            except Exception:
                raise SystemExit('Event publication failed; inspect protected operator configuration locally') from None
            print(json.dumps(result))
            return
        if args.command=='backup-create':
            from pathlib import Path
            from app.backup import BackupOptions,create_backup
            try:
                options=BackupOptions(Path(args.directory),Path(args.age),args.age_sha256,
                    Path(args.recipients),Path(args.signing_key),Path(args.pg_dump),args.seconds,settings.production)
                result=create_backup(engine,settings,options,database=args.database)
            except Exception:
                raise SystemExit('Backup failed; no successful receipt accepted. Inspect private staging locally; no source deletion.') from None
            print(json.dumps(result))
            return
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
                result = reconcile(db,settings.document_storage_dir)
                print(json.dumps(result))
                if any(result[key] for key in ('missing','mismatched','orphans','unsafe')):
                    raise SystemExit(2)
            return
        if args.command=='integration-status':
            with engine.connect() as connection:
                state=connection.execute(text('SELECT next_seq,floor FROM sync_state WHERE id=1')).mappings().one()
                result=dict(state)
                for key,query in {
                    'unpublished':"SELECT count(*) FROM sync_outbox WHERE published_seq IS NULL",
                    'published':"SELECT count(*) FROM sync_events",
                    'cursors':"SELECT count(*) FROM sync_cursors",
                    'snapshot_items':"SELECT count(*) FROM sync_snapshot_items",
                    'legacy_without_owner':"SELECT count(*) FROM integration_tokens WHERE owner_user_id IS NULL"}.items():
                    result[key]=connection.scalar(text(query))
                print(json.dumps(result))
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
        if args.command=='scan-pending':
            from app.operations import scan_batch
            from app.documents import ClamAVScanner
            try:
                result=scan_batch(engine,SessionFactory,settings,ClamAVScanner(settings),
                                  limit=args.limit,seconds=args.seconds)
            except Exception:
                raise SystemExit('Scan batch failed safely; inspect operator configuration without exposing secrets') from None
            print(json.dumps(result))
            if result['errors'] or result['exhausted'] or result['retry'] or result['suspended']:
                raise SystemExit(2)
            return
        if args.command in ('mfa-enroll-authorize','mfa-recover','mfa-enforce'):
            from app.mfa_service import authorize_enrollment,enforce_policy
            with SessionFactory() as db:
                try:
                    if args.command=='mfa-enforce':
                        enforce_policy(db,args.reference)
                    else:
                        authorize_enrollment(db,args.username,args.reference,recovery=args.command=='mfa-recover')
                    db.commit()
                except Exception:
                    db.rollback()
                    raise SystemExit('MFA administration failed; verify active identity, owner permissions and case reference locally') from None
            print('MFA policy/enrollment authorization recorded; affected sessions revoked; no bypass session issued')
            return
        if args.command=='mfa-key-rotate':
            from app.mfa_codec import SeedCipher
            from app.models import MfaCredential
            if settings.mfa_key_file is None or not 1<=args.limit<=100 or args.after_user_id<0:
                raise SystemExit('Explicit keyring and bounded rotation arguments required')
            with SessionFactory() as db:
                try:
                    cipher=SeedCipher(settings.mfa_key_file)
                    lock_identities(db)
                    rows=db.scalars(select(MfaCredential).where(MfaCredential.user_id>args.after_user_id,
                        MfaCredential.seed_ciphertext.is_not(None)).order_by(MfaCredential.user_id).limit(args.limit)).all()
                    for row in rows:row.seed_ciphertext=cipher.rotate(row.user_id,row.seed_ciphertext)
                    last=rows[-1].user_id if rows else args.after_user_id
                    audit(db,None,'mfa_key_rotation','mfa_credentials',count=len(rows),last_user_id=last)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise SystemExit('Key rotation failed; preserve old keys and investigate without logging seed material') from None
            print(json.dumps({'rotated':len(rows),'last_user_id':last,'old_keys_must_be_retained_for_backups':True}))
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
