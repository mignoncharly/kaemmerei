# Phase 1 baseline and verification evidence

## Current acceptance report — U009, 2026-10-21

This section supersedes the dated baseline below. Earlier failures are retained as history.

**Local application/database acceptance: passed.** Source implementation: `558c045` on `main`.
Native Windows startup was confirmed by the operator before this session. An independent
launcher repeat in this managed agent stopped at the owner-only directory ACL check;
it did not run initdb, restart the running cluster, or reproduce token error 87.
Hosted verification passed for this implementation; exact run and job evidence is recorded below.
This is technical Phase 1 acceptance, not production approval or completion of phases 2–10.

### Diagnosis and changes

| Issue | Diagnosis / implemented correction |
|---|---|
| Initial Windows token error 87 | Historical initdb host-token failure; the existing dedicated cluster is initialized and running. No reinitialization was attempted. |
| Startup did not return to PowerShell | PostgreSQL children could inherit captured stdout/stderr pipes. Operator-supplied `run_pg_ctl_start` redirects to a regular logfile, stdin DEVNULL, bounded timeout. Preserved and covered by a regression test. |
| Unicode path decoding | Operator-supplied identity check compares the first eight binary pg_control bytes against the connected cluster. No decoding of `SHOW data_directory`. Preserved; matching, mismatched and truncated identities tested. |
| Stale setup lock | Prior operator cleanup was historical. Lock ownership rules were retained. A live/existing lock remains present and blocks setup in the new regression. |
| Misleading launcher error | `Start-NativeTestDatabase.ps1` now reports the specific preceding failure without labeling every error as token error 87. |
| R01 | List filter metadata queries now use the same department scope as contract visibility. Direct details, searches, reports, export, document metadata/downloads, API scope and forged parent/child references have passing regression coverage. |
| R04 | Review updates lock the parent contract on PostgreSQL and reject archived contracts with HTTP 409 before mutation. Review controls are hidden for archived contracts. Admin/reviewer rejection preserves review content, timestamps, actor and audit row set. |
| R10 | Central active-membership check applies to session authentication, login and object read/write authorization. Scoped API tokens also deny inactive/missing departments. Existing sessions lose protected access immediately on the next request. Explicit global admin/reviewer roles retain their existing independent authority. |
| Disposable database safety | Only loopback `postgres` control connections as restricted `ohvr_verify` are accepted. Each fresh `ohvr_test_<uuid>` database has an OID, owner and random comment marker; identity and clean schema are checked before migration, and identity is checked again before DROP. Changed identity prevents deletion. |
| Alembic warnings | Explicit `path_separator = os` removes the legacy Alembic configuration warning. No schema migration or business-data backfill is needed for these fixes. |

Affected implementation: `app/logic.py`, `app/security.py`, `app/main.py`,
`scripts/native_test_database.py` (operator fixes retained), `scripts/Start-NativeTestDatabase.ps1`,
`tests/support.py`, `tests/test_phase1.py`, `tests/test_native_database.py`,
new `tests/test_acceptance.py`, `tests/test_database_safety.py`, `tests/test_postgresql_integration.py`,
`pytest.ini`, `alembic.ini`, `scripts/verify_phase1.py`, and `.github/workflows/phase1-verification.yml`.
The pre-existing whitespace-only edit in `scripts/Start-TestDatabase.ps1` is left untouched.

### Executed checks

Runtime: Windows, Python 3.14.3, pytest 9.1.1, native PostgreSQL 18,
Psycopg/SQLAlchemy, existing test cluster at loopback port 55432.
The agent did not inherit TEST_POSTGRES_ADMIN_URL/PGPASSFILE; it configured its test processes
to use the existing dedicated role and existing passfile without reading or printing credentials.
An additional read-only probe used the existing private bootstrap passfile solely to run
`assert_connected_cluster`: **the live binary cluster identity matched local marked storage**.
Separate test-role queries confirmed server version **18.3**, server encoding **UTF8**, and
current role **ohvr_verify**. No role provisioning or server configuration was performed by those probes.

