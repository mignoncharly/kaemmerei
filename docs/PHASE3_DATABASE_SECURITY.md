# Phase 3 — Database integrity, roles, RLS and audit

Date: 2026-10-21. Scope: P03-T01–T08 in the ten-phase remediation plan.
Implementation is verified against synthetic databases only. Production deployment,
DBA/security acceptance of D03, and business-data migration remain outstanding.

## Schema and legacy migration

New forward migrations are `0015_schema_integrity` and `0016_database_security`.
Previously applied migration files are unchanged. The missing tax-reviewer foreign
key now references stable user IDs with `ON DELETE SET NULL`; existing valid IDs
are preserved. Invalid references stop migration and require a reviewed mapping.
No user, contract, amount, document or historical identity is silently repaired/deleted.

The inventory reports table, rule, count and record IDs only. Constraints cover
role/department consistency, contract/review/tax/payment/direction states, nonnegative
amounts and document sizes, date order, notice months 0–120, renewal months 1–120,
positive versions, automatic-renewal prerequisites, contact scope, and exactly one
document source. Optional old department associations on admin/reviewer accounts
must be reviewed before migration; they are not silently cleared.

`schema-inventory` compares dialect-compiled types, nullability, column sets,
foreign keys including deletion rules, check names, indexes and unique constraints.
Python insertion defaults and SQL server defaults are intentionally distinct and
are not compared as equivalent expressions. The private security schema, functions,
policies and triggers are database controls, not missing ORM tables. Their behavior
is checked separately using real runtime connections.

SQLite batch rebuilds run in an explicit DDL transaction with FK enforcement off
only on the migration connection, `foreign_key_check` before commit, and enforcement
restored in `finally`. The existing status triggers would disappear on rebuild;
0015 installs the equivalent named CHECK. An invalid inventory leaves migration
version and original rows unchanged. Forward-only recovery preserves security;
do not disable RLS or restore broad runtime ownership to work around errors.

## Role and grant contract

| Role | Access |
|---|---|
| Migration/operator owner | Explicit migrations, legacy inventory, identity provisioning and backup/restore; never a web login credential |
| Web LOGIN | Metadata bootstrap, scoped business reads/writes, own sessions/password rotation, constrained identity administration; no general password/token hash SELECT |
| Integration LOGIN | Scoped contract/document reads and token last-used update; no credential tables, password resolver, contract lock or business writes |
| Maintenance LOGIN | `purge_expired()` only, plus role validation; deletes expired sessions and attempts older than seven days and records counts |
| Audit NOLOGIN owner | Owns revisions, identity audit, security events and narrow audit trigger functions; runtime roles cannot inherit it |

Runtime roles must have NOSUPERUSER, NOBYPASSRLS, NOCREATEDB, NOCREATEROLE and
NOREPLICATION. Separate direct LOGIN connections are required; `SET ROLE` simulation
does not satisfy the test. Startup rejects wrong registry entries, ownership or
owner membership and missing forced RLS. PUBLIC table/sequence/schema access and
security function execution are revoked. No permissive default grants are installed;
future migrations must explicitly review new objects and grants.

`scripts/configure_database_roles.py` configures four **existing** DBA-created roles;
it creates no production role or password. Run only with an explicit migration
connection and exact target database name at head 0016. The owner needs permission
to transfer objects to the NOLOGIN audit owner. Configure once after migration and
repeat after migrations that change privileges. Review existing inherited grants:
the script cannot certify arbitrary pre-existing role memberships as safe.

```powershell
# URLs come from the operator's secure environment; never paste credentials into docs.
& $python -m app.cli schema-inventory
& $python -m app.cli init-db
& $python scripts/configure_database_roles.py --database <dedicated-application-db> `
  --web <web-role> --integration <integration-role> `
  --maintenance <maintenance-role> --audit-owner <audit-owner>
& $python -m app.cli purge-sessions
```

Web workers receive DATABASE_URL, INTEGRATION_DATABASE_URL and
ENFORCE_DATABASE_SECURITY=1. Production requires these and explicit hosts/TLS.
Only the operator process receives MIGRATION_DATABASE_URL; only maintenance receives
MAINTENANCE_DATABASE_URL. CLI/Alembic refuse to use web credentials for secured
operator work. Backup/restore remains an explicit privileged DBA operation into a
new target with private document storage restored as a matching set. Runtime roles
receive no backup privilege. A production restore rehearsal is still Phase 9/10 work.

## RLS and request identity

Sixteen application tables use ENABLE and FORCE RLS, with SELECT visibility and
separate INSERT/UPDATE `WITH CHECK` policies. Business children, revisions and events
inherit parent scope. Admin/reviewer global reads follow the Phase 2 capability
matrix; ordinary department users and scoped integration tokens see their own
department. Assignments never create read authority. Inactive departments and
revoked credentials fail resolution. Reviewer decisions require capability, active
team membership, assignment and existing parent read scope; ordinary reviewers
cannot edit contracts. Archived parents cannot authorize child writes/decisions.

