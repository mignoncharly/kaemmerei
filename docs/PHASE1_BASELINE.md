# Phase 1 baseline and verification evidence

Recorded: 2026-10-21. Implementer: Codex. Scope: P01-T01–T08 technical foundation.

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