| Check | Collected / executed | Passed | Failed / errors | Skipped | Xfailed | Result |
|---|---:|---:|---:|---:|---:|---|
| Default `pytest -q -ra` (SQLite) | 44 | 43 | 0 | 1 | 0 | 15 additional subtests passed; 19.05s |
| Full `pytest -q -ra --database postgresql` | 44 | 44 | 0 | 0 | 0 | 15 additional subtests passed; 40.29s |
| Explicit `tests/test_postgresql_integration.py --database postgresql` | 1 | 1 | 0 | 0 | 0 | 1.74s; clean upgrade, repeat upgrade, identity, cleanup |
| Stdlib `verify_phase1.py --database postgresql` | 22 | 22 | 0 | 0 | 0 | 35.09s; no expected failures |

The SQLite skip is deliberate: the explicitly PostgreSQL-only lifecycle check cannot supply
PostgreSQL evidence on SQLite. It executed and passed on PostgreSQL, with no skips.
The full PostgreSQL run includes **20 application checks against migrated PostgreSQL**,
two clean/populated migration checks and the explicit lifecycle check; the other 21 checks
cover configuration and safety without application database writes. This is not a `-k postgres` selection.
All original ten application tests execute against PostgreSQL, including create/read/edit,
stale version rejection, archive, persisted before/after history, CSRF, authentication and department isolation.
Document upload, storage, download and API retrieval, review creation/update and archived refusal are exercised.
Populated `0001 -> 0003 -> 0013_integration_tokens` migration preserves contract/version/history/document metadata.
Fresh migrations and repeated head upgrades pass. No existing application database was migrated.

Local machine-readable evidence: `.verification/acceptance-sqlite.xml`,
`.verification/acceptance-postgresql.xml`, `.verification/acceptance-postgresql-explicit.xml`,
and `.verification/phase1-postgresql.json`. JUnit counts include 15 subtests, so its `tests=59`
corresponds to 44 pytest items plus those subtests. A sanitized summary is committed under `docs/evidence`.

Remaining local warnings: Starlette uses deprecated `anyio.abc.BlockingPortal`; pytest cannot
write its cache under this managed Windows identity. Neither warning was suppressed. Moving
the cache under `.verification` reproduced the same inherited/private-ACL issue, so that attempted
configuration change was removed. Test bodies and JUnit output still complete successfully.
Dependency upgrades and workspace-owner cache repair are separate maintenance work.

