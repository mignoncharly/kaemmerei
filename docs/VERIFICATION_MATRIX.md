# Verification matrix and implementation boundaries

Phase 8 U016: frontend/navigation technically verified for 6ebcaad: 178 collected; PG 176 passed + 2 local skips, SQLite 160 passed + 18; eight Phase 8 tests pass on both backends, all five hosted jobs including Chromium passed. [Behavior, browser constraints and evidence](PHASE8_FRONTEND_NAVIGATION.md). Production and usability acceptance remain pending.

Phase 7 U015: financial inventory/history, calendar estimates and create-only Excel technically verified: 170 collected; PG 168 passed + 2 local skips; SQLite 152 passed + 18; 15 subtests each. Phase 7 restricted PostgreSQL 19 passed; all four hosted jobs passed for 2fd1bf8. [Definitions, migration and verification](PHASE7_FINANCE_DATES_EXCEL.md). D08-D10 and production acceptance remain pending.

Stand: 2026-10-21. Phase 1 engineering baseline; no business acceptance implied.

Phase 2 update U010: [adopted capability matrix and migration/verification report](PHASE2_AUTHORIZATION.md).
Full local PostgreSQL: 66 passed; SQLite: 65 passed + one PostgreSQL-only skip; 15 subtests passed on both.
All three hosted jobs passed for Phase 2 implementation 9fde6c0. Current Phase 3 evidence: [database security report](PHASE3_DATABASE_SECURITY.md). Content-bound approvals remain Phase 4 work.

Phase 3 U011: PostgreSQL 81 passed; SQLite 69 passed + 12 PostgreSQL-only skips;
15 passing subtests per full suite. Explicit PostgreSQL selection: 12 passed, zero
skips. Hosted run 39600834032 passed all three jobs for 5986a74. No production acceptance.

## Permission regression matrix

Phase 4 U012: [workflow report](PHASE4_WORKFLOW.md), implementation f0d998f.
PostgreSQL 99 passed; SQLite 87 passed + 12 PostgreSQL-only skips; 15 subtests each.
Phase 4 actual restricted-login selection: 18 passed, including synchronized
decision/task races and nine archive paths. CI 39606147120 passed all three jobs.
Municipal D04 acceptance remains pending.

The desired rules below identify current evidence individually. Delegation, retention and remaining later-phase capabilities stay open. `Expected failure` means the desired assertion currently fails and remains an OPEN finding. A setup/migration/transport failure is not an acceptable expected failure.

| Case | Principal / resource | Desired result | Current evidence or pending phase |
|---|---|---|---|
| V01 | Guest -> list/detail/export/document/API | Login redirect for HTML; API 401; no business data | Original guest test covers list/create; API credentials test covers missing auth. Other guest endpoints extend in P2/P6. |
| V02 | Own-department writer -> own contract | Read/create/edit/archive under version and CSRF rules | Original isolation, CRUD/conflict, CSRF tests |
| V03 | Department writer -> other department contract | No read/write; forged posted department cannot change ownership | Original ownership/direct mutation tests |
| V04 | Department writer -> other department metadata | No private names/types from dropdown queries | R01 passing on SQLite/PostgreSQL; acceptance test also covers searches, reports, export, API and documents |
| V05 | Admin -> all department contracts | Authorized read/write; explicit department selected | Original search/filter and CRUD tests |
| V06 | Reviewer -> all contracts | Read permitted, normal contract/task/document writes forbidden | Original reviewer test and new child-permission test |
| V07 | Reviewer -> review decision | Forbidden without explicit approval capability/assignment | Passing Phase 2: default reviewer denied; capability + membership alone denied; only explicitly assigned authorized user can decide |
| V08 | Authorized approver -> assigned current-content review | Only allowed transitions/reasons/version; no unrelated decision | Phase 4 binding, transition/reopen, mandatory activation and material invalidation regressions pass |
| V09 | Wrong approver/self-approver -> decision | Denied under accepted separation-of-duty rules | Phase 4 pilot independent assignment checks pass; D04 municipal adoption pending |
| V10 | Inactive account -> login | 401; no authenticated session | New inactive-user test |
| V11 | Active account in inactive department -> protected access | Access denied/session invalidated consistently | R10 passing: existing session, fresh login, reads/writes and scoped tokens rejected |
| V12 | Any user -> forged child under different parent | 404 regardless of guessed child identifier | Shared parent/child loader; task/document/API mismatch regressions and assignment parent authorization pass |
| V13 | Other-department writer -> tasks/reviews/uploads/DMS link | No child creation or information exposure | New child-permission test |
| V14 | Admin -> upload/preview/download/API document | Only its application instance's private storage used | New end-to-end storage test, including a second isolated app |
| V15 | Scoped token -> contracts | Only token's department | New scoped-token test |
| V16 | Unscoped token -> contracts | Explicitly authorized global read | New unscoped-token test; narrower field capabilities Phase 6 |
| V17 | Expired/revoked/invalid/missing token | 401 consistently | New token test |
| V18 | Token -> wrong department or mismatched document parent | 404; no file bytes | Passing acceptance regression on SQLite/PostgreSQL; wider capability matrix remains Phase 6 |
| V19 | Any authorized writer -> archived aggregate | No contract or child mutation | Phase 4 shared parent locks and database archive barriers; all nine post-barrier mutations rejected |
| V20 | Concurrent task/review/archive -> same aggregate | Consistent versioned outcome; no lost decision | Phase 4 SQLite and actual restricted PostgreSQL logins: one task/decision winner, archive revision last |
| V21 | Missing CSRF -> authenticated HTML mutations | 403 and zero writes | Original login/create/edit/archive tests; extend child/admin paths in Phase 2/4 |
| V22 | Low-privilege DB role -> deliberately unscoped SQL | RLS denies other departments and invalid context | Phase 3 actual LOGIN-role SQL/API/child/credential tests in tests/test_phase3.py |
| V23 | Reused pooled connection -> different identity | No retained authorization context | Phase 3 same physical backend alternates principals; commit/rollback and revoked-session revalidation tested |
| V24 | Token -> scope transfer/incremental document changes | Removal and changed content reliably delivered | Phase 6; R05 remains open |

