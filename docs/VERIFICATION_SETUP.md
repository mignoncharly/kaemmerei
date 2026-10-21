# Verification setup and publication

Updated: 2026-10-21. Target repository: https://github.com/mignoncharly/kaemmerei.

## Prepared automation

The project folder is the Git repository root. `.github/workflows/phase1-verification.yml` is therefore in the correct root location. Source, tests, and documentation are selected explicitly for commits; business databases, uploaded documents, environments, and verification scratch data are excluded.

Two commands cover the remaining local workflow:

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Complete-Phase1Setup.ps1 -Push
```

The setup script creates/reuses `.venv-test`, installs requirements using the host's approved network/package configuration, runs SQLite verification and pytest/JUnit, starts the dedicated Docker test service, runs PostgreSQL verification and pytest/JUnit, and pushes committed source to the specified origin only if every local check passes and the working tree is clean. It never stages arbitrary files or edits network/sandbox policy.

Use `-Python 'C:\path\to\python.exe'` if Python 3.14 is not available through `py`. Omit `-Push` for local verification only.

## Host prerequisites

- Python 3.14, Git, an approved package index or complete development wheelhouse, and authorized GitHub authentication.
- Docker Desktop installed and running with Linux containers. Official installation instructions: https://docs.docker.com/desktop/setup/install/windows-install/.
- The Docker service is dedicated to synthetic tests, bound only to `127.0.0.1:55432`. It does not modify the existing Windows PostgreSQL service.

Docker installation requires host access outside the workspace, and any installer terms must be handled by the user. The current managed session has no Docker executable, connected browser, or GitHub administrative connector. Direct shell remote/API reads fail through the configured proxy, but the authorized Git push succeeded. The source is published and both authoritative Linux CI jobs passed; local Docker installation and branch protection remain separate tasks.

## Dedicated PostgreSQL service

`compose.test.yml` uses PostgreSQL 18 and its `/var/lib/postgresql` volume convention. `scripts/Start-TestDatabase.ps1` generates bootstrap/test credentials in process memory, waits for service readiness, and creates or resets a restricted `ohvr_verify` account with LOGIN/CREATEDB and without superuser, role administration, replication, or BYPASSRLS privileges. Tests create/drop only their generated databases.

Run only the service provisioning step when dependencies are already installed:

```powershell
& .\scripts\Start-TestDatabase.ps1
.\.venv-test\Scripts\python.exe scripts\verify_phase1.py --database postgresql
.\.venv-test\Scripts\python.exe -m pytest -q --database postgresql --junitxml=.verification/postgresql-pytest.xml
```

The script refreshes this terminal process's `TEST_POSTGRES_ADMIN_URL`. Run it in each new terminal before PostgreSQL tests; credentials are not saved in source. The bootstrap superuser is used only to administer this dedicated test container, not by the test suite.

## Linux CI

On a successful push, the workflow runs SQLite and PostgreSQL jobs on Ubuntu, installs requirements, creates a restricted PostgreSQL test role, runs the stdlib verification runner and pytest, and uploads JSON/JUnit artifacts. CI uses synthetic disposable-service credentials only, with read-only repository permission and no production credentials.

Actual workflow runs are at https://github.com/mignoncharly/kaemmerei/actions. Both jobs must finish successfully. R01/R04/R10 remain explicit expected failures until fixed in their assigned phases. A passing foundation run is not production acceptance.

After the first successful CI run, require the `sqlite` and `postgresql` checks for main-branch pull requests through repository branch protection/rulesets if supported by the account plan. This account setting is separate from committing the workflow.

## Current evidence and next gate

See HANDOFF U006 and [CI evidence](evidence/phase1-ci-39571113046.json). Actual [run 39571113046](https://github.com/mignoncharly/kaemmerei/actions/runs/39571113046) passed both SQLite and PostgreSQL verification/pytest jobs for source commit d9e39e520495928355dfe02b198c56150bf82077. Phase 1 is technically verified. PowerShell syntax/preflight checks do not establish that the local Docker service was run; that local capability remains unverified. R01/R04/R10 remain open, and no production acceptance is implied.
