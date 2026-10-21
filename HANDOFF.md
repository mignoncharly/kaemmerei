# Implementation handoff and current state

Last updated: 2026-10-21\
Project: OPEN.HERZ Vertragsregister\
Plan: [REMEDIATION PLAN PHASES.md](REMEDIATION%20PLAN%20PHASES.md)\
Current stage: Phase 9 in progress (U021). Bounded ingress/shared throttling/synchronous handlers implemented; operations, job scheduling, workload, recovery and identity/deployment gates remain open. See docs/PHASE9_OPERATIONS.md.\
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
| Latest migration observed | `0023_human_mfa`; encrypted owner-only credentials, challenge sessions and deliberate rollout policy, tested only in disposable databases. Rerun reviewed runtime-role configuration after migrations. No business migration. |
| Authorization | Shared application guards plus forced PostgreSQL RLS under separate actual web/integration LOGIN roles; SQLite remains application authorization only |
| Existing safeguards | Argon2; hashed sessions/tokens; CSRF; escaped templates; protected document routes; contract edit version checks |
| Tests | U020: 262 collected; native PostgreSQL 260 passed/2 local skips; SQLite 236/26 explicit skips; 15 passing subtests each. Explicit PG 24 passed, backup/Windows 29 passed. All 17 backup cases executed on PG. Zero failures/errors/xfails. |
| PostgreSQL/migrations | Native Windows 18.3; head 0023_human_mfa clean/populated/repeated upgrades, actual restricted roles and real database/document/MFA restores passed in synthetic disposable databases. Final read-only catalog 0 guarded DBs/0 generated roles; control privileges unchanged. No business migration/grants or cluster change. |
| Business database/documents | Not inspected, migrated, or changed; verification used synthetic disposable databases and instance-specific scratch storage |
| Deployment | Not inspected; no deployment performed |
| Source commit/branch | main; frozen application source 92329b6f181f174f0212c429e3368383bcc027dc committed/pushed. Exact-source CI run 39660619585 passed all five jobs, including required actual encrypted recovery. Documentation/evidence follow-up separate. |
| Completed deliverables | Phases 1-8 technical implementations/tests/evidence; HTML/browser/navigation contracts included. Owner, usability and production acceptance remain separate. |
| Application remediation | Phases 1-8 technically verified. P07-T01 finance agreement, availability/deployment/operations, remaining adapters and owner/usability acceptance remain open. |

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
| 1 — Baseline and verification | Verified / technically complete | P01-T01–T08 | Preserved; native Windows application/identity probes and hosted checks pass; independent agent launcher retry is ACL-limited | Engineering: Codex; no production acceptance | Preserve U009 evidence |
| 2 — Authorization and identities | Verified technically; owner acceptance pending | P02-T01–T08 | 66 PostgreSQL passed; 65 SQLite passed + one PostgreSQL-only skip; hosted three jobs passed for 9fde6c0 | Engineering: Codex; municipal owners unassigned | Next technical phase: P03-T01; municipal D01/D02 acceptance required before production |
| 3 — Schema, roles, RLS, audit | Verified technically; DBA/security acceptance pending | P03-T01–T08 | PostgreSQL 81 passed; SQLite 69 passed + 12 PG-only skips; explicit PostgreSQL 12 passed; all three hosted jobs passed | Engineering: Codex; DBA/security owner unassigned | Next technical phase P04-T01; review D03 before business deployment |
| 4 — Workflow/archive/concurrency | Verified technically; D04 owner acceptance pending | P04-T01–T08 | PostgreSQL 99 passed; SQLite 87 passed + 12 PG skips; Phase 4 actual restricted-login selection 18 passed; all three CI jobs passed | Engineering: Codex; municipal approval owners unassigned | Next technical phase P05-T01; D04 adoption before business deployment |
| 5 - Document lifecycle | Verified technically; D05/D06 owner acceptance pending | P05-T01-T08 | PostgreSQL 128 passed + 2 local skips; SQLite 116 + 14; real PG restore; successful hosted run including required real ClamAV | Engineering: Codex; security/records owners unassigned | Next technical phase P06-T01; production setup and owner decisions pending |
| 6 - Integration synchronization | Verified technically; D07 owner acceptance pending | P06-T01-T08 | PG 149 + 2 local skips; SQLite 134 + 17; 21 actual PG integration regressions; all four CI jobs passed | Engineering: Codex; integration/security owners unassigned | Next P07-T01; D07 consumer profiles/transition and retention before production |
| 7 - Reports/dates/Excel | Verified technically; D08-D10 unapproved | P07-T02-T09 technical defaults; T01 owner agreement pending | PG 168 + 2 local skips; SQLite 152 + 18; Phase 7 PG 19; explicit PG 16; four hosted jobs passed | Engineering: Codex; municipal owners unassigned | Next technical phase P08-T01; obtain D08-D10 before business deployment |
| 8 - Frontend and navigation | Verified technically; manual usability/AT and production acceptance pending | P08-T01-T09 | PG 176 + 2 local skips; SQLite 160 + 18; Phase 8 eight on both; real browser and all five hosted jobs passed | Engineering: Codex; usability owner unassigned | Next P09-T01; establish operational targets and release acceptance owners |
| 9 - Operations and availability | In progress; no exit acceptance | Partial P09-T01-T04, T07-T08; dashboard-only reminder limit documented | U017; 21 Phase 9 checks on each backend, full PG 197 passed + 2 skips, five hosted jobs passed | Engineering: Codex; operations/identity owners unassigned | Complete T03/T05 scheduling/queues and T04 representative workload; implement approved D12 TOTP/recovery; encrypted recovery, alert ownership and release gates |
| 10 — Acceptance and release | Not started | None | Not run | Unassigned | Assign acceptance owners and release scope |

No phase is complete merely because this plan has been written.

## 5. Findings closure tracker

The plan contains the full finding descriptions and primary phase mapping. Split grouped rows when individual findings change status. Record closure evidence and the verifying update ID for each finding before release.

| Finding IDs | Baseline severity | State | Closure evidence / update |
|---|---|---|---|
| R01 — Metadata isolation | High | Corrected and verified | U009; scoped metadata plus indirect/API/document regressions |
| R02 — Reviewer/recipient permissions | High | Explicit assignment plus independent approval implemented and locally verified | U010/U012; wrong recipient/self-approval denied |
| R03 — Approval version/activation integrity | High | Implemented and locally verified; municipal D04 acceptance pending | U012; decisions bind content; stale approvals cannot activate new content |
| R04 — Archive mutation | High | Corrected and verified | U009; locked parent, 409 and persisted review/history checks |
| R05 - Incremental synchronization | High | Reliable v2 implemented and technically verified; v1 consumer transition remains D07 work | U014; late commits, fixed snapshot/history, minimal removal, restart and replay |
| R06 - Historical financial population | High | Corrected and technically verified; D08 adoption pending | U015; actual archive/transfer ledger under restricted roles, independent historical population |
| R07 - Availability controls | High | Partially implemented; remains open | U017: ingress/shared budgets/workers; deployment/load/job/monitoring gates remain |
| R08 — Test foundation/coverage | High | Phase 1 foundation verified; later coverage remains open | U003/U006: original harness and PostgreSQL/pytest/CI gates pass; later feature/RLS/concurrency coverage remains assigned to target phases |
| R10 — Inactive department | Medium | Corrected and verified | U009; session/login/object permissions and scoped API tokens |
| R09, R13, R14 — RLS, audit, schema | Medium | Phase 3 implemented and locally verified; production acceptance pending | U011; restricted-role SQL, audit protection and schema regressions |
| R11, R12 — Concurrency and tax | Medium | Implemented and locally verified | U012; expected child versions, concurrent/archive races, restricted tax completion and cleared reopen metadata |
| R15/R16 - Document trust/recovery | Medium | Corrected and technically verified; D05 production policy pending | U013; real restore, recovery, integrity/authorization and hosted actual scanner |
| R17-R20 - Financial/date correctness | Medium | Corrected and technically verified; D08/D09 adoption pending | U015; unknown basis/direction/missing counts and anchored bounded calendar regressions |
| R21 - Loading/export/truncation | Medium | Pagination and row/byte/cooperative completion bounds implemented; scoped population optimization and workload acceptance remain | U016/U017; no production capacity claim |
| R22 - Operations | Medium | Partial TLS/proxy/health/correlation controls; scheduled jobs/recovery/alerts/deployment remain open | U017; Phase 9/10 |
| R23-R28 - Frontend correctness | Medium | Corrected and technically verified | U016; final local suites, eight restricted-role/frontend regressions and hosted Chromium gate |
| R31 — Contact/deputy identities | Scope gap | Maintained scoped catalog delivered; labels grant no access | U010; no implicit delegation; delegation requires a separate accepted policy |
| R32 — Department lifecycle | Scope gap | Audited administration delivered | U010; rename/suspend/reactivate, stable IDs, session revocation and token suspension |
| R34 — Account recovery/password/MFA | Scope gap | Password change and audited recovery delivered; MFA/SSO remains Phase 9 | U010; temporary passwords force replacement; session/CSRF rotation and rate limiting |
| R29-R30 - Integration/reminder scope | Scope decisions required | Open | Original phase assignments |
| R35 - Excel identity/update semantics | Scope gap | Explicit create-only identity technically verified; D10 adoption pending | U015; generated-number rejection, scoped references, atomic concurrent import and provenance |
| R37/R40 - Maintainability/distribution | Nice to fix/have | Remaining backlog | Original phase assignments; shared list/export filter specification delivered U016 |
| R42 - Newly reviewed dependency advisories | High (identified U017) | Reviewed affected ranges corrected: FastAPI 0.158.0 / Starlette 1.9.0 / multipart 0.0.32 adopted; current runtime OSV query zero matches | U017; five exact-source hosted jobs passed for 1649b15; wider tool/OS/release checks remain P09-T11 |
| R38 - Navigation/order/inbox | Nice to fix/have | Implemented and technically verified | U016; stable paging, filter-preserving links, scoped actionable inbox; manual usability acceptance pending |
| R39 - Document correction/supersession | Nice to fix/have | Implemented and technically verified | U013; retained predecessors, DMS correction, approval invalidation and hold preservation |
| R33 - Retention/disposal | Scope gap | Design and non-destructive hold defaults implemented; D06 pending | U013; no destructive disposal |
| R36 - API field coverage | Scope gap | Explicit v2 tax/task/decision/history fields technically verified; D07 pending | U014; no expansion of existing v1 tokens |
| R41 - Token ownership/rotation | Nice to fix/have | Implemented and technically verified; D07 policy adoption pending | U014; explicit owner/expiry/profile/rotation/revoke audit |

