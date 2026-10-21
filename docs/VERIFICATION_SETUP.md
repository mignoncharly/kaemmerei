# Verification setup and publication

Updated: 2026-10-21. Target repository: https://github.com/mignoncharly/kaemmerei.

## Prepared automation

The project folder is the Git repository root. `.github/workflows/phase1-verification.yml` is therefore in the correct root location. Source, tests, and documentation are selected explicitly for commits; business databases, uploaded documents, environments, and verification scratch data are excluded.

Two commands cover the remaining local workflow:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Complete-Phase1Setup.ps1 -Push
```

The setup script creates/reuses `.venv-test`, installs requirements using the host's approved network/package configuration, runs SQLite verification and pytest/JUnit, starts a dedicated **native PostgreSQL** test instance, runs PostgreSQL verification and pytest/JUnit, and optionally pushes committed source to the specified origin after all checks pass and the working tree is clean. Docker is not required for local development. It never stages arbitrary files or edits network/sandbox policy.

Use `-Python 'C:\path\to\python.exe'` if Python 3.14 is not available through `py`. Omit `-Push` for local verification only.

## Host prerequisites

- Python 3.14, Git, an approved package index or complete development wheelhouse, and authorized GitHub authentication.
- Native PostgreSQL binaries. The detected Windows installation is `C:\Program Files\PostgreSQL\18\bin`; override with `-PostgresBin` if needed.
- The separate native instance is dedicated to synthetic tests and bound only to `127.0.0.1:55432`. It does not reuse or modify the existing Windows PostgreSQL service.

The current managed session cannot change the native storage folder's Windows ACL and previously could not initialize PostgreSQL's restricted token. The scripts fail before writing credentials when directory protection is denied. Run the prepared setup command once from a normal authorized PowerShell terminal; no Docker installation, Windows service registration, production credentials, or changes to sandbox policy are required. The source is published and authoritative Linux CI is working; repository branch protection remains an account-administration task.

## Dedicated PostgreSQL service

`scripts/Start-TestDatabase.ps1` defaults to Native and invokes the native manager using the installed binaries. It creates a persistent, marked cluster in ignored `.local-postgres/`, restricts that directory to its owner, initializes SCRAM authentication, disables Unix sockets, and starts a loopback-only background server. It does not register or restart a Windows service. If another process occupies port 55432, it refuses to stop or borrow that process.

The bootstrap account is used only to provision this dedicated cluster. The test account `ohvr_verify` has LOGIN/CREATEDB and explicitly lacks superuser, role administration, replication, and BYPASSRLS. Generated credentials are stored in separate owner-only ignored passfiles. The exported connection URL contains no password; `PGPASSFILE` points only to the test account's file. Tests create/drop only their randomly named databases.

The manager refuses unmarked/external storage, mismatched ports or binary major versions, and incomplete nonempty initialization. It preserves data on stop and never recursively deletes a cluster. Failed setup retains the non-secret ownership marker so authorized initialization can be retried; the temporary init-password input is removed after initdb returns.

Run only the service provisioning step when dependencies are already installed:

```powershell
& .\scripts\Start-TestDatabase.ps1 -Python '.\.venv-test\Scripts\python.exe'
.\.venv-test\Scripts\python.exe scripts\verify_phase1.py --database postgresql
.\.venv-test\Scripts\python.exe -m pytest -q --database postgresql --junitxml=.verification/postgresql-pytest.xml
```

Before `.venv-test` is created, the already tested interpreter can provision the native instance directly:

```powershell
& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
```

The script configures this terminal's `TEST_POSTGRES_ADMIN_URL` and `PGPASSFILE`. Run it in each new test terminal to select the connection. If a separate `PGPASSWORD` is set in your terminal, clear that test terminal's conflicting setting or use a fresh terminal so libpq uses the intended passfile. Do not print or commit either passfile.

Stop the native background server while preserving its data:

```powershell
& .\scripts\Stop-NativeTestDatabase.ps1 -Python '.\.venv-test\Scripts\python.exe'
```

The server is not installed as an auto-start Windows service. Start it again after a host reboot with Start-TestDatabase. Administrative service registration can be added separately by IT if needed.

## Optional alternatives

- `Complete-Phase1Setup.ps1 -DatabaseBackend Existing` uses an explicitly configured dedicated test endpoint; it does not guess which installed service to use. The fixture's loopback/admin-database guards still apply.
- `Complete-Phase1Setup.ps1 -DatabaseBackend Docker` retains the optional legacy Docker helper and compose.test.yml. Docker is not installed or required by the default workflow.
- `-PostgresBin` and `-PostgresPort` select native binaries/port. Reopening an existing marked cluster with a different port is rejected; use the same port for start/stop.

## Linux CI

The existing SQLite and PostgreSQL 18 service-container jobs stay in place on GitHub's runners; those containers do not require Docker on your PC. An additional native-postgresql job uses Ubuntu 24.04's installed PostgreSQL binaries without Docker to exercise the new manager, migrations, and pytest. It shuts down its own cluster through an exit trap. The native job's PostgreSQL version is whatever the runner image supplies (currently documented as 16); the separate PostgreSQL 18 job remains the target-major verification.

All jobs use synthetic isolated test resources, read-only repository permission, and no production credentials. JSON/JUnit artifacts are uploaded; native passfiles and data storage are not uploaded.

Actual workflow runs are at https://github.com/mignoncharly/kaemmerei/actions. All three jobs must finish successfully. R01/R04/R10 are now fixed and covered by passing regressions. PostgreSQL jobs run the full suite and an explicit PostgreSQL-only lifecycle selection; neither may fall back to SQLite. A passing foundation run is not production acceptance.

After the first successful CI run, require the `sqlite` and `postgresql` checks for main-branch pull requests through repository branch protection/rulesets if supported by the account plan. This account setting is separate from committing the workflow.

## Preserved Phase 2 evidence

Phase 2 source 9fde6c0 passed all three jobs in [run 39594698525](https://github.com/mignoncharly/kaemmerei/actions/runs/39594698525). Full local PostgreSQL: 66 passed; SQLite: 65 passed + one PostgreSQL-only skip, with 15 passing subtests each. See [Phase 2 report](PHASE2_AUTHORIZATION.md) and HANDOFF U010. Existing native startup infrastructure is preserved. Migration 0014 has been verified only in disposable test databases; business deployment remains separate. Next technical work is Phase 3 schema/roles/RLS, not cluster reinitialization.

### Preserved Phase 1 native setup evidence

See HANDOFF U009 and the current [acceptance report](PHASE1_BASELINE.md) for exact results and reproducible commands. Native PostgreSQL 18 is initialized and running on Windows; the operator confirmed startup returns control to PowerShell. The managed agent's launcher repeat stops at the ACL check; do not reinitialize or weaken permissions. The full application suite actually passed locally against PostgreSQL: 44 tests, no skips or expected failures, plus 15 passing subtests. Thirteen native-manager safety checks pass. Historical successful [run 39575414353](https://github.com/mignoncharly/kaemmerei/actions/runs/39575414353) and its [evidence](evidence/native-postgresql-ci-39575414353.json) are retained; U009 records the run for the new fixes. Production acceptance is not implied.

## Phase 3 restricted-role verification

The full PostgreSQL suite now includes actual web/integration/maintenance LOGIN roles.
The native marked cluster uses its existing private bootstrap passfile, validated by
the binary cluster identity check, to create only temporary generated roles. An
explicit external test endpoint additionally needs TEST_POSTGRES_BOOTSTRAP_URL on
the same dedicated loopback test cluster. Never use business-cluster credentials.
No secrets are printed or added to evidence. SQLite explicitly skips these tests.
See [Phase 3](PHASE3_DATABASE_SECURITY.md) for role grants, isolated cleanup, recovery
journals and reproduction commands. Operator/maintenance production URLs are not
test control URLs and must not be installed in web workers.