The application supplies hashes of bounded opaque session cookies/bearer tokens,
never a client-selected role/user ID. `Session.after_begin` uses its passed Connection
to call `prepare_context`; the resolver validates current database session/token,
user, expiry and department, then caches a principal **for that transaction**.
Each new transaction revalidates, including reads after token-usage commits.
Commit/rollback removes local settings; alternating identities through the same
physical pooled connection is tested. Revocation takes effect by the next
transaction. Existing application authorization remains mandatory.

`lock_contract` is a narrow web-only function that locks an already readable parent
without granting contract UPDATE to assigned approvers. It preserves the existing
review/archive lock protocol. Comprehensive aggregate races remain Phase 4 work.

Credential resolution and lock functions use qualified objects, fixed
`search_path=pg_catalog,pg_temp`, reviewed owner identities and revoked PUBLIC
execution. Integration cannot execute the password resolver or read session/hash
columns. Table policies use an explicit trusted-owner CASE to avoid recursive
bootstrap policy evaluation; the migration owner and audit owner are privileged.

**Threat boundary:** shared-login custom GUC context defends against omitted query
filters and unintended ORM access. An attacker with unrestricted SQL execution or
the application database credential can forge context, call bootstrap functions or
change authentication records within that credential's grants. This is not a
database boundary against that attacker. Parameterized SQL, application authorization,
credential protection and operational controls remain essential.

## Audit

Append-only revisions/identity audit/security events reject UPDATE and DELETE by
triggers; runtime roles also lack those grants and TRUNCATE. Events are inserted by
separately owned triggers for contract/document/task/review mutations in the same
transaction. Stable actor/token IDs, principal, action, target, UTC timestamp,
outcome, request UUID and structural change metadata are stored. No passwords,
raw tokens, file bytes or complete row snapshots enter security event details.
Identity-audit triggers overwrite actor/principal/correlation and infer denied
outcomes from the application's denied action names. Users may read their own
identity-audit rows (needed by INSERT RETURNING); the administrative UI stays admin-only.

Events record committed changes, not every attempted database attack. A rolled-back
transaction rolls back its audit rows. Migration/schema owners can alter DDL and
are outside append-only runtime protection. External immutable logging, retention,
production backup access and tamper evidence remain operational decisions.

SQLite uses equivalent append-only triggers and application identity correlation,
but **has no RLS or separate SQL login enforcement**. SQLite passing cannot satisfy
the PostgreSQL role/RLS acceptance gate.

