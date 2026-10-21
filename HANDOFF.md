# Implementation handoff and current state

Last updated: 2026-10-21\
Project: OPEN.HERZ Vertragsregister\
Plan: [REMEDIATION PLAN PHASES.md](REMEDIATION%20PLAN%20PHASES.md)\
Current stage: Phase 1 local application acceptance passed against native PostgreSQL 18. R01/R04/R10 corrected; Windows launcher repeat in the agent is ACL-blocked, while normal-shell startup was confirmed by the operator. See U009 for current hosted evidence.\
Production readiness: Not established. No release or deployment approval is recorded here.

## 1. Start here

1. Read this file, the ten-phase plan, [README.md](README.md), and [docs/ARBEITSPLAN.md](docs/ARBEITSPLAN.md).
2. Inspect the actual working tree, applicable project instructions, environment, and migration head. Do not assume repository state matches the baseline review.
3. Select the next ready task from the phase tracker. Check dependencies and the decisions register in the plan.
4. Implement one coherent change, verify the affected behavior in an isolated environment, then update the current-state tables and append an update entry below.
5. Record unrun checks as **Not run**. Record failed checks and incomplete work plainly. Never mark a phase verified from code inspection alone.

Do not put credentials, full API tokens, password hashes, document contents, or personal contract records in this file or linked evidence.

## 2. Current state snapshot

| Item | Current state |
|---|---|
| Review baseline | Static source review dated 2026-10-20 |
| Documents reviewed | README and ARBEITSPLAN updated to distinguish prototype behavior, known defects, verification, and outstanding approvals |
| Application | FastAPI, SQLAlchemy, Jinja templates, local static CSS/JS |
| Database | SQLite development default; production configuration requires PostgreSQL/psycopg |
| Latest migration observed | `0013_integration_tokens` |
| Authorization | Application-level department checks; no database RLS policies observed |
| Existing safeguards | Argon2; hashed sessions/tokens; CSRF; escaped templates; protected document routes; contract edit version checks |
| Tests | 44 pytest items: PostgreSQL 44 passed, 0 failures/skips/xfails; SQLite 43 passed, 1 PostgreSQL-specific skip. Both have 15 passing subtests. PostgreSQL stdlib runner 22 passed. |
| PostgreSQL/migrations | Native Windows cluster running/authenticated; clean and populated migrations plus application lifecycle pass locally. Error 87 is historical. Agent launcher retry fails at ACL check; operator startup succeeded. Production grants/RLS unverified. |
| Business database/documents | Not inspected, migrated, or changed; verification used synthetic disposable databases and instance-specific scratch storage |
| Deployment | Not inspected; no deployment performed |
| Source commit/branch | main published to https://github.com/mignoncharly/kaemmerei.git; implementation 558c0451b346265675aaeb411cb6ce4971b31af5 passed all three jobs in run 39589726718; see U009 |
| Completed deliverables | Plan/handoff; Phase 1 harness, isolated storage/configuration, migration fixtures, stdlib runner, CI definitions, baseline/matrix docs, corrected German project status |
| Application remediation | Document storage now per app instance; migrations accept explicit test connections. Business authorization/workflow findings remain open |

## 3. Status definitions

| State | Meaning |
|---|---|
| Not started | No implementation work recorded |
| In progress | Work exists; implementation and/or required verification incomplete |
| Blocked | A specific missing dependency prevents the next required action; name it and its owner |
| Implemented, unverified | Code/document change exists, but required checks have not passed or have not run |
| Verified | Relevant checks passed with recorded evidence; deployment/acceptance may still be pending |
| Accepted / complete | All phase exit criteria met and required owner acceptance recorded |
| Deferred | Optional scope excluded with owner, rationale, and review date; never equivalent to fixed |
| Reopened | A previous completion claim is invalidated by a defect or new evidence |

Track task checkboxes in the plan as implementation progress. Use this file for verification, deployment, and acceptance state. Both must agree.

## 4. Phase tracker

