"""Restricted real LOGIN roles confined to an already marked disposable DB."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import os
import json
from pathlib import Path
import secrets
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from fastapi.testclient import TestClient

from app.config import Settings
from app.db_roles import configure_runtime_roles
from tests.support import database_identity, require_database_identity, environment_context


@dataclass
class RuntimeEnvironment:
    client: object = field(repr=False)
    app: object = field(repr=False)
    owner: object = field(repr=False)
    names: dict
    urls: dict = field(repr=False)


@contextmanager
def bootstrap_connection(admin_url, database='postgres'):
    explicit=os.getenv('TEST_POSTGRES_BOOTSTRAP_URL')
    if explicit:
        bootstrap=make_url(explicit)
        if (bootstrap.host!=admin_url.host or bootstrap.port!=admin_url.port or
                bootstrap.database!='postgres' or bootstrap.drivername!='postgresql+psycopg'):
            raise RuntimeError('Test bootstrap must match the dedicated local test control endpoint')
        with psycopg.connect(bootstrap.set(drivername='postgresql',database=database).render_as_string(hide_password=False),
                             autocommit=True,connect_timeout=5) as connection:
            yield connection
    else:
        from scripts.native_test_database import NativeCluster,ROOT,BOOTSTRAP
        cluster=NativeCluster(ROOT/'.local-postgres',Path(os.getenv('OHVR_NATIVE_BIN',r'C:\Program Files\PostgreSQL\18\bin')),admin_url.port or 55432)
        cluster.metadata()
        with patch.dict(os.environ,{'PGPASSFILE':str(cluster.passfile(BOOTSTRAP))}):
            connection=psycopg.connect(host=admin_url.host,port=admin_url.port,dbname=database,
                                       user=BOOTSTRAP,autocommit=True,connect_timeout=5)
        try:
            cluster.assert_connected_cluster(connection)
            yield connection
        finally:
            connection.close()


@contextmanager
def runtime_environment():
    with environment_context('postgresql') as (_owner_client,owner):
        owner_url=owner.state.engine.url
        db_name=owner_url.database
        admin_url=make_url(os.environ['TEST_POSTGRES_ADMIN_URL'])
        with psycopg.connect(owner_url.set(drivername='postgresql').render_as_string(hide_password=False),autocommit=True) as marker_connection:
            identity=database_identity(marker_connection,db_name)
        nonce=uuid4().hex
        names={kind:'ohvr_t_'+nonce[:20]+'_'+suffix for kind,suffix in
               [('web','w'),('integration','i'),('maintenance','m'),('audit','a')]}
        marker='ohvr-runtime:'+db_name+':'+nonce
        created=[]
        urls={}
        journal=Path(__file__).resolve().parent.parent/'.verification'/('role-cleanup-'+nonce+'.json')
        with bootstrap_connection(admin_url) as control:
            require_database_identity(control,db_name,identity)
            try:
                for kind,name in names.items():
                    password=secrets.token_hex(32)
                    login='NOLOGIN' if kind=='audit' else 'LOGIN'
                    try:
                        control.execute(sql.SQL('CREATE ROLE {} '+login+' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Identifier(name),sql.Literal(password)))
                    except psycopg.Error:
                        raise RuntimeError('Restricted temporary role creation failed') from None
                    control.execute(sql.SQL('COMMENT ON ROLE {} IS {}').format(sql.Identifier(name),sql.Literal(marker)))
                    oid=control.execute('SELECT oid FROM pg_roles WHERE rolname=%s',(name,)).fetchone()[0]
                    created.append((name,oid))
                    journal.write_text(json.dumps({'database':db_name,'database_identity':identity,'marker':marker,'roles':created}),encoding='utf-8')
                    urls[kind]=owner_url.set(username=name,password=password).render_as_string(hide_password=False)
                control.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(names['audit']),sql.Identifier(owner_url.username)))
                with owner.state.engine.begin() as connection:
                    configure_runtime_roles(connection,web=names['web'],integration=names['integration'],
                                            maintenance=names['maintenance'],audit_owner=names['audit'])
                from app.main import create_app
                app=create_app(Settings(database_url=urls['web'],integration_database_url=urls['integration'],
                    enforce_database_security=True,document_storage_dir=owner.state.document_storage_dir))
                from tests.scanner_support import CleanScanner
                app.state.document_scanner=CleanScanner()
                try:
                    with TestClient(app) as client:
                        yield RuntimeEnvironment(client,app,owner,names,urls)
                finally:
                    app.state.engine.dispose()
                    app.state.integration_engine.dispose()
            finally:
                require_database_identity(control,db_name,identity)
                for name,oid in created:
                    actual=control.execute("SELECT oid,shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=%s",(name,)).fetchone()
                    if actual!=(oid,marker):
                        raise RuntimeError('Refusing role cleanup: identity changed')
                # Only generated roles on the positively identified disposable DB.
                # Reassign audit objects before dropping their temporary owner.
                with bootstrap_connection(admin_url,database=db_name) as isolated:
                    if names['audit'] in dict(created):
                        isolated.execute(sql.SQL('REASSIGN OWNED BY {} TO {}').format(sql.Identifier(names['audit']),sql.Identifier(owner_url.username)))
                    for name,_ in created:
                        isolated.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(name)))
                for name,_ in reversed(created):
                    control.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(name)))
                journal.unlink(missing_ok=True)
