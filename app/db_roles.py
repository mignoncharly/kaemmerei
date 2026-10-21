"""Explicit database-owner deployment step; never run by web startup."""
from sqlalchemy import inspect, text

KINDS = ('web','integration','maintenance')


def configure_runtime_roles(connection, *, web, integration, maintenance, audit_owner):
    """Grant existing DBA-created roles only; create no global roles or passwords."""
    names=(web,integration,maintenance,audit_owner)
    if len(set(names))!=4 or any(not name or len(name)>63 for name in names):
        raise ValueError('Four distinct database roles are required')
    quote=connection.dialect.identifier_preparer.quote
    owner=connection.scalar(text("SELECT r.rolname FROM pg_namespace n JOIN pg_roles r ON r.oid=n.nspowner WHERE n.nspname='ohvr_security'"))
    for name in names:
        row=connection.execute(text('SELECT rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication,rolcanlogin FROM pg_roles WHERE rolname=:name'),{'name':name}).one_or_none()
        if row is None or any(row[:5]) or row[5] != (name!=audit_owner):
            raise ValueError('Runtime roles must be restricted LOGIN roles; audit owner must be restricted NOLOGIN')
        if name!=audit_owner and connection.scalar(text('SELECT pg_has_role(:name,:owner,\'MEMBER\')'),{'name':name,'owner':owner}):
            raise ValueError('Runtime role cannot inherit migration ownership')
        if name!=audit_owner and connection.scalar(text('SELECT pg_has_role(:name,:owner,\'MEMBER\')'),{'name':name,'owner':audit_owner}):
            raise ValueError('Runtime role cannot inherit audit ownership')
    db=quote(connection.scalar(text('SELECT current_database()')))
    connection.exec_driver_sql(f'REVOKE ALL ON DATABASE {db} FROM PUBLIC')
    connection.exec_driver_sql('REVOKE ALL ON SCHEMA public FROM PUBLIC')
    connection.exec_driver_sql('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC')
    connection.exec_driver_sql('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC')
    for kind,name in zip(KINDS,names):
        role=quote(name)
        connection.execute(text('INSERT INTO ohvr_security.runtime_roles(role_name,kind) VALUES (:name,:kind) ON CONFLICT(role_name) DO UPDATE SET kind=excluded.kind'),{'name':name,'kind':kind})
        connection.exec_driver_sql(f'GRANT CONNECT ON DATABASE {db} TO {role}')
        connection.exec_driver_sql(f'GRANT USAGE ON SCHEMA public,ohvr_security TO {role}')
        connection.exec_driver_sql(f'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}')
        connection.exec_driver_sql(f'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA ohvr_security FROM {role}')
    w,i,m,a=map(quote,names)
    connection.exec_driver_sql(f'GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA ohvr_security TO {w},{i},{a}')
    connection.exec_driver_sql(f'REVOKE EXECUTE ON FUNCTION ohvr_security.password_hash(integer) FROM {i}')
    connection.exec_driver_sql(f'REVOKE EXECUTE ON FUNCTION ohvr_security.lock_contract(integer) FROM {i}')
    tables=inspect(connection).get_table_names()
    for table in tables:
        if table in ('alembic_version','security_events') or table.startswith('sync_'):
            continue
        cols=[col['name'] for col in inspect(connection).get_columns(table) if col['name'] not in ('password_hash','token_hash') or table=='login_sessions']
        # token_hash on LoginSession is an opaque lookup key, restricted by RLS;
        # password/token credential hashes remain inaccessible as table columns.
        columns=','.join(quote(c) for c in cols)
        connection.exec_driver_sql(f'GRANT SELECT ({columns}) ON public.{quote(table)} TO {w}')
        connection.exec_driver_sql(f'GRANT INSERT ON public.{quote(table)} TO {w}')
        if table not in ('revisions','identity_audit','review_decisions'):
            connection.exec_driver_sql(f'GRANT UPDATE ON public.{quote(table)} TO {w}')
        if table in ('login_sessions','login_attempts','recipient_memberships'):
            connection.exec_driver_sql(f'GRANT DELETE ON public.{quote(table)} TO {w}')
        seq=connection.scalar(text('SELECT pg_get_serial_sequence(:table,\'id\')'),{'table':'public.'+table}) if 'id' in cols else None
        if seq:
            # pg_get_serial_sequence returns a server-generated qualified name.
            connection.exec_driver_sql(f'GRANT USAGE ON SEQUENCE {seq} TO {w}')
    connection.exec_driver_sql(f'GRANT SELECT ON public.security_events TO {w}')
    for table in ('contracts','contract_documents','departments','security_events'):
        connection.exec_driver_sql(f'GRANT SELECT ON public.{table} TO {i}')
    token_cols=','.join(quote(c['name']) for c in inspect(connection).get_columns('integration_tokens') if c['name']!='token_hash')
    connection.exec_driver_sql(f'GRANT SELECT ({token_cols}), UPDATE (last_used_at) ON public.integration_tokens TO {i}')
    connection.exec_driver_sql(f'GRANT SELECT ON public.sync_cursors,public.sync_snapshot_items,public.contract_tasks,public.contract_reviews,public.review_decisions,public.revisions TO {i}')
    connection.exec_driver_sql(f'GRANT INSERT ON public.sync_cursors,public.sync_snapshot_items TO {i}')
    connection.exec_driver_sql(f'REVOKE EXECUTE ON FUNCTION ohvr_security.sync_barrier() FROM {w},{a}')
    connection.exec_driver_sql(f'REVOKE EXECUTE ON FUNCTION ohvr_security.sync_events_page(integer,integer) FROM {w},{a}')
    connection.exec_driver_sql("""CREATE OR REPLACE FUNCTION ohvr_security.purge_expired() RETURNS void LANGUAGE plpgsql SECURITY DEFINER
     SET search_path=pg_catalog,pg_temp AS $$
      DECLARE sessions_count integer; attempts_count integer;
      BEGIN
      DELETE FROM public.login_sessions WHERE expires_at <= timezone('UTC',statement_timestamp());
      GET DIAGNOSTICS sessions_count = ROW_COUNT;
      DELETE FROM public.login_attempts WHERE created_at < timezone('UTC',statement_timestamp())-interval '7 days';
      GET DIAGNOSTICS attempts_count = ROW_COUNT;
      INSERT INTO public.security_events(principal,action,target,created_at,outcome,correlation_id,details)
      VALUES('maintenance','PURGE','expired_authentication',timezone('UTC',statement_timestamp()),'success',gen_random_uuid()::text,
       jsonb_build_object('sessions',sessions_count,'attempts',attempts_count));
      END;
     $$""")
    connection.exec_driver_sql('REVOKE ALL ON FUNCTION ohvr_security.purge_expired() FROM PUBLIC')
    connection.exec_driver_sql(f'REVOKE ALL ON FUNCTION ohvr_security.purge_expired() FROM {w},{i}')
    connection.exec_driver_sql(f'GRANT EXECUTE ON FUNCTION ohvr_security.purge_expired(),ohvr_security.role_kind() TO {m}')
    connection.exec_driver_sql(f'GRANT USAGE,CREATE ON SCHEMA public TO {a}')
    connection.exec_driver_sql(f'GRANT USAGE,CREATE ON SCHEMA ohvr_security TO {a}')
    for table in ('revisions','identity_audit','security_events','review_decisions'):
        connection.exec_driver_sql(f'ALTER TABLE public.{table} OWNER TO {a}')
    connection.exec_driver_sql(f'ALTER FUNCTION ohvr_security.capture_event() OWNER TO {a}')
    connection.exec_driver_sql(f'ALTER FUNCTION ohvr_security.audit_identity() OWNER TO {a}')


def validate_runtime_engine(engine, expected_kind):
    with engine.connect() as connection:
        row=connection.execute(text('SELECT current_user,session_user,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole,rolreplication FROM pg_roles WHERE rolname=current_user')).one()
        if row[0]!=row[1] or any(row[2:]):
            raise ValueError('Production must use a direct restricted database LOGIN role')
        if connection.scalar(text('SELECT ohvr_security.role_kind()'))!=expected_kind:
            raise ValueError('Database runtime role registry mismatch')
        if connection.scalar(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','ohvr_security') AND pg_has_role(current_user,c.relowner,'MEMBER')")):
            raise ValueError('Runtime role owns or inherits schema objects')
        row=connection.execute(text("SELECT count(*),bool_and(c.relrowsecurity AND c.relforcerowsecurity) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('contracts','contract_documents','contract_tasks','contract_reviews','revisions','identity_audit','security_events','review_decisions','document_jobs','sync_state','sync_outbox','sync_events','sync_cursors','sync_snapshot_items')")).one()
        if row[0]!=14 or not row[1]:
            raise ValueError('Required forced RLS policies are missing')