| Phase | State | Implemented tasks | Verification | Owner | Next action |
|---|---|---|---|---|---|
| 1 — Baseline and verification | Verified / technically complete | P01-T01–T08 | SQLite, PostgreSQL 18 and native PostgreSQL Linux jobs pass, including direct pytest; local safety checks pass | Engineering: Codex; no production acceptance | Begin Phase 2 when authorized; first native Windows initialization and branch protection pending |
| 2 — Authorization and identities | Not started | None | Not run | Unassigned | Adopt capability matrix; then scope all derived queries |
| 3 — Schema, roles, RLS, audit | Not started | None | Not run | Unassigned | Inventory schema differences; design context/bootstrap |
| 4 — Workflow/archive/concurrency | Not started | None | Not run | Unassigned | Define material content revision and mutation protocol |
| 5 — Document lifecycle | Not started | None | Not run | Unassigned | Define storage states, quarantine, recovery, and retention |
| 6 — Integration synchronization | Not started | None | Not run | Unassigned | Specify versioned cursor/feed/scope-removal contract |
| 7 — Reports/dates/Excel | Not started | None | Not run | Unassigned | Agree finance/history/date/interchange semantics |
| 8 — Frontend and navigation | Not started | None | Not run | Unassigned | Repair CSP-compatible charts and form state |
| 9 — Operations and availability | Not started | None | Not run | Unassigned | Define ingress limits, workload, and deployment targets |
| 10 — Acceptance and release | Not started | None | Not run | Unassigned | Assign acceptance owners and release scope |

No phase is complete merely because this plan has been written.

## 5. Findings closure tracker

The plan contains the full finding descriptions and primary phase mapping. Split grouped rows when individual findings change status. Record closure evidence and the verifying update ID for each finding before release.

| Finding IDs | Baseline severity | State | Closure evidence / update |
|---|---|---|---|
| R01 — Metadata isolation | High | Corrected and verified | U009; scoped metadata plus indirect/API/document regressions |
| R02 — Reviewer/recipient permissions | High | Open | None |
| R03 — Approval version/activation integrity | High | Open | None |
| R04 — Archive mutation | High | Corrected and verified | U009; locked parent, 409 and persisted review/history checks |
| R05 — Incremental synchronization | High | Open | None |
| R06 — Historical financial population | High | Open | None |
| R07 — Availability controls | High | Open | None |
| R08 — Test foundation/coverage | High | Phase 1 foundation verified; later coverage remains open | U003/U006: original harness and PostgreSQL/pytest/CI gates pass; later feature/RLS/concurrency coverage remains assigned to target phases |
| R10 — Inactive department | Medium | Corrected and verified | U009; session/login/object permissions and scoped API tokens |
| R09, R11–R14 — RLS, concurrency, tax, audit, schema | Medium | Open | Original phase assignments retained |
| R15–R16 — Document trust/recovery | Medium | Open | None |
| R17–R20 — Financial/date correctness | Medium | Open | None |
| R21–R22 — Capacity/operations | Medium | Open | None |
| R23–R28 — Frontend correctness | Medium | Open | None |
| R29–R36 — Integration/lifecycle scope gaps | Scope decisions required | Open | None |
| R37–R41 — Maintainability/usability/token policy | Nice to fix/have | Backlog | None |

## 6. Decisions and dependencies

All D01–D13 decisions in the plan are initially **Proposed / unapproved**. No city policy or sign-off is inferred from the technical plan.

| Decision IDs | Owner to assign | Current state | Immediate effect |
|---|---|---|---|
| D01–D02 — Roles, assignment, delegation | Kämmerei, identity/security | Proposed defaults | Implement read-only reviewers and explicit grants; confirm final policy |
| D03 — RLS and database roles | DBA/security | Proposed default | Design restricted production roles and fail-closed policies |
| D04 — Approval/activation/material changes | Approval owners | Proposed default | Preserve legacy uncertainty; do not fabricate approval provenance |
| D05–D06 — Documents, scanning, retention | Operations, security, privacy/records | Proposed defaults | Quarantine new content; no automatic destructive disposal |
| D07 — API/token/event policy | Integration/security | Proposed default | Design scopes, rotation, removals, and resnapshot behavior |
| D08–D10 — Finance, dates, Excel | Finance/domain/product | Proposed defaults | Preserve unknowns and define report/interchange contracts |
| D11–D12 — Hosting, recovery, identity | IT operations/security | Undecided targets/provider | Production acceptance depends on measured targets and identity choice |
| D13 — Connectors and notifications | Product owner | Scope not accepted | Do not claim unimplemented connectors or delivery capabilities |