## 6. Decisions and dependencies

All D01–D13 decisions in the plan are initially **Proposed / unapproved**. No city policy or sign-off is inferred from the technical plan.

| Decision IDs | Owner to assign | Current state | Immediate effect |
|---|---|---|---|
| D01–D02 — Roles, assignment, delegation | Kämmerei, identity/security | Proposed defaults | Implement read-only reviewers and explicit grants; confirm final policy |
| D03 — RLS and database roles | DBA/security | Technical default implemented/tested; owner acceptance pending | Separate owner/web/integration/maintenance/audit identities; shared-role GUC threat boundary documented |
| D04 — Approval/activation/material changes | Approval owners | Pilot default implemented/tested; municipal acceptance pending | Configured current independent approvals; legacy unverified; no activation override |
| D05–D06 — Documents, scanning, retention | Operations, security, privacy/records | Proposed defaults | Quarantine new content; no automatic destructive disposal |
| D07 — API/token/event policy | Integration/security | Proposed default | Design scopes, rotation, removals, and resnapshot behavior |
| D08–D10 — Finance, dates, Excel | Finance/domain/product | Proposed defaults | Preserve unknowns and define report/interchange contracts |
| D11–D12 — Hosting, recovery, identity | IT operations/security | Undecided targets/provider | Production acceptance depends on measured targets and identity choice |
| D13 — Connectors and notifications | Product owner | Scope not accepted | Do not claim unimplemented connectors or delivery capabilities |

**Verification gates:** Phase 1 local application/database and hosted technical gates passed (U009). Windows error 87 and unavailable pytest are historical, not current blockers. Phase 2 P02-T01–T08 now has passing local SQLite/PostgreSQL gates (U010); hosted results are recorded against the implementation SHA. D01/D02 defaults are implemented technically, not municipally approved. Branch protection remains an unverified repository-account setting.

## 7. Verification and environment ledger

Append exact commands only after identifying the correct environment. Record date, configuration, exit code, and evidence path for each executed check. Do not copy secrets from command arguments or environment values.

| Check | Environment | Latest result | Evidence |
|---|---|---|---|
| Static source review | Workspace source | Completed; findings recorded in plan | Baseline review and R01–R41 |
| Documentation creation | Workspace Markdown | Created | U001 below |
| Documentation cross-reference/content review | Workspace Markdown | Phase 1 and Phase 2 implementation tracked separately; policy/release acceptance explicitly open | U010; historical U002/U004 preserved |
| Python syntax/source snapshot | Workspace source | 31 Python files AST-parsed; 38 source/config inputs fingerprinted | U004; .verification/phase1-source-sha256.json |
| Existing application tests | Migrated disposable SQLite | 10/10 passed through unittest adapter | U003; .verification/phase1-sqlite.log |
| New regression tests | Disposable SQLite / restricted native PostgreSQL | Full PG 176 + 2 local skips; SQLite 160 + 18; Phase 8 8/8 both; no failures/errors/xfails; 15 subtests each full suite | U016; docs/evidence/phase8-local.json |
| Clean Alembic upgrade | Disposable SQLite / PostgreSQL | Head 0020, schema equality and repeated clean/populated upgrades pass | U015; full suites and migration/schema regressions |
| Populated baseline upgrade | Disposable SQLite / PostgreSQL | Original fixtures plus invalid legacy abort, reviewed synthetic correction and historical audit outcome preservation pass | U010/U011; MigrationTests, tests/test_phase2.py, tests/test_phase3_schema.py |
| Direct pytest | Windows SQLite/native PostgreSQL | Final source 6ebcaad: full suites pass; explicit PostgreSQL 16 passed, 162 deselected; five hosted jobs pass | U016; exact JUnit hashes and hosted evidence |
| RLS/application-role isolation | Actual separate PostgreSQL LOGIN roles | 11 Phase 3 tests passed; explicit selection also includes application lifecycle | U011; tests/test_phase3.py |
| Concurrent archive/review/task writes | SQLite and actual restricted PostgreSQL logins | One winning decision/task update; nine paths race archive and reject every post-barrier mutation | U012; tests/test_phase4.py |
| File scan/recovery fault cases | Isolated document storage / hosted actual ClamAV | Passed; two local capability skips documented; hosted scanner succeeds | U013/U015; full suites and hosted job evidence |
| API synchronization replay/transfers | Synthetic consumers and actual restricted PG logins | Phase 6 regression preserved in final full local/hosted suites | U014/U015 |
| Financial reconciliation/date fixtures | SQLite / actual restricted PostgreSQL roles | Phase 7 final PG 19 passed; SQLite 18 + one PG-only skip; full suites and hosted passed | U015; tests/test_phase7.py; docs/evidence/phase7-local.json |
| Browser/CSP/accessibility | Hosted real Chromium / synthetic app | CSP widths, keyboard/focus, persistent errors, checkbox recovery, 390/320 reflow pass. Selected palette contrast pass. Local browser blocked by WinError 5; manual AT/WCAG/usability unverified | U016; docs/evidence/phase8-ci-39635885108.json |
| Load/resource limits | Agreed synthetic workload | Not run; targets unassigned | None |
| Consistent backup restore | Isolated synthetic recovery environment | Actual PG dump/restore and restored authorization/hash tests pass; operational RPO/RTO acceptance remains open | U013/U015 |
| Pilot/security/privacy acceptance | Named owners | Not performed | None |

## 8. Migration, deployment, and recovery ledger

