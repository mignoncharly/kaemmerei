# Verification matrix and implementation boundaries

Stand: 2026-10-21. Phase 1 engineering baseline; no business acceptance implied.

Phase 2 update U010: [adopted capability matrix and migration/verification report](PHASE2_AUTHORIZATION.md).
Full local PostgreSQL: 66 passed; SQLite: 65 passed + one PostgreSQL-only skip; 15 subtests passed on both.
All three hosted jobs passed for Phase 2 implementation 9fde6c0. Current Phase 3 evidence: [database security report](PHASE3_DATABASE_SECURITY.md). Content-bound approvals remain Phase 4 work.

Phase 3 U011: PostgreSQL 81 passed; SQLite 69 passed + 12 PostgreSQL-only skips;
15 passing subtests per full suite. Explicit PostgreSQL selection: 12 passed, zero
skips. Hosted run 39600834032 passed all three jobs for 5986a74. No production acceptance.

## Permission regression matrix

The desired rules below are implementation targets with current evidence identified individually. Future content-bound approval, delegation and retention capabilities remain open. `Expected failure` means the desired assertion currently fails and remains an OPEN finding. A setup/migration/transport failure is not an acceptable expected failure.

| Case | Principal / resource | Desired result | Current evidence or pending phase |
|---|---|---|---|
| V01 | Guest -> list/detail/export/document/API | Login redirect for HTML; API 401; no business data | Original guest test covers list/create; API credentials test covers missing auth. Other guest endpoints extend in P2/P6. |
| V02 | Own-department writer -> own contract | Read/create/edit/archive under version and CSRF rules | Original isolation, CRUD/conflict, CSRF tests |
| V03 | Department writer -> other department contract | No read/write; forged posted department cannot change ownership | Original ownership/direct mutation tests |
| V04 | Department writer -> other department metadata | No private names/types from dropdown queries | R01 passing on SQLite/PostgreSQL; acceptance test also covers searches, reports, export, API and documents |
| V05 | Admin -> all department contracts | Authorized read/write; explicit department selected | Original search/filter and CRUD tests |
| V06 | Reviewer -> all contracts | Read permitted, normal contract/task/document writes forbidden | Original reviewer test and new child-permission test |
| V07 | Reviewer -> review decision | Forbidden without explicit approval capability/assignment | Passing Phase 2: default reviewer denied; capability + membership alone denied; only explicitly assigned authorized user can decide |
| V08 | Authorized approver -> assigned current-content review | Only allowed transitions/reasons/version; no unrelated decision | Phase 2 capability/membership/assignment/read-scope gate passes. Content version and full transition policy remain Phase 4. |
| V09 | Wrong approver/self-approver -> decision | Denied under accepted separation-of-duty rules | Phase 4 after D01/D02/D04 |
| V10 | Inactive account -> login | 401; no authenticated session | New inactive-user test |
| V11 | Active account in inactive department -> protected access | Access denied/session invalidated consistently | R10 passing: existing session, fresh login, reads/writes and scoped tokens rejected |
| V12 | Any user -> forged child under different parent | 404 regardless of guessed child identifier | Shared parent/child loader; task/document/API mismatch regressions and assignment parent authorization pass |
| V13 | Other-department writer -> tasks/reviews/uploads/DMS link | No child creation or information exposure | New child-permission test |
| V14 | Admin -> upload/preview/download/API document | Only its application instance's private storage used | New end-to-end storage test, including a second isolated app |
| V15 | Scoped token -> contracts | Only token's department | New scoped-token test |
| V16 | Unscoped token -> contracts | Explicitly authorized global read | New unscoped-token test; narrower field capabilities Phase 6 |
| V17 | Expired/revoked/invalid/missing token | 401 consistently | New token test |
| V18 | Token -> wrong department or mismatched document parent | 404; no file bytes | Passing acceptance regression on SQLite/PostgreSQL; wider capability matrix remains Phase 6 |
| V19 | Any authorized writer -> archived aggregate | No contract or child mutation | R04 passing: admin/reviewer updates rejected; persisted review/history unchanged. Broader concurrency remains Phase 4. |
| V20 | Concurrent task/review/archive -> same aggregate | Consistent versioned outcome; no lost decision | Phase 4 PostgreSQL concurrency checks |
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
