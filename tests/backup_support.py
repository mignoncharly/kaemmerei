"""Round-trip only the UUID-marked synthetic fixture, never a business database."""
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from contextlib import closing
from sqlalchemy import text
from sqlalchemy.engine import make_url
from tests.support import disposable_database,scratch_directory


@contextmanager
def restored_fixture(owner,backend):
    with scratch_directory('ohvr-document-restore-') as directory:
        root=Path(directory)
        storage=root/'restored-storage'
        # Test writer/worker calls have completed; no requests run during snapshot.
        source=owner.state.engine.url
        if backend=='sqlite':
            database=root/'restored.sqlite3'
            with closing(sqlite3.connect(source.database)) as src,closing(sqlite3.connect(database)) as dest:src.backup(dest)
            shutil.copytree(owner.state.document_storage_dir,storage)
            yield 'sqlite:///'+str(database),storage
        else:
            if not re.fullmatch('ohvr_test_[0-9a-f]{32}',source.database):
                raise RuntimeError('Backup test requires a marked disposable source')
            with owner.state.engine.connect() as connection:
                major=int(connection.scalar(text('SHOW server_version_num')))//10000
            candidates=[Path(os.getenv('OHVR_NATIVE_BIN','__not_configured__')),
                Path(r'C:\Program Files\PostgreSQL')/str(major)/'bin',Path('/usr/lib/postgresql')/str(major)/'bin']
            binary='pg_dump.exe' if os.name=='nt' else 'pg_dump'
            bindir=next((p for p in candidates if (p/binary).is_file()),None)
            if bindir is None:
                located=shutil.which(binary)
                if located:bindir=Path(located).parent
            if bindir is None:raise RuntimeError('Matching PostgreSQL dump/restore client required')
            version=subprocess.run([str(bindir/binary),'--version'],capture_output=True,check=True).stdout.decode('ascii')
            if not re.search(r'\b'+str(major)+r'\.',version):
                raise RuntimeError('Install the PostgreSQL client matching the test server major')
            def environment(url):
                env={**os.environ,'PGHOST':url.host,'PGPORT':str(url.port),'PGUSER':url.username,'PGDATABASE':url.database}
                env.pop('PGPASSWORD',None)
                if url.password:env['PGPASSWORD']=url.password
                return env
            archive=root/'synthetic.dump'
            with archive.open('wb') as output:
                subprocess.run([str(bindir/binary),'--format=custom','--no-owner','--no-privileges','--enable-row-security'],
                    stdout=output,stderr=subprocess.DEVNULL,env=environment(source),check=True,timeout=60)
            shutil.copytree(owner.state.document_storage_dir,storage)
            with disposable_database('postgresql',root) as destination:
                target=make_url(destination)
                # Harness created/identified this unique empty database and retains
                # its control connection and OID/owner/comment cleanup guards.
                restore=bindir/('pg_restore.exe' if os.name=='nt' else 'pg_restore')
                with archive.open('rb') as input_file:
                    subprocess.run([str(restore),'--no-owner','--no-privileges','--dbname',target.database],
                        stdin=input_file,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                        env=environment(target),check=True,timeout=60)
                yield destination,storage