**Phase 1 verification gate:** Closed technically by successful Linux CI run 39571113046. PostgreSQL and direct pytest succeeded on the hosted runner. Local Windows initdb still fails with token error 87; local pytest is unavailable and Docker is absent, but these no longer block the authoritative Linux verification. Branch protection has not been configured because authenticated repository-administration access is unavailable here.

## 7. Verification and environment ledger

Append exact commands only after identifying the correct environment. Record date, configuration, exit code, and evidence path for each executed check. Do not copy secrets from command arguments or environment values.

| Check | Environment | Latest result | Evidence |
|---|---|---|---|
| Static source review | Workspace source | Completed; findings recorded in plan | Baseline review and R01–R41 |
| Documentation creation | Workspace Markdown | Created | U001 below |
| Documentation cross-reference/content review | Workspace Markdown | Current links resolve; eight Phase 1 task boxes implemented; acceptance gate explicitly open | U004; historical original plan validation in U002 |
| Python syntax/source snapshot | Workspace source | 31 Python files AST-parsed; 38 source/config inputs fingerprinted | U004; .verification/phase1-source-sha256.json |
| Existing application tests | Migrated disposable SQLite | 10/10 passed through unittest adapter | U003; .verification/phase1-sqlite.log |
| New regression tests | Migrated disposable SQLite | Final suite 22 checks: 19 passed, 3 expected failures (R01/R04/R10) | U003; .verification/phase1-sqlite.json |
| Clean Alembic upgrade | Disposable SQLite / PostgreSQL | Passed in hosted verification jobs; local SQLite also passed | U003/U006; docs/evidence/phase1-ci-39571113046.json |
| Populated baseline upgrade | Disposable SQLite / PostgreSQL | Passed in hosted verification jobs from populated 0001 through document seed at 0003 to head | U003/U006; MigrationTests and CI evidence |
| Direct pytest | Hosted Ubuntu, SQLite / PostgreSQL | Both commands succeeded; JUnit artifacts uploaded | U006; CI run 39571113046 and both verification artifacts |
| RLS/application-role isolation | PostgreSQL restricted roles | Not implemented / not run | None |
| Concurrent archive/review/task writes | PostgreSQL | Not run | None |
| File scan/recovery fault cases | Isolated document storage | Not implemented / not run | None |
| API synchronization replay/transfers | Synthetic integration consumer | Not implemented / not run | None |
| Financial reconciliation/date fixtures | Synthetic domain fixtures | Not implemented / not run | None |
| Browser/CSP/accessibility | Local disposable app | Not run | None |
| Load/resource limits | Agreed synthetic workload | Not run; targets unassigned | None |
| Consistent backup restore | Isolated recovery environment | Not run; RPO/RTO unassigned | None |
| Pilot/security/privacy acceptance | Named owners | Not performed | None |

## 8. Migration, deployment, and recovery ledger

| Update | Migration/configuration | Data impact | Applied where | Recovery evidence |
|---|---|---|---|---|
| U001 | None; Markdown files only | No application/business-data change | Workspace documentation | Remove/revise these two files if needed |
| U003 | No new schema migration; explicit connection runner and instance storage settings | Synthetic verification DBs/files only | Workspace source; no deployment | Revert Phase 1 source changes together; no business-data restore needed |

For future updates, record schema revisions, backfill counts, legacy exceptions, required application/config versions, deployment state, and tested recovery instructions. Never list a migration as applied solely because its file exists.

## 9. Immediate next work

1. Preserve the U009 acceptance evidence and verify the latest hosted result against its source SHA.
2. Continue the remaining Phase 2 capability/assignment/query-scope work. R01/R10 are closed ahead of that phase; Phase 2 overall is not complete. R04 is closed ahead of Phase 4.
3. Use the existing native cluster and Start-TestDatabase.ps1 from the normal authorized PowerShell. Do not reinitialize it. The managed agent still cannot set owner-only native-storage ACLs.
4. Repository owner/admin should require sqlite/postgresql/native-postgresql checks on main through branch protection/rulesets; this account setting remains unverified. Production/RLS/business acceptance remains separate.