| Update | Migration/configuration | Data impact | Applied where | Recovery evidence |
|---|---|---|---|---|
| U001 | None; Markdown files only | No application/business-data change | Workspace documentation | Remove/revise these two files if needed |
| U003 | No new schema migration; explicit connection runner and instance storage settings | Synthetic verification DBs/files only | Workspace source; no deployment | Revert Phase 1 source changes together; no business-data restore needed |
| U010 | Forward migration 0014: approval flags, identity audit/guard, scoped contacts, teams/memberships, review assignment | Existing labels/IDs/passwords preserved; no automatic approvers or assignments | Synthetic isolated SQLite/PostgreSQL only; no business deployment | Forward repair or compatible verified backup; automatic destructive downgrade refused; never restore broad reviewer approval |
| U011 | Forward 0015/0016, restricted role registry/grants, FORCE RLS, protected audit and transaction context | Inventory blocks invalid rows; no silent repair; historical unknown correlation retained | Synthetic isolated SQLite/PostgreSQL and generated runtime roles only | Abort/rollback invalid upgrade verified; compatible app/schema restore or reviewed forward repair; never disable RLS |

For future updates, record schema revisions, backfill counts, legacy exceptions, required application/config versions, deployment state, and tested recovery instructions. Never list a migration as applied solely because its file exists.

## 9. Immediate next work