## Migration and environment matrix

| Case | SQLite | PostgreSQL |
|---|---|---|
| Clean Alembic upgrade to head and idempotent repeat | Passed locally and in CI | Passed locally on Windows PostgreSQL 18; explicit lifecycle test verifies cleanup |
| Populated 0001 -> 0003 -> head | Passed; record/version/revision/document metadata preserved | Passed locally on Windows PostgreSQL 18 and historically in Linux CI |
| Existing CRUD/authentication suite using migrated schema | 10 original checks passed | Passed in Linux CI through both stdlib runner and direct pytest |
| Document isolation and new permission checks | 4 checks passed | Passed in Linux CI |
| Production configuration rejection | Passed (one check with six invalid-setting subcases) | No connection required |
| Per-call document configuration | Passed | No connection required |
| Original three expected failures | R01/R04/R10 are normal passing regressions | All pass against PostgreSQL; full suite 44 passed, no skips/xfails; see U009 acceptance report |

Migration preservation fixtures use synthetic records and metadata, not a copied business database. They do not constitute a production-data migration rehearsal. Phase 3 adds the missing tax-reviewer FK and schema equality checks on both backends; invalid legacy rows stop migration without repairs. Security schema/functions/policies/triggers are intentional database-only controls; Python versus server defaults are documented separately.

## Domain/service boundaries (P01-T07)

Use these contracts for incremental extraction. Authorization must remain enforceable at every HTTP/API entry; moving functions alone does not close findings.

| Boundary | Current location | Intended responsibility / interface | Next phase |
|---|---|---|---|
| Runtime configuration | `app/config.py` | Immutable settings; each app owns DB/storage; env read at configuration time | Storage hardened in P5; operation limits P9 |
| Migration execution | `app/migrations.py`, `alembic/env.py` | Explicit disposable connection, head lookup; supplied connection cannot fall back to regular environment DB | P3 schema/RLS |
| Authentication/session | `app/security.py`, login routes | Resolve authenticated principal; CSRF/session/password lifecycle | P2/P9 |
| Authorization/query scope | `app/logic.py`, duplicated route queries | Capability decisions, authorized query specifications, parent/child lookup | P2 extraction |
| Aggregate mutations | `app/main.py` contract/child handlers | One authorization/version/archive/lock/audit/commit protocol | P4 service |
| Workflow/tax | Review routes and contract validation | Assignment, state transitions, decision provenance, content revision | P4 service |
| Documents | Upload helper and document routes | Explicit app-instance storage passed to helpers; future staged/scan/download lifecycle | P5 service |
| Integration/change publication | Token/API routes | Scoped read contract, durable change events/cursors/removals | P6 service |
| Reporting/deadlines | Report/date functions in `app/main.py` | Approved financial/date specification; shared status-aware calculations | P7 service |
| Excel | `app/excel.py`, import/export routes | Workbook encoding/parsing plus separate authorized application operations | P7 |
| HTTP/templates | `app/main.py`, `app/templates` | Parse input, invoke services, render consistent responses; no independent policy copies | P8 |