The user authorized Phase 1 implementation and repository/CI setup on 2026-10-21. Technical artifacts and local/hosted database verification are delivered. Agent launcher permissions, branch-rule administration and production acceptance remain separately recorded.

## 10. Update history

Append entries chronologically with stable IDs (`U001`, `U002`, ...). Correct earlier mistakes with a new entry and update the current snapshot; do not erase failure history. Routine progress entries may group related tasks, but each completed task needs evidence or an explicit unverified state.

### U001 — 2026-10-20 — Remediation plan and initial handoff

- **Implementer:** Codex.
- **Scope:** Documentation planning only; no phase task marked implemented.
- **Changes:** Created `REMEDIATION PLAN PHASES.md` with ten ordered phases, R01–R41 coverage, task IDs, dependencies, verification gates, recovery guidance, and D01–D13 decisions. Created `HANDOFF.md` with baseline, phase/finding trackers, evidence ledger, migration ledger, next actions, and update format.
- **Files:** These two Markdown files in the project root.
- **Migration/data impact:** None. Application code, business data, existing migrations, README, and ARBEITSPLAN unchanged by U001.
- **Verification:** Initial document readback and structural/reference review pending at time of entry creation. Application tests, browser checks, migrations, deployment, and security testing not run.
- **Known limitations:** All source-review findings remain unresolved. Live deployment and PostgreSQL behavior are unverified. No named policy/acceptance owners assigned.
- **Decisions:** Proposed defaults are documented; none recorded as approved.
- **Deployment/recovery:** Documentation exists in workspace only; no deployment. Recovery is a documentation revision/removal.
- **Next action:** Complete documentation readback, then begin P01-T01 when remediation implementation is undertaken.

### U002 — 2026-10-20 — Documentation readback and consistency review

- **Implementer:** Codex.
- **Scope/state:** Documentation verification completed; all remediation phases remain Not started.
- **Verification:** Read back both files and checked phase headings, task-ID uniqueness, finding/decision coverage, and decoded relative link targets with PowerShell. Command exited 0. Results: exactly phases 1–10; 86 tasks; zero duplicate task IDs; no missing R01–R41 finding rows; no missing D01–D13 decision rows; no missing link targets.
- **Content review:** Confirmed that phases specify dependencies, implementation tasks, exit checks, recovery guidance, and handoff requirements. Confirmed that current-state tables do not claim code remediation or operational acceptance.
- **Changes:** Updated the verification ledger and appended this evidence entry.
- **Checks not run:** Application tests, browser checks, database migrations, live security checks, load checks, and restore rehearsal; this update concerns the requested planning documents only.
- **Migration/deployment/data impact:** None.
- **Remaining work:** All remediation findings remain open; policy decisions and accountable owners remain unassigned.
- **Next action:** P01-T01: establish the implementation baseline when remediation work begins.

### U003 — 2026-10-21 — Phase 1 implementation and local verification