## Verification and reproduction

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
$python = 'C:\kämmerei\.venv\Scripts\python.exe'
& .\scripts\Start-TestDatabase.ps1 -Python $python
& $python -m pytest -q -ra
& $python -m pytest -q -ra --database postgresql
& $python -m pytest -vv -ra --database postgresql -m postgresql
& $python -m pytest -q --database postgresql tests/test_phase3_schema.py
```

The existing native test cluster/passfiles/binary identity check are retained. No
new Docker dependency is required. `TEST_POSTGRES_ADMIN_URL`/PGPASSFILE remain the
disposable-database control connection. RLS tests additionally need the test-only
bootstrap identity to create temporary restricted roles: the native helper verifies
the marked cluster with its private bootstrap passfile, or an explicit
TEST_POSTGRES_BOOTSTRAP_URL must match the same loopback control endpoint.
That bootstrap identity is never an application runtime identity.

Each fixture creates a uniquely named marked database, confirms OID/owner/comment,
creates four random test roles with random in-memory credentials, and tests actual
web/integration/maintenance logins. Cleanup rechecks database and role OIDs/comments,
reassigns audit objects inside that database, removes only generated roles and drops
only its identified database. A non-secret `.verification/role-cleanup-*.json`
journal is retained if interrupted. Recovery requires DBA review of every saved
OID/comment/database identity; never wildcard-delete roles or delete cluster storage.

New tests cover unscoped SQL, parent/child joins, forbidden department moves,
malformed/missing context, credential denial, reviewer decisions/revocation,
self-escalation, pooled reuse, post-commit reads, audit mutation, narrow maintenance,
owner rejection, schema equality, invalid direct writes and legacy migration abort.
Full R01/R04/R10 and Phase 2 regressions remain in the complete suite.

### Local results

Source: `5986a7473e3772e0f9a4e390aadc979101a1f9a9`. Windows, Python 3.14.3,
pytest 9.1.1, native PostgreSQL 18.3. [Machine-readable results](evidence/phase3-local.json)
contain local JUnit hashes; ignored `.verification` XML remains on this workstation.

| Run | Selected | Passed | Skipped | Failed / xfailed | Time |
|---|---:|---:|---:|---:|---:|
| Full PostgreSQL | 81 | 81 | 0 | 0 / 0 | 153.32s |
| Full SQLite | 81 | 69 | 12 PostgreSQL-only | 0 / 0 | 32.58s |
| Explicit PostgreSQL selection | 12 | 12 | 0 | 0 / 0 | 54.89s |
| Final schema/legacy selection, each backend | 4 | 4 | 0 | 0 / 0 | SQLite 3.26s; PostgreSQL 11.90s |

Both full runs additionally passed 15 subtests. The explicit selection deselected
69 ordinary tests and executed 11 restricted-role cases plus the PostgreSQL
application lifecycle. The final legacy-schema selection verifies the last historical
audit-outcome correction. Two remaining warnings in final full runs: Starlette/AnyIO
deprecated BlockingPortal alias and managed Windows pytest cache ACL. Neither is
suppressed. Read-only cleanup check found zero harness databases and zero generated
temporary roles. Production database/schema/storage and unrelated services were untouched.

### Hosted verification

Implementation pushed successfully to configured `main`; actual Phase 3 run:
[39600834032](https://github.com/mignoncharly/kaemmerei/actions/runs/39600834032).
Completed successfully for the exact implementation SHA above. SQLite,
PostgreSQL 18 and native-postgresql jobs all passed, including dependency
installation, migrations, full pytest and both PostgreSQL jobs' explicit
integration/RLS selection. Run/job/step and all three uploaded artifact metadata
were inspected through the GitHub API; artifact archives were not downloaded.
[Hosted evidence](evidence/phase3-ci-39600834032.json) records the actual conclusions.
**Phase 3 technical gate is verified locally and in hosted CI.** Production
DBA/security acceptance, business-data migration and restore rehearsal remain open.
Hosted success is not inferred from YAML. CI includes native PostgreSQL and
PostgreSQL 18 service jobs, full suites and explicit PostgreSQL test selection;
the service bootstrap password is synthetic and confined to the disposable runner.

### Acceptance checklist

- [x] Clean/populated migration and invalid legacy abort preserve data on both backends.
- [x] Schema inventory has no unexplained structural differences; tax reviewer FK enforced.
- [x] Real restricted LOGIN roles enforce parent/child isolation and denied modifications.
- [x] Authentication bootstrap, password rotation, assigned decisions and maintenance work under real grants.
- [x] Pool reuse, malformed/missing identity, revocation and post-commit reads checked.
- [x] Audit/event updates/deletes/TRUNCATE denied under runtime roles; separate ownership checked.
- [x] Full regular suites and actual PostgreSQL tests pass; R01/R04/R10 remain passing regressions.
- [x] SQLite and shared-login SQL-execution threat boundaries documented.
- [x] Hosted Phase 3 run completion inspected and recorded.
- [ ] DBA/security D03 acceptance, production legacy inventory/migration and restore rehearsal.

### Affected implementation files

| Area | Files |
|---|---|
| Migration and schema | alembic/env.py, versions/0015_schema_integrity.py, versions/0016_database_security.py, sql/0016_security.sql, app/schema_rules.py, app/schema_inventory.py, app/models.py |
| Roles/operator operations | app/db_roles.py, scripts/configure_database_roles.py, app/cli.py, app/config.py, .env.example |
| Request/transaction authorization | app/db.py, app/authorization.py, app/main.py, app/security.py, app/identity_service.py |
| Regression and CI | tests/runtime_support.py, tests/test_phase3.py, tests/test_phase3_schema.py, pytest.ini, .github/workflows/phase1-verification.yml |

0015 and its Phase 3 rule definitions must remain immutable after application;
future changes require a new forward migration, rather than editing historical rules.

### Investigation history

Initial role setup required CREATE on the private schema for the trusted NOLOGIN
owner to receive trigger-function ownership. An initial cleanup bug was corrected;
the four exact generated roles were identified and removed after confirming their
test database no longer existed. Subsequent fixtures clean up successfully.
Restricted-role tests exposed INSERT RETURNING audit visibility and approver parent
locking incompatibilities; both were corrected without broadening contract writes.
Schema comparison exposed the SQLite status-trigger rebuild issue and a type
comparison normalization issue (DATETIME versus dialect TIMESTAMP).

## Sources and remaining work

PostgreSQL's [row security documentation](https://www.postgresql.org/docs/18/ddl-rowsecurity.html)
describes owner/BYPASSRLS behavior, forced policies and policy checks. Its
[function documentation](https://www.postgresql.org/docs/18/sql-createfunction.html)
describes SECURITY DEFINER ownership, fixed search paths and PUBLIC execution.
SQLAlchemy's [session event documentation](https://docs.sqlalchemy.org/en/20/orm/session_events.html)
supports using the supplied connection for transaction initialization.

Phase 4 remains responsible for content-bound approval, activation/tax rules and
full aggregate concurrency. Phases 5–10 and municipal/DBA production acceptance
are not completed by this phase. No business database was migrated or inspected.