Phase 1 extracts only explicit migration execution and reusable verification resources, and removes module-global document storage. It deliberately leaves business authorization/workflow/reporting behavior for its scheduled phase.

## Release checks

- Phase 1 exit requires working foundations and actual PostgreSQL migration evidence. This technical gate is now met by [CI run 39571113046](https://github.com/mignoncharly/kaemmerei/actions/runs/39571113046), with [recorded evidence](evidence/phase1-ci-39571113046.json). Local Docker execution remains separately unverified.
- Expected failures count as open defects. Removing a marker requires target-phase evidence; an unexpected success fails the verification command and requires review.
- R08 is partially addressed: harness repairs and initial matrix are delivered, while later feature, RLS, concurrency, and acceptance coverage remain outstanding.
- Zero Critical/High findings, explicit Medium risk decisions, named owners, privacy/security/domain acceptance, and recovery evidence remain production gates in the plan.

## Phase 5 document lifecycle (U013)

Implementation and operator procedures: [Phase 5 report](PHASE5_DOCUMENT_LIFECYCLE.md).
New tests cover non-clean scanner outcomes, exact-byte hash/range handling,
container/active-content rejection, storage confinement, four processing crash
points, metadata commit failure/orphans, non-destructive reconciliation, retained
held predecessors, audited DMS correction, archive during slow scan and actual
SQLite/PostgreSQL database-and-blob restore with authorization. Synthetic fixture
scanner is not real malware detection evidence. A separate hosted job requires
real ClamAV and current official definitions; Windows local scanner/symlink skips
remain explicit. Final local and hosted results are recorded in U013/evidence.
D05/D06 and production rollout are separate acceptance gates.

Final Phase 5 source 5516769: full PostgreSQL 128 passed + 2 local skips,
SQLite 116 passed + 14 skips; 130 items collected, 15 subtests each. Final document
selection 29 passed + 2 local skips per backend; explicit PostgreSQL 12 passed,
118 deselected. Hosted run 39613990793 completed success, including real ClamAV
clean/EICAR/current official definitions, service/native PostgreSQL and SQLite.
[Local evidence](evidence/phase5-local.json) and
[hosted observations](evidence/phase5-ci-39613990793.json) retain exact source,
counts/hashes and API state. Local ClamAV and actual Windows symlink privileges,
production ACLs, D05/D06 and operational release acceptance remain separate.

## Phase 6 integration synchronization (U014)

[Contract, state/publication design, owner policy and recovery](PHASE6_INTEGRATION_SYNC.md).
Tests exercise materialized pagination, current-scope minimal removal, capability
and v1 isolation, opaque cursor tamper/cross-token/expiry/retirement, revoked or
inactive owners/departments, rollback, concurrent publication, document/task/review
changes, deferred usage, audited overlapping rotation, rescope/revoke races,
equal timestamps/application restart and genuine PostgreSQL late commits and
writer/snapshot lock waits. Initial checks pass; final evidence is appended after
execution. D07 and production operations remain separate acceptance gates.

Final Phase 6 source 3d5e88a: 151 collected; full PostgreSQL 149 passed + 2 local
skips, SQLite 134 + 17; 15 subtests each. Dedicated Phase 6 PG 21 passed, SQLite
18 + 3 PostgreSQL-only skips. Explicit PostgreSQL 15 passed, 136 deselected.
Materialized history paging and unsupported-isolation/development-owner cases are
included. Hosted 39624468561 passed all four jobs, including real ClamAV and
explicit Phase 6 on service/native PostgreSQL. Final synthetic DB/role counts zero;
legacy-token preservation and read-only status probes passed on both backends.
[Local evidence](evidence/phase6-local.json),
[hosted evidence](evidence/phase6-ci-39624468561.json). D07 and production adoption
remain separate; legacy v1 consumers still need the announced v2 transition.

## Phase 8 frontend/navigation (U016)

[Behavior, recovery contracts and browser limitations](PHASE8_FRONTEND_NAVIGATION.md).
Eight frontend tests exercise true boolean state, noncredential/escaped recovery,
HTML vs API errors, 507 authorized rows beyond the prior cap, stable paging and
export parity/capacity, distinct approval contract counts, stylesheet chart widths,
assignment/revision/capability inbox scope, archive confirmation and readonly tax /
new-activation UI restrictions. Server guards remain independently tested.

Final implementation 6ebcaad has five successful hosted jobs in run 39635885108,
including real Chromium CSP, keyboard/focus, persistent errors and 390/320 CSS-pixel
reflow. Local browser launch is unverified due Windows named-pipe WinError 5; no
permissions or security settings were weakened. Selected static contrast pairs
pass; manual assistive-technology/WCAG/usability acceptance is not inferred.

Local final SQLite: 178 collected, 160 passed + 18 explicit skips, 15 subtests.
Final local PostgreSQL/counter evidence will be appended after execution.
[Hosted metadata](evidence/phase8-ci-39635885108.json); screenshot archives have not
been manually inspected. R21's broader loading/performance and R22 operations
remain Phase 9; no production acceptance or deployment.

Final Phase 8 source 6ebcaad: full PG 176 passed + two local skips; SQLite 160 + 18,
178 collected and 15 passing subtests each. Phase 8 eight passing tests per backend;
explicit PG 16 passed, 162 deselected. Five exact-source hosted jobs passed. Final
catalog: zero harness databases/generated roles, unchanged restricted control role.
[Local evidence](evidence/phase8-local.json). No production/usability acceptance.


## Phase 9 availability work started - U017

Base b962824, guards 1cecc54 and patched dependency source 1649b15 add pre-parser streamed byte/deadline/form/admission controls,
shared database login/API work budgets, synchronous POST workers, pool/export bounds,
private storage quotas, TLS/proxy validation, redacted request correlation and basic
health checks. Additive migration 0021 and actual restricted integration reservations
are covered by tests/test_phase9.py. Full results and evidence will be appended to
[Phase 9 operations](PHASE9_OPERATIONS.md) after local verification finishes.

Phase 9 is **in progress**. Scheduler/jobs, workload targets/optimization, metrics and
alert delivery, encrypted scheduled recovery, identity/MFA policy, broader tool/OS and reproducible release
artifact checks and actual deployment are not verified or delivered
by this first batch. A local implementation commit is not a hosted CI pass: the initial push
failed through the configured network proxy; a normal retry succeeded. Runs 39644065729 (guards) and 39645201928
(patched dependencies 1649b15) passed all five jobs. Existing Phase 8 hosted evidence applies
to its own revision only. No Docker or business DB migration/cleanup was introduced.

U017 final adopted-environment evidence: [phase9-local.json](evidence/phase9-local.json): 199 collected, PG 197 passed/2 skipped; SQLite 181 passed/18 skipped; 15 passing subtests each; explicit PG 16 passed; Phase 9 each backend 21 passed. Zero failures/errors/xfails. Hosted run 39645201928 passed all five jobs for 1649b15; this verifies that source checkpoint, not subsequent operations work or production deployment.


## Phase 9 U018 operations and read-load evidence

Production scan deferral, bounded operator coordinator, crash reservations,
backoff/exhaustion, uploader revocation, archive and non-overlap are covered by
`tests/test_phase9_operations.py`. Windows task/config structural checks and actual
Windows PowerShell parsing are covered by `tests/test_windows_operations.py`.
Statement-scoped RLS equivalence and SQL aggregation are covered by
`tests/test_phase9_queries.py`. CI explicit Phase 9 selections now include these
files as well as existing availability regressions. Actual native service/TLS,
MFA, backup, alert and release acceptance are separate outstanding gates.
Initial workload failures remain in `phase9-workload-before.json` and
`phase9-workload-read-optimized.json`; do not replace them with a success claim.


## Phase 9 U019 human MFA

`tests/test_mfa_codec.py` uses public RFC vectors/disposable keys for encryption,
account binding, tamper rejection, replay/format and rotation.
`tests/test_phase9_mfa.py` covers operator enrollment/recovery, challenge scope,
expiry/throttling, concurrent consumption, ordinary user revocation, service-token
separation, private PostgreSQL tables/functions, missing policy/startup config
and a real synthetic database/seed/audit restore. CI explicit Phase 9 selections
include both. Full SQLite: 244 collected, 219 passed/25 explicit skips, 15 passing
subtests; PostgreSQL/current-source CI results must be appended after completion.
No deployed keys/ACLs/TLS, real identity recovery or encrypted scheduled backup
acceptance is implied by these checks.

U019 final checkpoint ece7797: 244 collected; native PostgreSQL 242 passed/2 local skips; SQLite 219 passed/25 explicit skips; 15 passing subtests each; explicit PostgreSQL 23 passed. All five exact-source hosted jobs passed (39656369586). TOTP implementation technically verified; production custody/deployment and the remaining Phase 9 gates remain open. Evidence in HANDOFF U019 and docs/evidence/phase9-u019-local.json.