- **Implementer:** Codex. **Tasks:** P01-T01–T08. **Findings:** R08 partially addressed; R37 boundaries defined; R01/R04/R10 reproduced and still open.
- **State:** Phase 1 Not started -> Implemented, partially verified. Phases 2–10 not started; no production acceptance.
- **Baseline:** Windows 11, CPython 3.14.3, source head 0013_integration_tokens. No Git repository/commit available. Usable Python is the parent workspace .venv; project-local .venv lacks runtime packages. Earlier count of 11 original tests corrected to the actual 10 source functions.
- **Changes:** Repaired redirect-ID parsing and archive-filter assertion. Added per-app document storage and explicit migration connections. Replaced create_all-based fixtures with real isolated migrations, synthetic identities, guarded random PostgreSQL DB creation, shared pytest/unittest support, migration/config/storage/permission checks, and strict known-defect cases. Added a standard runner, disposable Windows PostgreSQL launcher, and SQLite/PostgreSQL CI jobs. Published baseline, matrix, service boundaries, and revised German project status.
- **Files:** app/config.py, app/main.py, app/migrations.py, alembic/env.py; tests/support.py, conftest.py, test_app.py, test_phase1.py; scripts/verify_phase1.py, verify_phase1_postgres.ps1; pytest.ini; .github/workflows/phase1-verification.yml; .gitignore; docs/PHASE1_BASELINE.md, docs/VERIFICATION_MATRIX.md; README, ARBEITSPLAN, plan, HANDOFF, CHANGELOG.
- **Migration/data impact:** No new schema migration; existing revision files unchanged. Only generated synthetic SQLite databases migrated. Regular business DB/documents not read or changed. Alembic's supplied-connection path is separate from regular CLI configuration.
- **Dependency attempts:** requirements-dev install failed because pytest was unavailable through the configured network. Cached httpx/httpcore/certifi wheels installed offline successfully. pytest remains unavailable; no proxy/sandbox restrictions bypassed.
- **Verification:** `C:\kämmerei\.venv\Scripts\python.exe scripts\verify_phase1.py --database sqlite` -> final exit 0; 22 checks, 19 passed, 3 expected failures, 0 errors/skips/unexpected successes. Includes all 10 original application checks, clean/populated migration preservation, storage upload/preview/download/API isolation, token scopes, child permissions, and configuration/unsafe-test-target rejection.
- **Expected failures:** R01 private contract-type dropdown leak; R04 archived review decision accepted; R10 access retained after department deactivation. These are OPEN findings. Fixture preparation is outside marked assertion methods, so setup errors remain real errors.
- **Failed attempts:** First SQLite run failed on Python 3.14 private temporary-directory ACLs (18 setup errors); verification now uses inherited-ACL workspace scratch paths and guarded cleanup. PostgreSQL bootstrap failed before tests: initdb cannot create restricted token, error 87. No existing PostgreSQL service used as fallback.
- **Evidence:** docs/PHASE1_BASELINE.md, docs/VERIFICATION_MATRIX.md; local .verification/phase1-sqlite.log/.json and .verification/phase1-postgresql.log. Reports contain synthetic verification output and are ignored artifacts.
- **Not run:** Direct pytest/hosted CI; actual PostgreSQL migrations/regression; production-role RLS and later concurrency/load/browser/restore checks. CI files are definitions, not evidence of execution.
- **Decisions:** D01–D13 remain proposed/unapproved; no business policy adopted.
- **Deployment/recovery:** Workspace only, no deployment. Revert Phase 1 source/config changes together if needed; no business-data rollback required. First-attempt restricted-ACL synthetic scratch directories may need workspace-owner cleanup; no broad deletion or ACL changes attempted.
- **Next action:** Execute PostgreSQL/pytest verification in an allowed disposable environment and record evidence before Phase 1 acceptance. Phase 2 capability/scoping work is next application remediation.

### U004 — 2026-10-21 — Final source and handoff consistency review

- **Scope:** Phase 1 documentation/evidence readback; no additional business behavior changed.
- **Verification:** Parsed 31 Python files with the stdlib AST parser; fingerprinted 38 source/config inputs with SHA-256 in `.verification/phase1-source-sha256.json`; checked links in README, HANDOFF, plan, ARBEITSPLAN, baseline, and verification matrix with zero missing targets. Confirmed no `DOCUMENTS_DIR` global remains and all eight Phase 1 task checkboxes indicate implementation.
- **Consistency correction:** Updated the README result after the final fixture-safety test: 22 checks, 19 passed, 3 known expected failures. The final runner report/log already reflect those figures.
- **State:** Phase 1 remains implemented and partially verified. PostgreSQL/pytest/hosted CI evidence remains outstanding; all application security findings outside the Phase 1 foundation remain open.
- **Next action:** Obtain permitted PostgreSQL and pytest execution evidence before accepting the Phase 1 exit gate. No deployment or business-data migration performed.

### U005 — 2026-10-21 — Repository initialization and automated host setup

