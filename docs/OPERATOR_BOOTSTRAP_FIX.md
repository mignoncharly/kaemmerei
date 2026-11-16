# PostgreSQL operator bootstrap repair

The CLI selects `MIGRATION_DATABASE_URL` under database hardening. Identity and
MFA mutations remain schema-owner operations, but hardening transfers
`identity_audit` to a separate NOLOGIN owner. With `INHERIT FALSE, SET TRUE`
membership, the migrator has neither direct INSERT permission nor inherited audit
ownership. The failure also affects password resets, disabling users, MFA
authorization/recovery/enforcement and key rotation: all use `identity_service.audit`.

Migration `0028_operator_audit` adds a single append-only SECURITY DEFINER
function owned by the existing audit-table owner. Only the direct login owning
`ohvr_security` may append operator records; registered runtime roles are also
explicitly rejected. PUBLIC receives no execute grant. The function fixes the
principal and actor, supplies a database timestamp, validates arguments, and
uses a fixed `pg_catalog,pg_temp` search path with qualified application objects.
The existing insert trigger supplies correlation/outcome. Existing FORCE RLS
policies admit the audit owner, and immutable triggers still reject UPDATE and
DELETE. No table grants or RLS policies change.

The shared audit service flushes administrative mutations, then invokes this
function through the same SQLAlchemy session/transaction. A failed append rolls
back the mutation; a later failure rolls back the append. No function commits,
no separate audit connection exists, and application transactions never switch
roles. Web auditing with an actor continues using its existing scoped INSERT.

Transactional role switching of the entire CLI operation would lose the schema
owner's access to private MFA tables. Switching just for each application append
would complicate ORM flushing and exception cleanup. The definer confines that
boundary to a single INSERT. Deployment DDL briefly uses `SET LOCAL ROLE` solely
to grant execute after ownership transfer (PostgreSQL rewrites owner ACLs).
The migration works on both fresh schemas and already hardened revision 0027;
its entire DDL transaction rolls back on failure. Downgrade intentionally fails.

`configure_database_roles.py` delegates to `configure_runtime_roles`, which now
transfers the new function and revokes all runtime execute grants before its
transaction commits. Existing hardened deployments need only the migration;
there is no need to reconfigure database roles or change their passwords.

## Deployment on Debian

These commands are instructions, not a record of deployment. First merge this
patch into `mignoncharly/kaemmerei` main. Use the existing protected operator
shell/environment used for the failing CLI, with its verified TLS connection,
application settings and `MIGRATION_DATABASE_URL` for `ohvr_migrator`. Do not copy
credentials into shell commands or source an unreviewed environment file. Take
the normal protected backup before migration. Stop writers using the existing
service procedure during the code/schema update; service-unit names are not
specified in this repository's Debian deployment context.

From a clean deployment checkout, after merging:

```bash
cd /opt/open-herz
git fetch origin main
git switch main
git merge --ff-only origin/main
PYTHON=/opt/open-herz-runtime/venv/bin/python
: "${MIGRATION_DATABASE_URL:?Load the existing protected operator environment}"
"$PYTHON" - <<'PY'
import os
from sqlalchemy.engine import make_url
from app.config import get_settings, validate_database_tls
u = make_url(os.environ['MIGRATION_DATABASE_URL'])
assert u.drivername == 'postgresql+psycopg'
assert u.database == 'openherz_pilot' and u.username == 'ohvr_migrator'
s = get_settings()
s.validate()
assert s.enforce_database_security
if s.production:
    validate_database_tls(os.environ['MIGRATION_DATABASE_URL'])
PY
"$PYTHON" -m app.cli init-db
"$PYTHON" -m app.cli schema-inventory
```

No dependency changes are required by this patch. The Python path above is the
runtime found in the supplied workspace; if the target uses another existing
virtualenv, set `PYTHON` to that interpreter. Migration head must be
`0028_operator_audit`. Review inventory output and then restart the existing web
and integration services with their original restricted runtime environments.
Do not supply operator credentials to those services.

Retry in that same protected operator shell:

```bash
"$PYTHON" -m app.cli add-department 'Kämmerei'
"$PYTHON" -m app.cli add-user pilot_admin --role admin
"$PYTHON" -m app.cli list-departments
```

The user command prompts twice for a new password through getpass; do not pass a
password on the command line. An admin has no department assignment. If an account
already exists, creation fails rather than overwriting it. The first login must
change the password. Use the existing verified MFA enrollment process if MFA is
required; this repair creates no MFA bypass.

## Validation evidence

Executed with Python 3.14.10 and PostgreSQL 17.12 in a NEW loopback-only test
cluster on port 55439, separate from the existing cluster. Synthetic database
names and temporary restricted roles are generated and removed by repository
fixtures. The test bootstrap superuser creates/removes test roles only;
application operations run as the restricted schema-owner or runtime logins.
The new tests use audit membership `INHERIT FALSE, SET TRUE`.

- Identity/MFA/TLS tests on SQLite: 47 passed, 2 PostgreSQL-only tests skipped.
  This run is not evidence for PostgreSQL RLS.
- `tests/test_phase2.py tests/test_phase3.py tests/test_phase9_mfa.py
  tests/test_postgresql_integration.py --database postgresql`: 51 passed.
- `tests/test_operator_bootstrap.py tests/test_server_security.py
  tests/test_operator_tls.py --database postgresql`: 38 passed.
- `python -m pip check`: no broken requirements.
- `git diff --check`: passed.

The new tests execute actual CLI commands after hardening, exercise fresh and
hardened-0027 migration paths, audit immutability, direct migrator INSERT denial,
runtime denial (including an accidental EXECUTE grant), atomic rollback in both
directions, password/user administration and MFA recovery/enforcement/rotation.
Existing PostgreSQL tests also exercise web auditing and MFA concurrency.
A Starlette/httpx deprecation warning remains unrelated to this fix.

The supplied pilot database was not inspected, migrated, reset or changed. No
passwords or existing pilot records were overwritten. Test connections did not
exercise deployment TLS: the existing production verify-full enforcement and
TLS regression tests remain in place. No browser or frontend changes were made.