1. Preserve U009/U010 evidence and match every hosted result to its implementation SHA.
2. Next technical phase: P07-T01 finance/history/date/Excel definitions. Preserve proven v2 publication/snapshot/scope contracts and earlier RLS/workflow/document safeguards.
3. Review D01-D07 and upcoming D08-D10 with municipal identity/security/integration/records/finance owners before production; implementation defaults do not establish adopted policy.
4. Use the existing native cluster; do not reinitialize it. Branch protection, production backup/restore and deployment approval remain separate account/operations work. No business database has been migrated by this update.

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
- **Windows evidence:** Existing cluster on 127.0.0.1:55432 authenticated as ohvr_verify without printing credentials. Read-only probes confirmed PostgreSQL 18.3/UTF8 and live binary cluster identity matching local marked storage; the identity probe used the existing bootstrap passfile without credential output or writes. Operator previously confirmed nonblocking normal PowerShell startup. This agent's independent launcher repeat stopped at the owner-only ACL boundary before initdb or restart; error 87 was not reproduced. Startup is not independently reverified from this managed shell.
- **Hosted verification:** Push to the already configured/authorized main branch triggered [run 39589726718](https://github.com/mignoncharly/kaemmerei/actions/runs/39589726718), source `558c0451b346265675aaeb411cb6ce4971b31af5`. All three jobs succeeded: sqlite, PostgreSQL 18 service and native-postgresql. Dependency installation, full pytest/migrations/security regressions, and explicit PostgreSQL-only lifecycle selection succeeded. API run/job/step and artifact metadata inspected directly; artifact contents were not downloaded.
- **Evidence/report:** [Current acceptance report](docs/PHASE1_BASELINE.md), [local summary](docs/evidence/phase1-acceptance-local.json), [hosted summary](docs/evidence/phase1-acceptance-ci-39589726718.json); ignored local JUnit XML and stdlib JSON retained. README, ARBEITSPLAN, plan, matrix and setup documentation updated. Previous implementation history preserved.
- **Warnings/boundaries:** Starlette/AnyIO deprecation and managed Windows pytest-cache ACL warning remain; no warning suppression. Broad concurrency, database RLS, approver assignment/content binding, production grants/backup/recovery and remaining phase findings are not accepted by these checks. Branch protection remains an account task. Local application/database and hosted technical gates pass; independent agent Windows launcher repeat remains ACL-limited. No production acceptance.
- **Host command:** From normal authorized PowerShell in the project root, run `& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'` for the first native initialization. For full dependency/local-test setup, use Complete-Phase1Setup.ps1. No database password is requested or printed by either script.
- **Next action:** Publish the evidence update; start Phase 2 only when authorized. Repository branch protection remains an owner/admin account setting.

### U010 — 2026-10-21 — Phase 2 authorization and identity administration

- **Authorization/scope:** User requested the next phase and confirmed the source plan. Implemented P02-T01–T08 from REMEDIATION PLAN PHASES.md; Phase 1 R01/R04/R10 fixes retained. Initial worktree contained only the unrelated Start-TestDatabase.ps1 whitespace edit, which remains untouched.
- **Implementation:** Source `9fde6c09546f93df75195b9096a19a4173900eee` published to authorized main. Shared contract scope/query/parent-child loaders; explicit approval capability + active team membership + assignment + existing read authority; scoped contact/department/team administration; password change and forced-reset flow; shared CLI/web identity service and concurrent last-admin guard. Identity decisions/administration are audited without secrets. Old reviewers are not automatically approvers; assignments/labels grant no read access.
- **Migration:** New additive forward `0014_identity_authorization`; private department-scoped contact backfill, preserved legacy labels/IDs/passwords, false approval flags, no invented review assignments. Existing migrations unchanged. Applied only to synthetic isolated databases; no business schema/data migration or deployment. Destructive downgrade refused; recovery requires forward repair or a compatible verified backup without restoring broad reviewer rights.
- **Verification:** Full native Windows PostgreSQL 18.3: 66 collected/passed, no failures/errors/skips/xfails, 15 passing subtests (125.97s). SQLite: 66 collected, 65 passed, one PostgreSQL-only skip, zero failures/errors/xfails, 15 passing subtests (62.69s). Final targeted PostgreSQL Phase 2: 21/21 passed (60.71s). Explicit PostgreSQL lifecycle: 1/1 passed (2.64s). Concurrent admin writers leave one active admin; populated migration preserves private labels and grants no approval. Final read-only catalog check: zero harness databases; test role attributes unchanged.
- **Investigation/corrections:** Retained the failing UI assertion and corrected new German strings damaged by PowerShell pipeline encoding. Fixed a real CLI error-path engine leak with finally disposal after SQLite cleanup failed. PostgreSQL WITH FORCE cleanup failed once with signal permission denied after all 62 then-current bodies passed; the transient process type was not established. Normal guarded DROP now replaces forced termination, with a regression and no privilege widening. The exact failed-test PostgreSQL database and SQLite scratch directory were verified against known synthetic fixtures and safely removed. Later runs pass cleanup.
- **Final transaction follow-up:** Initial implementation 3b2c2e6 passed three jobs in run 39593686567. Final source 9fde6c0 additionally consumes review form bodies before locks and holds the identity lock across credential verification and session creation without the old mid-request commit. A concurrent in-flight login/password-change regression passes on both backends; stale login sessions cannot survive the password change. The complete final source passed all three hosted jobs again.
- **Hosted evidence:** [Run 39594698525](https://github.com/mignoncharly/kaemmerei/actions/runs/39594698525) for exact source 9fde6c0 passed sqlite, postgresql and native-postgresql. Dependency setup, current migrations, full pytest/security/identity tests and explicit PostgreSQL selection succeeded. API run/job/step and artifact metadata inspected directly; artifact contents not downloaded.
- **Docs/evidence:** [Phase 2 matrix, mappings, recovery and commands](docs/PHASE2_AUTHORIZATION.md), [local summary/JUnit hashes](docs/evidence/phase2-local.json), [hosted summary](docs/evidence/phase2-ci-39594698525.json). Plan task boxes, README, ARBEITSPLAN, verification matrix/setup and changelog updated. Earlier history retained.
- **State:** Phase 2 technically verified; municipal owners/acceptance for D01/D02 remain pending. No delegation or extra read grants inferred. Local Starlette/AnyIO deprecation and pytest cache ACL warnings remain unsuppressed. Native cluster/passfiles/services preserved; no Docker introduced. Production grants/RLS/audit protection remain Phase 3; version-bound approvals and broader workflow concurrency remain Phase 4; MFA/SSO remains Phase 9. No production approval or business deployment.
- **Next action:** P03-T01 inventory migrated schema versus models and legacy exceptions, then least-privilege roles, bootstrap/context and RLS. Branch protection and municipal policy acceptance remain owner work.

### U011 — 2026-10-21 — Phase 3 schema, restricted roles, RLS and audit

- **Scope:** User authorized the next phase of the named ten-phase plan. P03-T01–T08 implemented; phases 1/2 preserved. Unrelated Start-TestDatabase.ps1 whitespace edit remains untouched and excluded from commits.
- **Implementation:** Forward integrity/security migrations, safe schema/legacy inventory, tax reviewer FK, portable constraints, separate web/integration/maintenance LOGIN roles and NOLOGIN audit owner, forced parent-scoped RLS, narrow authentication/locking functions, per-transaction validated request context, deferred credential columns and append-only events. CLI/Alembic use explicit operator/maintenance connections. See docs/PHASE3_DATABASE_SECURITY.md for grants and threat boundaries.
- **Migration/data:** Head 0016 verified on synthetic clean/populated databases. Invalid legacy associations abort without repair; test explicitly corrects its synthetic mapping then upgrades. Historical denied audit outcomes preserved and unknown historical correlation stays NULL. No business data inspected/migrated, no role/password production deployment, no cluster deletion/reinitialization/service change.
- **Verification:** Full local PostgreSQL 81 passed, zero failures/skips/xfails, 15 passing subtests (153.32s). Explicit actual PostgreSQL selection 12 passed, 69 deselected, no skips/xfails (54.89s); 11 restricted-role cases plus application lifecycle. Final SQLite full 69 passed, 12 PostgreSQL-only skips and 15 passing subtests (32.58s). Final portable migration/schema selection 4/4 passed on both backends, including legacy audit outcome preservation. Local JUnit hashes: docs/evidence/phase3-local.json. Remaining unsuppressed warnings: Starlette/AnyIO deprecation and managed Windows pytest-cache ACL.
- **Safety:** Read-only final catalog check: zero harness databases and zero generated temporary roles remain. Test role creation/cleanup validates database OID/owner/comment and generated role OID/comment; interruption journal contains no secrets. Native passfiles/binary identity/startup corrections preserved; no Docker local dependency introduced.
- **Investigation:** Initial role ownership transfer/cleanup errors corrected; exact temporary roles positively identified and cleaned. Restricted roles exposed audit RETURNING visibility and parent-lock/UPDATE policy incompatibilities, both corrected. SQLite table rebuild now preserves status CHECK and transactional FK integrity. A test's unsupported recipient fixture was corrected to an existing recipient, without weakening validation.
- **Hosted:** Implementation 5986a7473e3772e0f9a4e390aadc979101a1f9a9 pushed successfully to authorized main. Actual [run 39600834032](https://github.com/mignoncharly/kaemmerei/actions/runs/39600834032) completed successfully: sqlite, PostgreSQL 18 and native-postgresql jobs all passed. Dependency install, full migrations/tests and explicit PostgreSQL/RLS selections passed. Run/job/step and three artifact metadata inspected; archives not downloaded. Evidence: docs/evidence/phase3-ci-39600834032.json. Native bootstrap uses the existing marked cluster/private passfile; CI service bootstrap credential is synthetic.
- **Boundaries:** Shared-role GUC RLS protects omitted filters, not unrestricted application SQL/database credential compromise. Identity is a transaction snapshot and revalidated next transaction. Events cover committed changes; rolled-back denials need separate operational logging. SQLite has no RLS. DBA/security D03 acceptance, business migration, backup/restore rehearsal and production release remain open; Phase 4 owns content-bound approvals/aggregate races.
- **State/next:** Phase 3 technically verified. Publish final evidence, then P04-T01 aggregate mutation protocol. DBA/security D03 acceptance, production legacy-data inventory and operational restore remain separate; no deployment approval is inferred.

### U012 — 2026-10-21 — Phase 4 bound workflow and archive concurrency

- **Scope:** User authorized the next phase of the existing plan. P04-T01–T08 implemented without replacing working application/infrastructure. Unrelated Start-TestDatabase.ps1 whitespace edit preserved and excluded from commits.
- **Protocol:** Parsed input precedes identity guard and parent lock; session/capability revalidated under lock, including PostgreSQL GUC refresh and SQLite session validity. New/create/import writers also revalidate actor under the guard. Parent version/archive checks, child versions, mutation and revision/audit/events commit once. Guard serializes aggregate writers globally; throughput remains a Phase 9 measurement.
- **Workflow:** Separate content revision/material editor, immutable request/content/team/assignee/actor/time decisions, independent assigned approval, configurable mandatory recipients, draft creation/import and no activation override. Material/document changes supersede old approvals and downgrade activation. Terminal decisions require administrator reopening. Conflicts retain inputs; UUIDs prevent duplicate child workflow creation. Tax assessment is administrator-only; reopen/material change clears current completion metadata and preserves history.
- **Migration:** Additive 0017; legacy active/tax/review values remain explicitly unverified, unknown old review content/material actor stays unknown. New workflow-inventory returns sorted reconciliation IDs without private values. SQLite rebuild restores event triggers. Decision table has forced PostgreSQL RLS and separate NOLOGIN audit ownership. Grants/startup checks updated for head 0017/new table. No business database inspected or migrated. Recovery is forward repair or a compatible verified backup; never reactivate superseded approvals or disable RLS.
- **Local:** Full PostgreSQL 99 passed; SQLite 87 passed + 12 PostgreSQL-only skips; both with 15 passing subtests. Phase 4 selection 18 passed on both backends, PostgreSQL using actual restricted logins. Simultaneous review/task updates produce exactly one winner; nine archive races cover task create/edit, request create/edit, assignment, file upload, DMS link, contract edit and tax edit. Final hashes/times and cleanup counts recorded in docs/PHASE4_WORKFLOW.md and local evidence after execution.
- **Investigation:** Old archive regression now starts from in_review instead of assuming self-approval is allowed; it still checks rejection preserves all fields/history. Populated old-schema fixture now reflects its actual schema rather than injecting new ORM columns; labels and legacy markers asserted. PostgreSQL owner decision mutation originally affected zero rows under default-deny RLS; explicit trusted migration policy now exposes rows to the append-only trigger, which rejects modification. No xfail or warning suppression introduced.
- **Hosted:** f0d998f862941e04cbe5f120c2fa18de6c1986b7 pushed to authorized main. Actual [run 39606147120](https://github.com/mignoncharly/kaemmerei/actions/runs/39606147120) passed all three jobs: SQLite, PostgreSQL 18 and native-postgresql. Dependency install, full migrated suites, explicit PostgreSQL security selection and both explicit Phase 4 selections succeeded. Run/job/step and three artifact metadata inspected; archives not downloaded. Evidence: docs/evidence/phase4-ci-39606147120.json.
- **Boundaries:** D04 pilot rules await municipal acceptance. No business reconciliation counts, production migration/grants, scanner/quarantine, durable blob recovery, reliable external change publication, or operational load/restore acceptance claimed. Existing native cluster, passfiles, binary identity and services preserved; no Docker dependency added. Unsuppressed Starlette/AnyIO and managed Windows pytest-cache warnings remain.
- **Final verification:** Local full PostgreSQL 99 passed (202.79s), SQLite 87 passed + 12 PG-only skips (65.80s); 15 passing subtests each. Final Phase 4 PostgreSQL 18/18 passed (58.80s), SQLite 18/18 (21.80s); explicit PostgreSQL security/lifecycle 12/12 passed (35.90s), 87 deselected. No failures/errors/xfails. Final catalog: zero harness databases and zero generated temporary roles. JUnit hashes and exact source: docs/evidence/phase4-local.json.
- **State/next:** Phase 4 technically verified; publish final evidence, then P05-T01. Business D04 adoption, migration/grants, operational recovery and release remain separate approved activities.

### U013 - 2026-10-21 - Phase 5 private document lifecycle

- **Scope:** User authorized the next phase of the existing plan. P05-T01-T08 implemented. Existing Phase 1-4 safeguards and unrelated Start-TestDatabase.ps1 whitespace change preserved; no deployment or business database migration.
- **Changes:** Additive 0018 document lifecycle, durable jobs with forced PostgreSQL RLS, verified private storage, bounded container policy, fail-closed ClamAV, attachment/range digest checks, safe access audit, replacement/DMS history and hold placement. Upload metadata/job commits before processing; expensive scan outside writer locks; publication revalidates parent/principal/bytes. Pending state is not available content. Retry/reconciliation preserve unknown files. Retention eligibility is always false until D06; no deletion or hold release bypass.
- **Verification in progress:** Earlier targeted selections passed on SQLite and actual restricted PostgreSQL roles, including real native PostgreSQL 18.3 dump/restore and restored hash/authorization. Full final and hosted evidence will be appended after execution. Real local scanner and actual Windows symlink creation are explicitly unverified; CI adds an actual ClamAV/fresh-definition gate and Linux link checks.
- **Investigation:** Windows 0700 special DACL excluded the managed token; development inherits workspace ACL while production requires private operator-provisioned root/subdirectories. One empty inaccessible synthetic fixture remains. SQLite restore handle cleanup fixed with explicit connection closing; FORCE RLS pg_dump now uses full-scope trusted test owner and explicit row security. Two earlier failed synthetic fixture directories remain because automatic approval review rejected recursive cleanup (sandbox approval disabled). Exact paths and limits in Phase 5 report; no alternate deletion bypass, cluster change or credential output.
- **Boundaries:** D05/D06 municipal acceptance, production scanner installation/definitions/private Windows ACLs, business migration, scheduled retries/capacity alerts, operational RPO/RTO and release remain pending. No Docker local dependency. No independent owner acceptance inferred.
- **Documentation:** docs/PHASE5_DOCUMENT_LIFECYCLE.md covers settings, content policy, state/transaction/recovery behavior, retention/disposal design, backup/restore, shared storage and limits. README, ARBEITSPLAN, CHANGELOG, plan and verification matrix updated.
- **Final verification:** Final implementation 55167699123f310e224c400234accaa11bdef41b: 130 items collected; full PostgreSQL 128 passed + 2 explicit local skips (295.41s), SQLite 116 passed + 14 explicit skips (85.16s), 15 subtests each. Final Phase 5 selections 29 passed + 2 local skips on each backend (PG 62.10s; SQLite 16.96s). Explicit actual PostgreSQL security/lifecycle 12 passed, 118 deselected (57.54s). No failures/errors/xfails. Clean/populated/repeated migrations through 0018 and actual PG dump/restore passed. Final read-only catalog: zero harness databases and zero generated roles. Warnings remain Starlette/AnyIO and managed pytest cache ACL; no suppression. Hashes in docs/evidence/phase5-local.json.
- **Hosted final:** [Run 39613990793](https://github.com/mignoncharly/kaemmerei/actions/runs/39613990793) completed success for 5516769. SQLite, native PostgreSQL, service PostgreSQL full/explicit selections and real ClamAV clean/EICAR/current definitions succeeded. Four artifact metadata inspected, contents not downloaded. Service job API status briefly lagged the completed successful run and all successful steps; exact observed fields retained in docs/evidence/phase5-ci-39613990793.json. Initial service-suite failure traceback could not be retrieved through unauthenticated logs; later explicit matching-client installation failed until the official signed PGDG repository was configured. Final provisioning and tests pass; no skip/xfail workaround. Earlier failed runs retained in evidence.
- **State/next:** Phase 5 technically verified; production acceptance remains open. Publish evidence, then P06-T01 API compatibility and reliable synchronization when authorized. D05/D06 owners, production scanner/signatures/ACLs, retry/alert scheduling and operational restore remain separate; no deployment approval inferred.

### U014 - 2026-10-21 - Phase 6 reliable integration synchronization

- **Scope:** User authorized the next phase of the named ten-phase plan. P06-T01-T08 implemented; prior safeguards and unrelated Start-TestDatabase.ps1 whitespace change preserved. No business database migration, production role change or deployment.
- **Implementation:** Forward 0019, transactional scope-bearing outbox and serialized post-commit publication; fixed-boundary stored snapshots; opaque hashed token/API/mode/grant-bound cursors; minimal removals; explicit v2 metadata/finance/documents/content/tax/tasks/history capabilities. v1 retained without new rights for old tokens. New private sync tables have forced PostgreSQL RLS; raw scope columns are not granted to runtime roles. Parent timestamps advance on child changes. Publication/snapshot barriers also cover token/owner/department changes; authority/GUC context refreshed after lock waits.
- **Tokens:** Explicit accountable account/service, finite v2 expiry, audited grant changes/rotation/revocation, overlapping independent credentials and new-token resnapshot. Ownerless legacy policy remains explicit, with no invented ownership. Last-used telemetry is deferred and throttled after successful reads; no pre-read commit or lost request context.
- **Verification progress:** Initial full SQLite 128 passed + 15 skips and PostgreSQL 141 passed + 2 local skips; 15 subtests each. Added regressions cover late commits with lower outbox IDs, transfers, replay/tampering/expiry/floor, process restart/equal timestamps, rollback/concurrent publication, child-only changes, ownership and grant races. Final suites/source/CI evidence will be appended after execution, not inferred from these earlier counts.
- **Investigation:** Fixed literal SQL format-percent escaping through Psycopg during 0019 initialization. Corrected a test's unsupported tax enum to the existing not_applicable value. Closed a real GUC scope-refresh race around the snapshot barrier and rechecked administrator role after the identity guard. No xfail, warning suppression, permission widening or cluster replacement.
- **Boundaries:** D07 integration/security owner adoption and D06/D07 physical replay/snapshot retention remain unapproved. No automatic purge, consumer sunset date, business adapter or production load/RPO/RTO acceptance inferred. Snapshot/child expansion bounds fail explicitly rather than truncate. Existing Windows ClamAV/symlink/ACL limits remain documented; native infrastructure preserved without Docker.
- **Docs:** docs/PHASE6_INTEGRATION_SYNC.md, public API response schema, admin UI, README, plan, ARBEITSPLAN, CHANGELOG and verification matrix. Snapshot payloads must enter the privacy/backup inventory; post-restore consumers require explicit resnapshot.
- **Final implementation:** 3d5e88a7fbd5f198437b883cf233187482434d5e. Follow-ups preserve explicit development PostgreSQL owner configurations without fallback after restricted-role failure, reject non-READ-COMMITTED synchronization with 503, and materialize contract-bound history pages instead of using raw revision IDs as commit watermarks.
- **Final local evidence:** 151 collected; PostgreSQL 149 passed + 2 local skips (421.57s), SQLite 134 passed + 17 skips (147.68s), 15 subtests each. Phase 6 PG 21/21 (109.96s), SQLite 18 passed + 3 PG-only skips (22.71s). Explicit actual PostgreSQL selection 15 passed, 136 deselected (107.97s). No failures/errors/xfails. Separate 0013-to-0019 legacy-token probes preserve legacy-only rights, unknown owner and original creator/expiry/credential on both backends. Read-only operator status executed on both synthetic backends. Final catalog: zero harness databases and zero generated temporary roles; control-role attributes unchanged. JUnit hashes/counts/probes: docs/evidence/phase6-local.json.
- **Hosted:** [Run 39624468561](https://github.com/mignoncharly/kaemmerei/actions/runs/39624468561) completed success for exact final source 3d5e88a. All four actual job conclusions/steps confirmed: SQLite, PostgreSQL 18, native-postgresql, real ClamAV/current official definitions. Dependencies, migrations, full suites and explicit security/Phase 4/5/6 checks passed. Four artifact metadata inspected; archives not downloaded. Earlier implementation runs 39622830892/39623587187 also passed. Evidence: docs/evidence/phase6-ci-39624468561.json.
- **Remaining boundaries:** Two unsuppressed local warnings remain Starlette/AnyIO and managed pytest cache ACL. Local scanner/symlink/production ACL limits and earlier Phase 5 filesystem residues unchanged. D07 profile/ownership/transition adoption, D06/D07 physical replay/snapshot retention and privacy, production capacity/quotas/alerts/RPO/RTO, business migration/grants and release remain pending. No deployment or new Docker dependency.
- **State/next:** Phase 6 technically verified; publish final evidence, then P07-T01 when authorized. Financial/history/date/Excel corrections and owner decisions remain their planned next phase.

### U015 - 2026-10-21 - Phase 7 financial history, dates and Excel

- **Scope:** Next phase authorized under the existing ten-phase plan. Technical defaults P07-T02-T09 implemented; P07-T01 finance agreement and D08-D10 remain unapproved. No business migration, deployment or native cluster change. Unrelated Start-TestDatabase.ps1 whitespace preserved.
- **Changes:** Additive 0020 unknown legacy value basis, scoped exact external identity, narrow PostgreSQL historical aggregate function with live session authorization. Recorded-at snapshot history independent of current population, historical department/direction/basis, missing-data/reconciliation tables. One bounded calendar service; explicit terminated/missed-notice/legal limits. Strict create-only XLSX, literal strings, date-system/overflow/formula/header/reference checks; guarded atomic duplicates, natural-description ambiguity and raw/hash/row audit provenance.
- **Verification progress:** Phase 7 actual restricted PostgreSQL 18 passed; SQLite 17 passed + one PG-only skip. Broader security/schema selections 22 passed on each backend before subsequent added regressions. Full final suites and hosted evidence pending actual results. No xfail/warning suppression. Initial fixture keyword collision, missing new export fields and unknown-amount rendering failures corrected and rerun.
- **Boundaries:** D08 finance inventory semantics, D09 legal calendar interpretation and D10 reference/import policy need named owner adoption. EUR metadata only, no payments/commitments/effective-at history inferred. Legacy pre-evidence gaps remain unknown. Phase 8 browser/CSP/text/accessibility and operational release gates remain open.
- **Documentation/recovery:** docs/PHASE7_FINANCE_DATES_EXCEL.md, public response schema and existing project docs updated. Preserve amounts, unknown basis, optional references and import provenance; forward repair or coordinated backup recovery only. No destructive downgrade.
- **Next:** Finish full SQLite/PostgreSQL suites, explicit PostgreSQL selection, hosted jobs and safe final catalog check; append exact-source evidence before declaring technical verification.

- **Final implementation:** 2fd1bf85406895254d070453bbc1ced03fe7ff72. Follow-up guard refreshes actor membership before import row ownership/tax/identity validation; added race regression. Populated migration assertions preserve unknown basis and NULL references. No application/test source changed after this commit.
- **Final local verification:** 170 items; PostgreSQL 168 passed + 2 known local skips (441.32s), SQLite 152 passed + 18 explicit skips (129.17s), 15 passing subtests each. Phase 7 PG 19/19 (33.18s), SQLite 18 passed + one PG-only skip (7.39s); explicit actual PG selection 16 passed, 154 deselected (100.19s). Zero failures/errors/xfails. Clean/populated/repeated 0020, schema equality, actual restricted roles and dump/restore pass. Exact JUnit counts/hashes: docs/evidence/phase7-local.json.
- **Final safety check:** Native PostgreSQL 18.3; zero harness databases and zero generated runtime roles. Control role remains NOSUPERUSER CREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS. No cluster replacement, unrelated service operation, business data/grant change or credential output. Existing Windows launcher/identity/Unicode fixes preserved.
- **Hosted:** [Run 39629880926](https://github.com/mignoncharly/kaemmerei/actions/runs/39629880926) completed success for exact final implementation 2fd1bf8. All four actual jobs/steps confirmed: SQLite, PostgreSQL 18 service, native PostgreSQL and ClamAV. Dependencies, migrations, full suites, explicit PostgreSQL and Phase 4/5/6/7 selections passed. Four artifact metadata entries inspected, archives not downloaded. Evidence: docs/evidence/phase7-ci-39629880926.json.
- **Remaining limitations:** Two unsuppressed local warnings (Starlette/AnyIO and managed pytest cache ACL); local real scanner/symlink/production ACL and earlier Phase 5 retained synthetic filesystem residues unchanged. Finance/legal/product D08-D10 are not approved. Historical evidence gaps, no effective-at/payment ledger, no automatic Excel updates, browser/CSP/accessibility/encoding and operational release gates are explicit. P07-T01 remains unchecked; no municipal sign-off or deployment is inferred.
- **State/next:** Phase 7 technically verified. Next technical phase P08-T01 under the existing plan; owner adoption and production deployment remain separate.

### U016 - 2026-10-21 - Phase 8 frontend behavior and navigation

- **Scope:** Next phase under the existing plan. P08-T01-T08 implemented; T09 browser/semantic/keyboard/reflow gate added, actual hosted result pending. Prior ownership/RLS/workflow/document/integration safeguards preserved. No schema, native cluster or business deployment change. Unrelated Start-TestDatabase.ps1 whitespace preserved.
- **Changes:** External chart width classes under unchanged CSP; normalized checkbox presentation; persistent feedback and explicit success dismissal; allowlisted bounded noncredential recovery with HTML/API error separation. Shared list/export filters, stable pagination beyond 500, exact totals and explicit 5000-row export bound. Distinct approval contract counts; scoped personal task/actionable-current-review inbox. German validation/text/UTC clarity, review action consistency, archive confirmation/recovery wording, focus/skip/contrast/semantic/reflow improvements.
- **Verification progress:** Initial broad SQLite selection 70 passed + one PG-only skip; Phase 8 initial 6/6 on both backends, extended to seven items. Full suites and hosted evidence pending actual execution. Fixture-only failures corrected without relaxing safety limits. No xfail or warning suppression.
- **Local browser:** Browser service inventory empty. pip proxy/private temp ACL limitations; official PyPI wheel hashes checked and tools isolated in ignored workspace scratch. Playwright failed before browser start with Windows named-pipe WinError 5. No permissions/sandbox/security weakening. Required Linux browser CI job added; no local browser pass claimed. Not the historical PostgreSQL error 87.
- **Boundaries:** No complete WCAG/assistive-technology or municipal usability certification, production workload target, owner acceptance or deployment inferred. Earlier D08-D10 and other decisions remain pending. Existing local ClamAV/symlink/production ACL and earlier retained synthetic filesystem residues unchanged.
- **Docs/next:** docs/PHASE8_FRONTEND_NAVIGATION.md and existing project docs. Finish local full suites, explicit PostgreSQL/Phase 8, actual hosted browser/jobs and final read-only cleanup catalog; append exact source/counts/hashes/results.

- **Hosted final:** Run 39635885108 completed success for 6ebcaad00e8dae84f41a5b0480c3793598541f5a. Actual job/step conclusions verified for all five jobs: browser, SQLite, PostgreSQL 18 service, native-postgresql and ClamAV. Five artifact metadata entries inspected; archives/screenshots not downloaded or manually inspected. Earlier runs 39634529672/39635125218 were superseded/cancelled, not passed overall. Evidence: docs/evidence/phase8-ci-39635885108.json.
- **Local final progress:** 178 collected; SQLite 160 passed + 18 explicit skips, 15 passing subtests (341.85s). Phase 8 eight passing items on both backends, including tax/activation controls and independent role/capability presentation. Final full PostgreSQL and final catalog remain pending; earlier complete PostgreSQL 175 + two skips is intermediate evidence. Selected static palette contrast checks pass; no full WCAG/manual screen-reader acceptance inferred.

- **Final implementation/evidence:** 6ebcaad00e8dae84f41a5b0480c3793598541f5a. No application/test source changes after this revision. Phase 8 eight items pass on both backends (SQLite 24.17s; PG 97.59s). Final full 178 collected: SQLite 160 passed + 18 explicit skips (341.85s); PostgreSQL 176 passed + two local skips (1019.38s); 15 passing subtests each. Explicit PG 16 passed, 162 deselected (110.71s). Zero failures/errors/xfails. Durations reflect overlapping local verification, not a production performance benchmark. Counts/hashes: docs/evidence/phase8-local.json.
- **Final safety:** All local runs finished; read-only catalog reports zero harness databases and zero generated runtime roles. Native PostgreSQL 18.3 control role remains NOSUPERUSER CREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS. No cluster replacement/service stop, business data change or credential output. Existing launcher/Unicode/identity protections preserved.
- **Final state:** P08-T01-T09 technically verified; five exact-source hosted jobs passed. Browser/scanner/Linux link checks have hosted coverage. Two local full-PG skips are existing ClamAV absence and Windows symlink permission. Starlette/AnyIO and managed pytest cache warnings remain unsuppressed. Local browser WinError 5, manual AT/WCAG/usability, earlier D08-D10/other owners, R21 broader workload controls and R22 operations remain explicit. No production deployment or owner acceptance inferred.
- **Next:** P09-T01 under the existing plan. Obtain workload/deployment/security/recovery targets and owners; preserve all current authorization, workflow, document, synchronization and frontend safeguards.

### U017 - 2026-10-21 - Phase 9 first availability implementation batch

- **Plan/source:** P09-T01-T04, T07-T08 and T11 partial; base b962824, guards 1cecc54, dependency source 1649b15. Phase 9 remains in progress, all exit criteria and incomplete plan boxes remain open. Phase 10 not started.
- **Changes:** Pre-parser streamed byte/deadline/part/concurrency admission; private-storage quota including orphan/legacy bytes; shared login/API work reservations; synchronous POST workers; bounded PostgreSQL pools/timeouts; export byte/completion checks plus eager department loading; trusted proxy/HTTPS/DB TLS configuration; redacted correlation and basic health checks.
- **Schema/privileges:** Additive 0021 indexes and fixed-budget SECURITY DEFINER API reservation. Reapply explicit runtime grants after authorized migration. No broad integration table grants, no business backfill/deletion. Existing role provisioning script now checks actual Alembic head instead of obsolete 0019.
- **Development defects corrected:** Multipart exception/cancellation cleanup, authorization priority with stricter form counts, and v2 reauthentication opening a second SQLite writer. Failed intermediate runs remain failed evidence, superseded only by subsequent completed tests.
- **Verification:** Final results appended below after execution. Explicit restricted-role PostgreSQL selection is required, not SQLite substitution. Existing native cluster/Unicode/lock/startup infrastructure preserved. No production deployment or external message delivery.
- **CI verified:** Initial push failed, normal retry succeeded. Runs 39644065729 (guarded 1cecc54) and 39645201928 (patched dependencies 1649b15) each passed all five jobs. Actual job/step/artifact metadata inspected; archives/screenshots not manually inspected. Evidence docs/evidence/phase9-ci-39645201928.json. No deployment or Phase 9 exit inferred.
- **Remaining engineering:** Durable background job claims/retries/coordinator/schedules, scoped workload optimization and agreed benchmarks, full metrics/alert delivery, encrypted scheduled backup/restore/RPO-RTO evidence, identity/MFA/provider implementation after D12, current dependency advisory/release-artifact review. Proxy/volume quota/actual TLS/service checks outstanding. R07/R21/R22 remain open.
- **Owner decisions:** D11 hosting/load/recovery/alert owners and D12 identity policy unapproved; D13 dashboard/manual-only default not product acceptance. D06/D07 prohibit inventing destructive retention rules.
- **Safety:** Existing user whitespace change in scripts/Start-TestDatabase.ps1 preserved and excluded from commit. Never reinitialize/delete the cluster, bypass managed ACLs, stop unrelated services, print secrets or apply tests to a business DB.
- **Advisory follow-up (new R42; original R41 preserved):** Reviewed initial affected Starlette 0.50.0 / multipart 0.0.29 ranges against maintainer sources. Added parser/UNC/Host guards and raw ASGI security paths; adopted compatible FastAPI 0.158.0, Starlette 1.9.0, multipart 0.0.32 and required OpenTelemetry API 1.44.0 from SHA-verified wheels. No SDK/exporter, third-party source patch, proxy/TLS/ACL weakening or real message delivery. Initial partial offline install repaired by normal retry; obsolete pip backups preserved outside site-packages. pip check passes. Actual OSV query returned zero matches for 28 adopted runtime versions; broader tool/OS review and release lock remain open.
- **Next:** Continue Phase 9 P09-T03/T05 durable jobs/scheduling and P09-T11 release artifacts from docs/PHASE9_OPERATIONS.md; do not skip to Phase 10 or report Phase 9 complete.

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

### U017 verification checkpoint and owner decisions (2026-10-21)

Final adopted-environment results: PostgreSQL 197 passed/2 skipped, SQLite 181 passed/18 skipped (199 collected; 15 passing subtests each); explicit PostgreSQL 16 passed; Phase 9 selection 21 passed on each backend. Zero failures, errors or xfails. See `docs/evidence/phase9-local.json`; JUnit suite totals include subtests whereas testcase elements count main items. Catalog cleanup confirmed zero harness databases/generated roles. Hosted exact-source 1649b15 run 39645201928 passed all five jobs; metadata inspected, artifacts not downloaded.

D11 platform selected by user: native Windows, PostgreSQL and a TLS reverse proxy. D12 selected by user: existing local accounts, TOTP MFA and audited administrator recovery. These select implementation scope; neither deployment nor unimplemented MFA is accepted. Proposed workload/RPO/RTO targets remain awaiting reply. Operations/identity owners and production acceptance remain pending.

### U018 - Phase 9 operations, approved decisions and measured workload (2026-10-21)

- User selected native Windows/PostgreSQL/TLS proxy and local TOTP with audited administrator recovery. Approved initial targets: 10 concurrent users, 10,000 contracts, 50,000 document metadata rows; page p95 <2s, bounded export <15s; RPO 24h, RTO 4h. No deployment authorization inferred. Human MFA remains unimplemented and is a production blocker.
- Production scans now use durable quarantine jobs; explicit operator scan-pending has a database-wide session lock, fixed batch/launch deadline, persisted crash reservations, bounded backoff/five attempts, unchanged publication/hash safeguards and live uploader revalidation. Automated legacy recovery is excluded. Web/limited-maintenance roles cannot execute coordinator operations. No deletion, cluster/service change or new privileged web grant.
- Added review-only Windows launcher, nonsecret configuration example, redacted rotating logs, native TLS proxy example and disabled Task Scheduler XML renderer. Native PowerShell syntax and structural template tests pass; no service/task/proxy installed or live-tested. OS ACL/quota/firewall/certificate/service acceptance remains pending.
- Initial approved-size synthetic read load failed: list p95 10.35s with ten 503s, reports 6.80s; detail/export passed. Failure retained in docs/evidence/phase9-workload-before.json. Dataset has undated drafts and external metadata only, without revision histories/tasks/reviews or file bodies; representative mixed load remains a separate gate.
- Added scoped SQL status/approval counts, dated-only reminder candidates and department eager loading. Migration 0022 evaluates the exact existing department SELECT rule via an uncorrelated statement InitPlan. Mutation policies unchanged; helper PUBLIC execute revoked. Actual-role rule-equivalence/plan tests pass 2/2 after correcting EXPLAIN to VERBOSE; original assertion failure retained in verification history.
- Existing document/operations/Windows PostgreSQL selection: 46 passed + 2 explicit local skips (before query optimization); Windows/operations SQLite selection: 13 passed + 3 PG-only skips (before later added uploader recheck test). Final frozen-source full tests, benchmark rerun, cleanup and hosted results must be appended below before acceptance claims.
- Remaining Phase 9 work: MFA enrollment/challenge/replay/seed protection/recovery, encrypted consistent backups and measured RPO/RTO, representative dates/history/mixed-load benchmark, remaining schedules/queue admission/monitoring/alert ownership, live native proxy/service/ACL/storage validation and reproducible release gate. U017 exact-source CI is historical evidence, not CI for these new operations changes.


U018 final checkpoint: source c3499965fa619b48e126d18e0ddb8103c9b03828 committed/pushed main. Full 219 collected: PostgreSQL 217 passed + 2 local skips (476.19s), SQLite 196 + 23 skips (154.99s); 15 passing subtests each. Explicit actual PostgreSQL 21 passed/205 deselected; seven new draft MFA codec tests were collected but deselected in that run. No failures/errors/xfails. All five exact-source hosted jobs passed: run 39650882010. Initial undated read-load rerun meets all four targets, all 200 HTTP 200; mixed dates/history/files remain unverified. Catalog cleanup confirmed 0 guarded databases/0 generated roles, control privileges unchanged. See phase9-u018-local.json, phase9-workload-aggregated.json and phase9-ci-39650882010.json. U019 MFA work is beginning and is excluded from this acceptance checkpoint; existing user launcher whitespace change remains untouched. Phase 9 exit remains open.


### U019 - Approved local TOTP and audited recovery implementation (2026-10-21)

- D12 implementation: password-proven five-minute pending sessions, CSRF-protected operator-authorized enrollment, six-digit/30s TOTP with persisted monotonic replay step, shared throttling/five-attempt challenge burn and atomic verified full-session rotation. PostgreSQL principal checks enforce MFA; service-token authorization remains separate.
- Additive 0023: encrypted MFA credentials and rollout policy have forced owner-only RLS; no direct runtime grants, fixed-search-path scoped functions, PUBLIC revoke and integration/audit function denial. Migration preserves old rows and never silently enables rollout or enrolls users. Production startup requires key/policy; missing policy fails closed. Password and identity changes revoke pending challenges as well as full sessions.
- PyOTP 2.10.0/cryptography 50.0.2 adopted from official hash-verified wheels; user-bound Fernet ciphertext, private external keyring, read-only production ACL checks, bounded operator key rotation and separate escrow requirements. Runtime closure 30 versions has zero OSV matches/errors/pagination; broader tooling/hash-lock work remains open. Installer temp cleanup warnings retained without external deletions.
- Recovery requires an explicit owner command, verified-identity assertion and case reference; revokes sessions, clears old factor, authorizes 24h new setup and forces password change. No browser factor-disable endpoint or bypass session. Enrollment/recovery/verification/denial/rotation audited without secret material. Windows role launcher/example updated for nonsecret key-path configuration.
- Targeted real PG MFA/codec: 21 passed, later 24 with configuration checks; real synthetic MFA database restore/missing-policy selection 3 passed. Initial cache-header and wrong API-version test assertions were corrected without weakening application controls. New full suites/hosted checks are running; their final results must be appended. U018 c349996 remains the last fully recorded checkpoint until then.
- Deployment and actual private key/ACL/custodian/device acceptance remain open, along with encrypted scheduled backup/recovery, representative mixed workload, remaining operations/alerts/schedules and release reproducibility. Production has not been deployed, migrated, reconfigured or granted new roles. Existing native cluster/Unicode fixes and unrelated launcher whitespace remain intact.

U019 interim full verification: SQLite 244 collected, 219 passed/25 explicit skips, 15 passing subtests (233.36s), zero failures/errors/xfails. Native PostgreSQL full suite remains running. Exact-source MFA CI is pending the new implementation push; U018 CI remains verified only for c349996.


U019 final verification: ece779758db1660c2a3314331cea97f63974c2e6 committed/pushed main. Full 244 collected: PostgreSQL 242 passed + 2 local skips (585.98s), SQLite 219 + 25 skips (233.36s), 15 passing subtests each. Explicit actual PostgreSQL 23 passed/221 deselected (85.23s). All 25 MFA/codec items executed in the full PG run; two PG-only cases are explicit SQLite skips. Zero failures/errors/xfails. Clean/populated/repeated head 0023 migrations, actual roles and real restore regressions passed. Catalog 0 guarded DBs/0 generated roles, control privileges unchanged. Hosted run 39656369586 passed all five exact-source jobs; artifact metadata inspected, archives not downloaded. Evidence: phase9-u019-local.json and phase9-ci-39656369586.json. P09-T10 implementation technically verified; production custodians/keys/ACL/device/recovery procedure adoption remain unaccepted. Phase 9 exit remains open. Next independent work: P09-T09 encrypted signed backup/restore and remaining scheduling/monitoring/release gates.


### U020 - Encrypted/signed native backup and guarded restore (2026-10-21)

- P09-T09 implementation in app/backup.py, backup_crypto.py, backup_restore.py and operator CLI: owner-only named PostgreSQL identity, non-overlap lock, guarded exported snapshot, checked file inventory, native age encryption and independently trusted Ed25519 receipt. No migration, retention deletion, business DB import or deployment.
- Restore prepares a new private bundle only after signature, exact ciphertext-stream digest, authenticated decryption, strict member bounds and all hashes pass. Actual import tests use only UUID/OID/owner/comment-identified new empty databases; restricted LOGIN access, document hashes, revision IDs and encrypted MFA replay state are verified after restore.
- Disabled 12-hour Windows backup task draft and required native age provisioning for both hosted PostgreSQL jobs. No production keys/escrow, task registration, external notifications or approval workflows activated. Tool asset hashes recorded; Sigsum proof not verified.
- Latest user ownership decision: future operations proposed for Municipal IT Operations/System Administration; sensitive identity recovery/key custody proposed for authorized identity/access or IT Security Administration with dual authorization, all provisional. No individuals or dedicated IAM team assumed. No municipal approvals for development, testing, routine login/use or local account recovery. Existing local operator procedures remain available. See PHASE9_OPERATIONS for distinctions and review-only commands.
- Verification history: first new test collection failed on an incorrect model name; corrected to existing Revision without schema changes. Then 16, 28 and 29 targeted tests passed; latest reviewed-source targeted run 29 passed/0 skipped/0 failed in 17.69s. Entire suite now 262 collected. Full current-source PostgreSQL/SQLite and hosted CI results pending below. Previous ece7797 hosted pass applies only to U019.
- P09-T09 stays open: no production/off-host schedule, representative recovery/RPO/RTO, backup-age alert or retention/custody acceptance. Tiny synthetic recovery timings are observations, not certificates. Keep all prior failures/history. User launcher whitespace preserved. Next: frozen-source full tests, exact-source hosted verification and catalog cleanup evidence; then remaining Phase 9 monitoring/workload/release gates.


### U020 final technical verification - source 92329b6

- 262 collected. Native PostgreSQL: 260 passed, 2 explicit local skips, 15 passing subtests, 578.16s. SQLite: 236 passed, 26 explicit skips, 15 passing subtests, 160.25s. Zero failures/errors/xfails.
- Explicit PostgreSQL: 24 passed/238 deselected/zero skips, 128.22s. Reviewed backup/Windows selection: 29 passed/zero skips, 17.69s. All 17 backup cases executed in full PostgreSQL; SQLite skips only the real PostgreSQL backup among those cases.
- Actual clean/populated/repeated migrations remain at 0023_human_mfa. Encrypted snapshot/native restore, restricted restored department access/downloads, IDs/hashes, revisions and encrypted MFA replay state passed. Tiny synthetic timings: backup 1.199s and preparation/import/verification 3.030s. Two contracts, one PDF and one staged orphan: this is not representative production recovery or RPO/RTO acceptance.
- All FIVE exact-source hosted jobs passed: [run 39660619585](https://github.com/mignoncharly/kaemmerei/actions/runs/39660619585), source 92329b6f181f174f0212c429e3368383bcc027dc. Both PostgreSQL jobs required native encryption tools and actual backup tests. Run/jobs/steps and five artifact metadata entries inspected; archives not downloaded.
- Final read-only catalog: zero guarded disposable databases, zero generated roles; dedicated control privileges unchanged. No business data/schema/cluster/service modification or production deployment. pip check clean. Warnings: existing Starlette/httpx TestClient deprecation and Windows pytest-cache ACL/path warning; no warning suppressed.
- Evidence: [local JSON](docs/evidence/phase9-u020-local.json), [hosted JSON](docs/evidence/phase9-ci-39660619585.json), [native tool provenance](docs/evidence/phase9-age-provenance.json). JUnit hashes bind the recorded local results.
- Phase 9 remains open. Remaining work includes monitoring/backup-age alerts, representative mixed workload/recovery, remaining scheduled jobs, native TLS/service/ACL/capacity acceptance and reproducible release checks. Production ownership and custody are provisional, not development blockers. A static follow-up is explicit production TLS validation in the standalone DBA role-configuration script, which currently constructs development Settings; the application/operator CLI backup path already revalidates production TLS. Do not deploy via that script before resolving the follow-up. No production rollout is authorized.


### U021 - Production DBA TLS and reproducible source release (2026-10-21)

- Phase 10 entry requires Phase 9 verification or explicit optional scope. Continuing required Phase 9 engineering; no production readiness or waiver inferred.
- Shared production verify-full/absolute local CA policy now covers the standalone grants script before connecting, with environment validation and redacted malformed URLs. Existing identity/head/grant checks preserved; development needs no TLS or municipal approval. Actual production TLS handshake remains unverified.
- Runtime lock: 30 unchanged versions, 706 official non-yanked wheel hashes, no sdists. Fresh native Windows venv installed all packages offline from hash-verified official wheels; version checks/pip check passed. Shared environment unchanged. Metadata/lock provenance retained.
- Deterministic HEAD-blob release builder/manifest and independent-checksum verifier exclude private/runtime-data paths, links, unexpected runtime objects and uncommitted changes. Packaged-source smoke uses only isolated in-memory SQLite with credentials removed. No deployment, service/task registration or production key operation.
- Hosted workflow now has eight jobs: existing five, Windows/Linux locked-release checks and cross-platform byte comparison. Current-source hosted/full results pending. Latest targeted release/TLS 29 passed; preceding SQLite availability/MFA/TLS 47 passed/2 explicit PG skips.
- Investigation: explicit UTF-8 fixes metadata decoding; own synthetic Git object read-only attributes handled in fixture cleanup; pip --target private-temp ACL failure resolved using supported pip --python into a new venv. Earlier six failed synthetic fixture directories retained after automatic cleanup approval rejection; no alternate deletion attempted. Pip temp warnings retained. User launcher whitespace preserved.
- Next: freeze source, build/smoke actual archive with fresh runtime, full SQLite/PG/explicit PG tests, exact-source hosted evidence and final DB/role cleanup check. Phase 9 remains open; PHASE9_OPERATIONS U021 has commands and remaining gates.