- **Authorization:** User asked the agent to carry out the repository/CI/local-service setup rather than delegate all steps manually.
- **Changes:** Initialized project-root Git repository on main and configured the explicitly supplied origin. Added compose.test.yml, scripts/Start-TestDatabase.ps1, scripts/Complete-Phase1Setup.ps1, and docs/VERIFICATION_SETUP.md. Added .venv-test/.env.test exclusions. Updated Linux CI with JUnit artifact upload, read-only repository permissions, concurrency cancellation, and a restricted LOGIN/CREATEDB PostgreSQL test role.
- **Scope:** Setup/verification infrastructure only; no business schema, database, document, or permission workflow changed. R01/R04/R10 remain expected failures; Phase 1 not fully accepted.
- **Checks executed:** Both new PowerShell scripts parsed successfully. Actual missing-Docker preflight failed with the intended prerequisite message. Reviewed explicit source staging candidates for credential/private-key patterns; observed generated credentials and synthetic test values, no known real credentials. Real Docker orchestration, direct pytest, and Linux CI not executed.
- **Access findings:** Git is available; GitHub CLI and Docker are absent. No connected browser or GitHub connector is available. Shell `git ls-remote` fails connecting to github.com via configured proxy 127.0.0.1. No credentials were requested, exposed, or added to the repository; proxy/sandbox restrictions were not bypassed.
- **Remaining host prerequisite:** Install/start Docker Desktop with Linux containers in an authorized host session and provide working package/GitHub network/authentication access. Then the prepared setup command can run all local checks and push reviewed commits.
- **Next action:** Commit the reviewed source, attempt the authorized push, and record the actual result in U006. Hosted workflow/branch protection still require reachable authenticated GitHub access.

### U006 — 2026-10-21 — Publication and successful authoritative Linux CI

- **Source:** Committed the reviewed 62-file project as d9e39e520495928355dfe02b198c56150bf82077 with explicit Codex attribution. Published main to the user-specified GitHub repository; `git push -u origin main` exited 0. No business database, uploads, virtual environments, or real credentials were committed.
- **Access correction:** Earlier `git ls-remote` and direct API curl requests failed through the configured proxy, but the authorized git push command succeeded using available Git authentication. U005's remote-read failure remains historical evidence, not a claim that publication is still blocked.
- **Actual run:** https://github.com/mignoncharly/kaemmerei/actions/runs/39571113046, status completed / conclusion success, source SHA d9e39e520495928355dfe02b198c56150bf82077, completed 2026-10-21T08:41:52Z.
- **Verified jobs:** sqlite (119125229357) and postgresql (119125228881), both completed successfully. Each installed requirements-dev, ran scripts/verify_phase1.py against its backend, ran direct pytest, and uploaded artifacts. PostgreSQL container initialization and restricted test-role creation also succeeded.
- **Artifacts:** sqlite-verification (12331364024) and postgresql-verification (12332072377), both present and unexpired at inspection. Artifact archives were not downloaded/parsed locally; GitHub API confirms successful upload and existence.
- **Evidence:** docs/evidence/phase1-ci-39571113046.json records the actual run, jobs, step conclusions, source commit, and artifact metadata from GitHub's public REST API retrieved through the connected read tool.
- **Phase state:** Phase 1 -> Verified / technically complete. No production acceptance; phases 2–10 not started. R01/R04/R10 remain expected failures. R08 later-feature coverage remains open in the assigned phases.
- **Remaining limitations:** Docker engine installation requires host access outside this managed workspace; no Docker executable or connected desktop/browser is available. Local Compose execution remains unverified. No authenticated GitHub administrative API/browser capability is available to apply branch protection. Linux CI is now the working authoritative alternative to the blocked Windows bootstrap.
- **Next action:** Publish this evidence update. Begin Phase 2 only when authorized; local Docker setup and repository-owner branch rules can be completed independently.

### U007 — 2026-10-21 — Native PostgreSQL as the local default

