"""Reviewed native server security floor; not a complete advisory clearance.

Official CVE-2026-14666 and CVE-2026-6479 reviewed 2026-10-22.
Development diagnostics remain possible on an isolated synthetic test server.
Production requires this floor and separate current host/client patch review.
"""
import re
from sqlalchemy import text

MINIMUM_PATCH={16:15,17:11,18:6}


def validate_server_version(number):
    if type(number) is not int or number<0:
        raise ValueError('Unverified PostgreSQL server version')
    major,minor=divmod(number,10000)
    if major not in MINIMUM_PATCH or minor<MINIMUM_PATCH[major]:
        raise ValueError('PostgreSQL component is below the reviewed production security baseline; patched host/client review required')


def validate_pg_dump_version(output):
    if not isinstance(output,bytes) or len(output)>4096:
        raise ValueError('Unverified PostgreSQL backup client version')
    match=re.search(rb'^pg_dump \(PostgreSQL\) ([0-9]+)\.([0-9]+)(?:\s|$)',output)
    if not match:raise ValueError('Unverified PostgreSQL backup client version')
    validate_server_version(int(match[1])*10000+int(match[2]))


def validate_server_security(engine):
    if engine.dialect.name!='postgresql':
        raise ValueError('Production server security review requires PostgreSQL')
    with engine.connect() as connection:
        validate_server_version(int(connection.scalar(text('SHOW server_version_num'))))
