"""DBA entry-point policy rejects unsafe production config before connecting."""
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

import pytest
from app.config import validate_database_tls
from scripts import configure_database_roles as tool


def invoke(raw,environment):
    arguments=['roles','--database','register','--web','web','--integration','integration',
               '--maintenance','maintenance','--audit-owner','audit']
    return patch.dict('os.environ',{'APP_ENV':environment,'MIGRATION_DATABASE_URL':raw}),patch('sys.argv',arguments)


@pytest.mark.parametrize('query',['','?sslmode=disable','?sslmode=require',
    '?sslmode=verify-ca','?sslmode=verify-full','?sslmode=verify-full&sslrootcert=relative.crt',
    '?sslmode=verify-full&sslrootcert=x&sslrootcert=y'])
def test_production_dba_rejects_insecure_tls_before_engine_creation(query):
    secret='SYNTHETIC_NEVER_PRINT_ME'
    env,argv=invoke('postgresql+psycopg://owner:'+secret+'@example.invalid/register'+query,'production')
    with env,argv,patch.object(tool,'make_engine') as factory:
        with pytest.raises(SystemExit,match='production requires') as error:tool.main()
        assert secret not in str(error.value)
        factory.assert_not_called()


@pytest.mark.parametrize('environment',['production','development'])
def test_valid_policy_reaches_existing_identity_checks_without_requiring_web_mfa_config(environment):
    query='?sslmode=verify-full&sslrootcert='+quote(str(Path.cwd()/'synthetic-ca.crt'),safe='') if environment=='production' else ''
    env,argv=invoke('postgresql+psycopg://owner@example.invalid/register'+query,environment)
    with env,argv,patch.object(tool,'make_engine',side_effect=RuntimeError('STOP_BEFORE_CONNECT')) as factory:
        with pytest.raises(RuntimeError,match='STOP_BEFORE_CONNECT'):tool.main()
        factory.assert_called_once()


def test_invalid_environment_and_malformed_url_fail_redacted_before_connect():
    for raw,environment in [('not a url SYNTHETIC_NEVER_PRINT_ME','production'),
                            ('postgresql+psycopg://owner@localhost/register','prodution')]:
        env,argv=invoke(raw,environment)
        with env,argv,patch.object(tool,'make_engine') as factory:
            with pytest.raises(SystemExit) as error:tool.main()
            assert 'SYNTHETIC_NEVER_PRINT_ME' not in str(error.value)
            factory.assert_not_called()