### Reproduce in normal Windows PowerShell

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
$python = 'C:\kämmerei\.venv\Scripts\python.exe'
& .\scripts\Start-TestDatabase.ps1 -Python $python
if ($LASTEXITCODE -ne 0) { throw 'Native test startup failed' }
& $python -m pytest -q -ra
if ($LASTEXITCODE -ne 0) { throw 'Default tests failed' }
& $python -m pytest -q -ra --database postgresql
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL suite failed' }
& $python -m pytest -vv -ra --database postgresql tests/test_postgresql_integration.py
if ($LASTEXITCODE -ne 0) { throw 'Explicit PostgreSQL lifecycle failed' }
& $python scripts/verify_phase1.py --database postgresql
if ($LASTEXITCODE -ne 0) { throw 'Stdlib PostgreSQL checks failed' }
```

The startup wrapper exports TEST_POSTGRES_ADMIN_URL and PGPASSFILE in that terminal.
Use the existing cluster; do not delete its data or reset its credentials. For ACL errors,
use the already authorized normal host terminal rather than weakening directory permissions.
For a setup lock, establish whether its process still exists before any operator cleanup;
the implementation never automatically deletes an existing lock.

### Hosted CI evidence

GitHub API inspection confirmed [run 39589726718](https://github.com/mignoncharly/kaemmerei/actions/runs/39589726718)
completed successfully for source `558c0451b346265675aaeb411cb6ce4971b31af5` on `main`.
All three jobs succeeded: `sqlite` (119187370759), `postgresql` (119187371014),
and `native-postgresql` (119187371032). Successful steps include dependency
installation, the stdlib verification runner, full pytest, restricted role provisioning,
and explicit PostgreSQL-only pytest execution. The native job starts its own marked cluster,
checks native-manager safety, executes migrations/application/security tests and stops that cluster
through its exit trap. The PostgreSQL 18 service job was retained; no local Docker dependency was added.
The full-suite invocations execute the migrations and R01/R04/R10 regressions from this source SHA.

Three artifact records are present. Artifact metadata was verified; artifact contents were not
downloaded, so exact hosted counts/warnings are not inferred from the local JUnit files.
The API run/job/step evidence is saved in [phase1-acceptance-ci-39589726718.json](evidence/phase1-acceptance-ci-39589726718.json).
Local counts and JUnit hashes are saved in [phase1-acceptance-local.json](evidence/phase1-acceptance-local.json).
The prior run at `a434648` was also checked directly and succeeded, but it does not verify these new fixes.

For any subsequent source change, require a new successful workflow run for its SHA:
open Actions → Phase 1 verification foundation → select the new `main` run → confirm all three
jobs and their PostgreSQL/full-suite/explicit-lifecycle steps succeed. Do not substitute YAML inspection.

### Acceptance checklist and boundaries

- [x] Dedicated native cluster running; restricted-role authentication succeeds.
- [x] Cluster identity check preserved, regression-tested and matched against the live server without Unicode path decoding.
- [x] Nonblocking Windows startup previously confirmed by operator; file-based subprocess regression passes.
- [x] Isolated PostgreSQL clean/populated migrations and application operations pass.
- [x] R01/R04/R10 have normal passing regression tests; zero expected failures remain.
- [x] Safe test cleanup demonstrated; generated-name/OID/owner/comment mismatch fails closed.
- [x] No cluster deletion, unrelated service stop or business database migration performed. A final read-only catalog check found zero `ohvr_test_<uuid>` databases remaining.
- [ ] Independent Windows launcher repeat from agent: ACL-blocked; operator's normal-shell success is the available Windows startup evidence.
- [x] Hosted run for implementation SHA 558c045: all three jobs passed; run and step evidence recorded.

Remaining product risks are outside this acceptance scope: database RLS is absent (R09/Phase 3);
explicit approver assignment/separation of duties and content-bound decisions remain open (R02/R03);
broader aggregate concurrency/retention/audit, synchronization, reporting and other findings retain
their phase assignments. The PostgreSQL test role's NOBYPASSRLS attribute does not establish RLS policies.
Branch protection is an account setting still unverified. No deployment or production acceptance is claimed.

## Historical baseline (preserved)

Recorded: 2026-10-21. Implementer: Codex. Scope: P01-T01–T08 technical foundation.

Native setup update (U007): local setup now defaults to the installed native PostgreSQL binaries, with a separate marked cluster and private passfiles under ignored .local-postgres. Docker is optional locally. Ten native-manager safety checks pass; this session's actual Windows startup attempt stopped at denied owner-only directory ACLs before credentials were written. A native Linux CI job is added alongside the existing successful PostgreSQL 18/SQLite jobs. See [VERIFICATION_SETUP.md](VERIFICATION_SETUP.md) and HANDOFF for the latest run evidence.

Subsequent setup updates (U005/U006): Git is initialized and main was published to https://github.com/mignoncharly/kaemmerei.git. Source commit d9e39e520495928355dfe02b198c56150bf82077 passed both Linux CI jobs in [run 39571113046](https://github.com/mignoncharly/kaemmerei/actions/runs/39571113046), including PostgreSQL and direct pytest. See [evidence](evidence/phase1-ci-39571113046.json). Earlier no-repository, missing-pytest, and blocked-bootstrap observations below remain historical local-environment evidence. Docker Compose/host setup automation is supplied; actual local Docker execution remains unverified. See [VERIFICATION_SETUP.md](VERIFICATION_SETUP.md).

## Source and runtime

- Workspace: `C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase`.
- No Git repository was found by `git rev-parse --show-toplevel` or `git status --short`; both returned `fatal: not a git repository`. No branch, commit, tracked/untracked inventory, or commit-based rollback can be claimed. Source files remain local workspace files.
- No applicable AGENTS.md was found in the workspace search or checked ancestor paths.
- Observed runtime: Windows 11 build 26200, CPython 3.14.3, 64 bit.
- Usable interpreter: `C:\kämmerei\.venv\Scripts\python.exe`. The project-local `.venv` exists but has no FastAPI package metadata; it is not the tested interpreter.
- Installed PostgreSQL executable: version 18.3 at `C:\Program Files\PostgreSQL\18\bin`. This identifies available binaries, not a verified running application database.
- Source migration head: `0013_integration_tokens`, obtained through Alembic ScriptDirectory without opening the business database.
- Post-implementation source fingerprint: `.verification/phase1-source-sha256.json`, 38 application/test/migration/script/configuration inputs with SHA-256 hashes. This is a local snapshot after Phase 1 edits, not an invented pre-change Git revision. All 31 Python source files in that inventory passed AST syntax parsing; documentation relative links were checked with no missing targets.
- Linux/Python 3.14/PostgreSQL 18 jobs were initially unexecuted; U006 now records successful hosted execution for the source commit above. No wider runtime compatibility claim is made.

## Dependency inventory

Authoritative manifests: `requirements.txt` and `requirements-dev.txt`. Runtime versions observed in the usable environment:

| Package | Installed |
|---|---|
| fastapi | 0.128.2 |
| starlette | 0.50.0 |
| uvicorn | 0.48.0 |
| SQLAlchemy | 2.0.50 |
| Jinja2 | 3.1.6 |
| python-multipart | 0.0.29 |
| argon2-cffi | 25.1.0 |
| alembic | 1.18.4 |
| psycopg | 3.3.6 |
| httpx | 0.28.1 |
| httpcore | 1.0.9 |
| certifi | 2026.2.25 |
| pytest | Unavailable locally |

`pip install -r requirements-dev.txt` failed: no available pytest distribution through this environment's configured network route. A direct PyPI metadata request also failed to connect to the configured proxy. No proxy/sandbox restrictions were bypassed. Existing cached wheel archives supplied httpx/httpcore/certifi via an offline `pip install --no-index --find-links .verification/offline-wheels httpx==0.28.1` (successful install). pytest was not in that cache.

The stdlib runner executes the original application test functions through real unittest cases and the same disposable fixture used by pytest. It is not a fake pytest implementation. Direct pytest execution and pytest-specific collection/configuration remain unverified locally until pytest is available.

## Artifact inventory

- Application, templates/static files, migrations, requirements, docs, and tests are source inputs.
- Existing `data/`, virtual environments, `.wheelhouse/`, `__pycache__/`, and `.tmp_*.json` files were observed by file listing only. Business database/document contents were not read, migrated, or edited.
- New `.verification/` contains synthetic scratch resources, local reports/logs, and recovered offline wheels. It is ignored for future version control and excluded from source fingerprints.
- `.gitignore` now also excludes `.verification/`, `.venv-no-pip/`, `.wheelhouse/`, and temporary package metadata. Existing caches/environments were not deleted.
- The first Windows test attempt exposed inaccessible ACLs on Python 3.14 TemporaryDirectory directories. Disposable verification now uses inherited workspace ACLs with generated names and guarded cleanup confined to `.verification/tmp`. The initial failed run had 18 setup errors; it was not counted as a successful regression run.
- Those first-attempt restricted-ACL scratch directories may require workspace-owner cleanup. Later generated directories are cleaned after each fixture. No broad cleanup or ACL changes were attempted.

## Commands and results

Run commands from the project root using the verified interpreter, or an equivalent environment with requirements installed.

```powershell
& 'C:\kämmerei\.venv\Scripts\python.exe' scripts\verify_phase1.py --database sqlite
& .\scripts\verify_phase1_postgres.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
```

| Verification | Outcome | Evidence |
|---|---|---|
| SQLite stdlib runner | Exit 0; 22 checks: 19 passed, 3 expected failures; zero errors/unexpected successes/skips | `.verification/phase1-sqlite.log`, `.verification/phase1-sqlite.json` |
| Original application checks | All 10 pass within the above runner | `tests/test_app.py`; source count corrects earlier handoff's estimate of 11 |
| Clean SQLite migration | Pass to actual Alembic head; repeat at head passes | `MigrationTests.test_clean_upgrade` |
| Populated SQLite migration | Pass from 0001, add synthetic document metadata at 0003, upgrade to head; preserve contract/version/revision/document fields | `MigrationTests.test_populated_initial_upgrade_preserves_records_and_document_metadata` |
| Isolated storage/permissions/API checks | Pass; second app cannot resolve first app's upload | `ResourceAndPermissionTests` |
| Production unsafe defaults/config refresh | Pass; no business connection | `ConfigurationTests` |
| PostgreSQL disposable bootstrap | Failed before test execution: `initdb: could not create restricted token: error code 87` | `.verification/phase1-postgresql.log` |
| PostgreSQL actual migrations/regression | Initial local attempt blocked; subsequently passed in authoritative Linux CI | U006; evidence/phase1-ci-39571113046.json |
| pytest direct command / hosted CI | Local pytest still unavailable; both direct pytest jobs passed on hosted Ubuntu | U006; SQLite/PostgreSQL job conclusions and JSON/JUnit artifact metadata |

### Confirmed expected failures

- **R01:** Department-A page contains department-B-only contract type.
- **R04:** Review update on an archived contract returns a successful redirect instead of 409.
- **R10:** Existing department-user session still gets protected page 200 after department deactivation.

Fixture preparation runs outside expectedFailure-marked assertion methods, so setup/migration/transport errors are reported as real errors. Unexpected success makes the verification runner fail. These three findings are reproduced, not remediated.

## Disposable PostgreSQL safety

`scripts/verify_phase1_postgres.ps1` initializes a separate loopback-only cluster in a generated workspace directory with random SCRAM credentials, chooses a temporary port, invokes verification, then stops and cleans only its own cluster. It does not connect to or alter the installed application service. Cluster bootstrap failed locally under the managed Windows token; no existing service was used as a fallback.

For an already provisioned disposable CI/local cluster, `TEST_POSTGRES_ADMIN_URL` must use `postgresql+psycopg`, loopback, and administrative database `postgres`. Test fixtures create `ohvr_test_<uuid>` databases, run migrations there, and drop only their generated names. The supplied administrative database is never migrated. Use a dedicated verification cluster/account with CREATE DATABASE rights; this does not demonstrate production least privilege or RLS.

## Phase status

P01-T01–T08 implementation artifacts are delivered and the technical verification gate is closed by successful Linux CI. Local SQLite passes with three recorded expected failures; hosted SQLite/PostgreSQL verification and direct pytest also pass. Phase 1 is **technically complete**, not production acceptance. D01–D13 remain unapproved, and production readiness is not established.

Next application remediation is Phase 2's permission matrix and metadata scope fix. Local Docker engine installation and repository branch protection remain host/account tasks. See [VERIFICATION_MATRIX.md](VERIFICATION_MATRIX.md) and [../HANDOFF.md](../HANDOFF.md).
