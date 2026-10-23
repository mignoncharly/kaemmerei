"""Known advisory floors are required for production, not synthetic diagnostics."""
import pytest
from sqlalchemy import text
from app.server_security import validate_pg_dump_version,validate_server_security,validate_server_version


@pytest.mark.parametrize('number',[160015,160016,170011,170012,180006,180007])
def test_reviewed_security_floor_accepts_fixed_minor_or_later(number):
    validate_server_version(number)


@pytest.mark.parametrize('number',[160014,170010,180003,180005,150019,190000,True,None,'180006',-1])
def test_affected_unknown_and_malformed_versions_are_rejected(number):
    with pytest.raises(ValueError):validate_server_version(number)


@pytest.mark.parametrize('output',[
    b'pg_dump (PostgreSQL) 18.6\n',b'pg_dump (PostgreSQL) 17.11 (Vendor build)\n',
    b'pg_dump (PostgreSQL) 16.15\r\n'])
def test_patched_matching_family_backup_client_is_accepted(output):
    validate_pg_dump_version(output)


@pytest.mark.parametrize('output',[
    b'pg_dump (PostgreSQL) 18.3\n',b'pg_dump (PostgreSQL) 17.10\n',
    b'pg_restore (PostgreSQL) 18.6\n',b'unknown','not-bytes',b'x'*4097])
def test_known_affected_or_unverified_backup_client_is_rejected(output):
    with pytest.raises(ValueError):validate_pg_dump_version(output)


@pytest.mark.postgresql
def test_actual_server_version_is_read_only_and_production_guard_is_explicit(environment,request):
    if request.config.getoption('--database')!='postgresql':
        pytest.skip('Actual PostgreSQL server identity required')
    _,app=environment
    with app.state.engine.connect() as connection:
        number=int(connection.scalar(text('SHOW server_version_num')))
    request.node.user_properties.append(('observed_server_version_num',number))
    if (number//10000,number%10000) in ((18,3),(16,14),(17,10)):
        with pytest.raises(ValueError):validate_server_security(app.state.engine)
    else:
        try:validate_server_version(number)
        except ValueError:
            with pytest.raises(ValueError):validate_server_security(app.state.engine)
        else:validate_server_security(app.state.engine)