- **Authorization:** User selected native PostgreSQL instead of mandatory local Docker and instructed implementation.
- **Changes:** Added scripts/native_test_database.py and native start/stop PowerShell wrappers. Start-TestDatabase and Complete-Phase1Setup now default to Native, support explicit Existing endpoints, and retain Docker only as an optional backend. Added .local-postgres to ignores and moved the previous Docker launcher to Start-DockerTestDatabase.ps1. Updated local setup/README guidance.
- **Isolation/security:** Dedicated marked cluster under .local-postgres, loopback port 55432, SCRAM, no Unix sockets, separate bootstrap/test passfiles, restricted LOGIN/CREATEDB test identity, no password in connection metadata. No adoption of unmarked storage, no business-service reuse, no cluster deletion or Windows service registration, no bypass of token/ACL checks. Owner-only storage protection is required before any credential is written.
- **Existing service:** postgresql-x64-18 is running. CIM/registry service configuration was unavailable to this session; its contents were not inspected and no test connection was made to it.
- **Local verification:** Ten native-manager safety unit checks passed; all five setup/launcher PowerShell scripts parsed successfully. Actual native Windows startup failed at icacls directory protection (exit 5), before credentials were written or initdb called. No existing PostgreSQL service changed. The safe non-secret marker allows retry from the authorized host terminal.
- **CI:** Existing authoritative SQLite/PostgreSQL 18 jobs retained. Added a native-postgresql Ubuntu 24.04 job using the runner's installed PostgreSQL binaries (runner currently documents version 16), testing native startup, migrated application checks, direct pytest, and shutdown without Docker. Target-major PostgreSQL 18 coverage remains in the original service-container job. Actual run evidence will be appended after push.
- **State:** Native implementation delivered; real Windows startup remains host-blocked. Phase 1's previously verified technical gate is preserved; no production acceptance and R01/R04/R10 remain open.
- **Next action:** Publish source and inspect all three actual CI jobs. First local initialization is one prepared command in a normal authorized PowerShell; no Docker installation is required.

### U008 — 2026-10-21 — Native PostgreSQL end-to-end CI passed

- **Source/run:** b45b26d131e72df91d4e4f5b8a804541611ee2b1; https://github.com/mignoncharly/kaemmerei/actions/runs/39575414353, completed / success.
- **Actual jobs:** native-postgresql (119139604720), sqlite (119139604849), and postgresql (119139604985), all success. The native job initialized the marked native cluster without Docker, provisioned the restricted account/passfiles, ran migrated application verification and direct pytest, and stopped its own server through the exit trap. The original PostgreSQL 18 job also remained green.
- **Evidence:** docs/evidence/native-postgresql-ci-39575414353.json records final run/job/step conclusions and verification artifact metadata. Native, SQLite, and PostgreSQL artifact uploads succeeded; archives were not downloaded/parsed locally.
- **Local checks:** Ten native-manager safety checks and all five PowerShell launcher syntax checks passed. Actual Windows first startup is still blocked by managed-session ACL permissions before credentials are written; no existing Windows service changed.
- **State:** Native implementation is verified end-to-end on Linux CI and is the default local setup. Docker is optional on the PC. Windows first startup is a host-specific outstanding action, not an unrun PostgreSQL/pytest foundation gate. R01/R04/R10 and later remediation findings remain open; no production acceptance.

### U009 — 2026-10-21 — Phase 1 real PostgreSQL acceptance and security fixes

