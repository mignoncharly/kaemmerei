"""Explicit DBA-reviewed grants on an already migrated named database; no role/password creation."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app.config import Settings
from app.db import make_engine
from app.db_roles import configure_runtime_roles
from app.migrations import migration_head


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True)
    for name in ('web','integration','maintenance','audit-owner'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    raw=os.environ.get('MIGRATION_DATABASE_URL')
    if not raw:
        raise SystemExit('MIGRATION_DATABASE_URL is required; no default or credential output')
    url=make_url(raw)
    if url.drivername!='postgresql+psycopg' or url.database!=args.database or args.database in ('postgres','template0','template1'):
        raise SystemExit('Explicit application database identity required; no administrative/default DB')
    engine=make_engine(Settings(database_url=raw))
    try:
        with engine.begin() as connection:
            if connection.scalar(text('SELECT current_database()'))!=args.database:
                raise RuntimeError('Database identity mismatch')
            if connection.scalar(text('SELECT version_num FROM alembic_version'))!=migration_head():
                raise RuntimeError('Migrate and review inventory before grants')
            configure_runtime_roles(connection,web=args.web,integration=args.integration,
                                    maintenance=args.maintenance,audit_owner=args.audit_owner)
        print('Restricted runtime grants configured; no database roles or credentials created.')
    except Exception:
        raise SystemExit('Role configuration failed; transaction rolled back. Check reviewed role membership/ownership and schema state without exposing credentials.') from None
    finally:
        engine.dispose()


if __name__=='__main__':
    main()