- **Scope:** User explicitly requested acceptance completion and fixes for R01/R04/R10. Existing working infrastructure and historical entries retained. Original migration head remains `0013_integration_tokens`; no business database migration, schema replacement, cluster deletion, unrelated service stop or deployment.
- **Initial state:** `main` at a434648; operator edits existed in native manager and a whitespace-only Start-TestDatabase change. Operator startup pipe/log and binary cluster identity fixes were preserved and included in implementation 558c045. The unrelated whitespace edit remains unstaged and untouched.
- **R01:** Department-scoped stored filter choices; expanded tests exercise searches, report/export, details, private document metadata/bytes, API scope and mismatched parent references. **R04:** PostgreSQL parent lock, server-side archived guard/409 and hidden review controls; persisted review fields and audit IDs unchanged after rejected admin/reviewer decisions. **R10:** Shared active-membership guard for login/session/object access and inactive-department scoped token rejection. Explicit global roles retain their existing authority.
- **Safety:** Fresh randomly named PostgreSQL database per fixture, dedicated restricted role, OID/owner/comment checks before migrations and deletion, clean-schema check, and fail-closed replacement/default-database safety tests. Native live lock/binary identity/no-PIPE regressions added. No weakening of permissions or locking. Launcher no longer labels all errors as token error 87.
- **Local verification:** 44 pytest items collected. Default SQLite: 43 passed, one explicit PostgreSQL-only skip, zero failures/xfails; PostgreSQL: 44 passed, zero failures/skips/xfails. Both have 15 passing subtests. Explicit PostgreSQL lifecycle: one passed, no skips. PostgreSQL stdlib runner: 22 passed. Clean/populated/repeated migrations pass. Final read-only catalog check: zero harness databases remain.
- **Windows evidence:** Existing cluster on 127.0.0.1:55432 authenticated as ohvr_verify without printing credentials. Operator previously confirmed nonblocking normal PowerShell startup. This agent's independent launcher repeat stopped at the owner-only ACL boundary before initdb or restart; error 87 was not reproduced. Startup is not independently reverified from this managed shell.
- **Hosted verification:** Push to the already configured/authorized main branch triggered [run 39589726718](https://github.com/mignoncharly/kaemmerei/actions/runs/39589726718), source `558c0451b346265675aaeb411cb6ce4971b31af5`. All three jobs succeeded: sqlite, PostgreSQL 18 service and native-postgresql. Dependency installation, full pytest/migrations/security regressions, and explicit PostgreSQL-only lifecycle selection succeeded. API run/job/step and artifact metadata inspected directly; artifact contents were not downloaded.
- **Evidence/report:** [Current acceptance report](docs/PHASE1_BASELINE.md), [local summary](docs/evidence/phase1-acceptance-local.json), [hosted summary](docs/evidence/phase1-acceptance-ci-39589726718.json); ignored local JUnit XML and stdlib JSON retained. README, ARBEITSPLAN, plan, matrix and setup documentation updated. Previous implementation history preserved.
- **Warnings/boundaries:** Starlette/AnyIO deprecation and managed Windows pytest-cache ACL warning remain; no warning suppression. Broad concurrency, database RLS, approver assignment/content binding, production grants/backup/recovery and remaining phase findings are not accepted by these checks. Branch protection remains an account task. Local application/database and hosted technical gates pass; independent agent Windows launcher repeat remains ACL-limited. No production acceptance.
- **Host command:** From normal authorized PowerShell in the project root, run `& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'` for the first native initialization. For full dependency/local-test setup, use Complete-Phase1Setup.ps1. No database password is requested or printed by either script.
- **Next action:** Publish the evidence update; start Phase 2 only when authorized. Repository branch protection remains an owner/admin account setting.

### Update entry template — copy for the next update

```markdown
### U___ — YYYY-MM-DD — Short description

- Implementer / accountable owner:
- Phase and task IDs:
- Finding IDs:
- State before -> state after:
- Behavior changed and reason:
- Files / source revision:
- Migration, backfill, and configuration changes:
- Business-data / legacy-state impact:
- Verification commands and environment:
- Actual outcomes / exit codes / evidence paths:
- Checks not run and why:
- Remaining defects, risks, or blockers:
- Decisions adopted / pending (D IDs, owner, date):
- Deployment state:
- Recovery / rollback implications:
- Next exact action and owner:
```

## 11. Release checklist

- [ ] Phase trackers and plan task checkboxes agree.
- [ ] Every Critical/High finding closed with verification evidence.
- [ ] Medium risks resolved or accepted by named owners with expiry/review dates.
- [ ] Scope gaps explicitly included and delivered, or excluded with accepted manual procedures.
- [ ] PostgreSQL migrations, restricted roles, RLS, and pooled identity isolation verified.
- [ ] Workflow, archive, concurrency, document integrity, synchronization, and reports verified.
- [ ] Deployment protections, monitoring, maintenance, and restore rehearsal verified.
- [ ] Required privacy/domain/security/operations acceptance recorded.
- [ ] README, ARBEITSPLAN, CHANGELOG, API/operator documentation match actual behavior.
- [ ] Release version, deployment state, residual backlog, ownership, and next maintenance date recorded.
