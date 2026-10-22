# Remediation plan — 10 implementation phases

U023 local candidate `af290a4`: PostgreSQL 362 passed/2 skips, SQLite 328 passed/36 skips, 15 subtests each; representative mixed load and encrypted recovery passed. [Final evidence and exact remaining actions](docs/U023_CANDIDATE_VERIFICATION.md). Earlier connection-timeout failure retained. Hosted CI/actual native patch, browser/scanner/host and participant gates remain open; no real-data or production authorization.

U022 final local verification: implementation `05648ed`, PostgreSQL 343 passed/2 skips, SQLite 309 passed/36 skips, 15 subtests each; full representative mixed workload and encrypted restore passed. [Exact evidence, scope and remaining release gates](docs/U022_ENGINEERING_VERIFICATION.md). Synthetic scope approval is separate from actual-host/participant acceptance and real-data/production authorization.

Baseline date: 2026-10-20\
Project: OPEN.HERZ Vertragsregister\
Plan status: Phases 1-8 technically verified; Phase 9 in progress through U022; Phase 10 preparation continues. Approved synthetic pilot decisions are recorded in docs/PILOT_DECISIONS.md. Current-source evidence is in HANDOFF; real-data and production authorization remain separate and ungranted.\
State and update history: [HANDOFF.md](HANDOFF.md)

## 1. Purpose and evidence

Bring the existing FastAPI/SQLAlchemy/Jinja application from a functional working version to a controlled pilot, then to an explicitly accepted production release. Preserve contract records, document references, revision history, and existing access boundaries throughout migration.

This plan follows a static review of application code, templates, JavaScript, models, all 13 Alembic migrations, tests, [README.md](README.md), and [docs/ARBEITSPLAN.md](docs/ARBEITSPLAN.md). The review did not execute tests, inspect business records, evaluate a running deployment, or validate PostgreSQL migrations. Findings are source observations and reasoned failure paths, not penetration-test results. No critical exploit was confirmed. High findings are production blockers until corrected and verified.

The documents' statement that F1–F15 are implemented describes broad functional coverage. It does not establish workflow correctness, production readiness, or completion of external integrations. Phase 1 replaces that ambiguity with explicit acceptance criteria.

### Delivery rules

- Use the task IDs below in changes, verification evidence, and handoffs. Each task is an independently reviewable work item; combine tasks only when their migrations or transactions are inseparable.
- Preserve existing applied migrations. Add forward migrations after `0013_integration_tokens`; allocate each new revision against the actual repository head when implementation starts. Repair defects through new migrations.
- Inspect the current code before acting: line numbers in the original review are a baseline, not permanent identifiers.
- Use synthetic fixtures for automated verification. Never copy production documents, passwords, tokens, or personal data into tests, logs, or handoffs.
- Separate migration ownership from application database privileges. Test migrations against both a clean database and a representative upgrade fixture.
- Require a backup and a verified recovery path before migrations against business data. Prefer a forward repair or database-and-document restore over an unsafe downgrade.
- Update HANDOFF after each completed work session and material state change, including failed verification and partially completed work. A checked implementation task does not imply verified acceptance.
- Do not silently weaken authorization, archive protection, CSRF, audit integrity, or content security policy to make another feature work.
- Mark external dependencies explicitly. Missing city decisions can block the affected release gate; they should not stop unrelated authorized implementation work.

## 2. Severity and release policy

| Level | Meaning | Release treatment |
|---|---|---|
| Critical | Confirmed path to severe compromise or widespread unauthorized access | Stop release; contain and fix immediately. None confirmed at baseline. |
| High | Material authorization, integrity, availability, synchronization, or verification defect | Must be fixed and verified before production; normally before a business-data pilot. |
| Medium | Significant weakness, incorrect behavior, or missing control with narrower/preconditioned impact | Resolve before production or obtain a named, dated, time-limited risk acceptance. |
| Nice to fix/have | Maintainability, convenience, or optional capability | May remain in a tracked backlog with scope explicitly documented. |

A release requires zero unresolved Critical/High findings. Optional integrations may remain excluded when the accepted release scope explicitly says so. An out-of-scope integration cannot be advertised as delivered.

## 3. Findings register and coverage

IDs stabilize the review findings for implementation tracking. Related findings can share one implementation task, but each must have its own closure evidence.

| ID | Severity | Finding / gap | Primary phase |
|---|---|---|---|
| R01 | High | Cross-department contract metadata in filter dropdowns — corrected/verified U009 | 2 |
| R02 | High | Application capability/recipient assignment corrected U010; broader decision policy remains Phase 4 | 2, 4 |
| R03 | High | Decisions not bound to content/version; no enforced activation gate | 4 |
| R04 | High | Reviews remain editable after archival — corrected/verified U009 | 4 |
| R05 | High | Incremental API misses document changes, scope removals, and stable pagination | 6 |
| R06 | High | Historical totals exclude currently archived/transferred populations | 7 |
| R07 | High | Request limits, login limits, session growth, and blocking async work | 9 |
| R08 | High | Broken test helper/assertions; major feature and production-database coverage gaps | 1, all phases |
| R09 | Medium | No database RLS; authorization entirely application-enforced | 3 |
| R10 | Medium | Inactive departments retain inconsistent access — corrected/verified U009 | 2 |
| R11 | Medium | Child updates lack conflict checks and atomic archive protection | 4 |
| R12 | Medium | Stale tax completion metadata and review validity | 4 |
| R13 | Medium | Missing administrative/access audit events and append-only protection | 3, 9 |
| R14 | Medium | Missing tax reviewer foreign key and business constraints | 3 |
| R15 | Medium | Signature-only document validation; no quarantine/scanning | 5 |
| R16 | Medium | File/database crash consistency, checksums, and reconciliation absent | 5 |
| R17 | Medium | Unknown financial direction counted as expense; unclear report population | 7 |
| R18 | Medium | Net/gross basis not recorded for financial amounts | 7 |
| R19 | Medium | Date arithmetic boundaries and Excel overflow failures | 7 |
| R20 | Medium | Terminated contract renewal display differs from dashboard | 7 |
| R21 | Medium | Unbounded data loading/export; 500-row list truncation | 8, 9 |
| R22 | Medium | Deployment, TLS, monitoring, backup, and scheduled maintenance unimplemented | 9, 10 |
| R23 | Medium | Inline chart widths conflict with CSP | 8 |
| R24 | Medium | Failed form rendering treats string `0` as checked | 8 |
| R25 | Medium | Validation errors disappear automatically | 8 |
| R26 | Medium | Raw JSON errors interrupt HTML form flows | 8 |
| R27 | Medium | Dashboard approval count counts reviews rather than contracts | 8 |
| R28 | Medium | Corrupted German validation messages | 8 |
| R29 | Scope gap | No H&H, LDAP/SSO, or product-specific DMS adapter | 10 |
| R30 | Scope gap | No scheduled delivery/escalation of reminders | 9, 10 |
| R31 | Scope gap | Maintained scoped contact catalog delivered U010; labels never grant access or delegation | 2 |
| R32 | Scope gap | Audited department lifecycle delivered U010 | 2 |
| R33 | Scope gap | Retention, legal hold, deletion/anonymization, document disposal absent | 5, 10 |
| R34 | Scope gap | Password change/recovery delivered U010; MFA/SSO remains Phase 9 | 2, 9 |
| R35 | Scope gap | Excel creates records only; numbers ignored; no update/round-trip contract | 7 |
| R36 | Scope gap | API omits tax, tasks, decisions, and revision history | 6, 10 |
| R37 | Nice | Duplicated query/permission code and oversized main module | 1, 2 |
| R38 | Nice | Missing filter-preserving navigation, sorting, and personal inbox | 8 |
| R39 | Nice | No document correction/supersession workflow | 5 |
| R40 | Nice | Temporary package files and duplicate environments in workspace/distribution | 9 |
| R42 (new U017) | High | Maintainer framework/parser advisories identified U017; compatible patched dependencies and 28-package runtime OSV review verified for 1649b15; broader release checks remain | 9 (P09-T11) |
| R41 | Nice | Token owner, rotation, and deactivation semantics unspecified | 6 |
| R43 (new U022) | High release gate | Observed native PostgreSQL 18.3 server/client is in official affected ranges. Production security floors added; actual patched host/client verification and applicability review remain open. No exploit confirmed; see docs/NATIVE_SECURITY_BASELINE.md. | 9, 10 |

Scope gaps become release blockers when required by the accepted release scope. Record that decision rather than assigning them an unsupported vulnerability severity.

## 4. Implementation sequence and owners

Owner names must be assigned before business-data pilot approval. Roles below are accountability placeholders, not named approvals.

| Phase | Outcome | Dependencies | Accountable roles |
|---|---|---|---|
| 1 | Reproducible baseline and repaired verification foundation | None | Engineering, QA, product owner |
| 2 | Consistent application authorization and identity administration | 1 | Engineering, Kämmerei, IT identity owner |
| 3 | Constrained schema, database roles, RLS, protected audit storage | 1, 2 policy | Engineering, DBA, security |
| 4 | Versioned approvals, archive integrity, concurrency safety | 2, 3 | Engineering, Kämmerei, approval owners |
| 5 | Safe document lifecycle and recovery | 3, 4 mutation protocol | Engineering, IT operations, records/privacy owners |
| 6 | Reliable scoped integration/change API | 2–5 relevant schema/events | Engineering, integration owner |
| 7 | Correct financial history, deadlines, and Excel semantics | 3, 4 event contract | Engineering, finance/domain owners |
| 8 | Correct, usable frontend and bounded navigation | 2, 4–7 interfaces | Engineering, UX/accessibility, QA |
| 9 | Availability, observability, deployment, and maintenance controls | 1–8 relevant interfaces | Engineering, operations, security |
| 10 | Acceptance, explicit exclusions, recovery rehearsal, release | 1–9 gates | Product owner, IT, privacy, domain owners |

Small independent work can proceed once its listed interface is stable. Keep the completion order and dependencies visible in HANDOFF. Do not label a phase complete while required verification remains unperformed.

## Phase 1 — Establish the baseline and repair verification

**Priority:** High. **Findings:** R08, R37. **Entry:** Existing source available.

**Current acceptance update (U009, 2026-10-21):** P01-T01–T08 verification now includes native Windows PostgreSQL 18: 44 pytest items passed, no failures/skips/xfails, 15 subtests passed; SQLite has 43 passed and one PostgreSQL-specific skip. R01/R04/R10 are corrected and covered by normal passing regressions. Clean/populated migrations, real application lifecycle and positive-identity cleanup pass. Operator confirmed nonblocking Windows startup; an agent repeat was stopped by owner-only ACL enforcement. Hosted evidence, commands and limitations: [acceptance report](docs/PHASE1_BASELINE.md), [matrix](docs/VERIFICATION_MATRIX.md), HANDOFF U009. Later-phase scope and production approval remain open.

**Historical implementation update (U006):** P01-T01–T08 delivered with 22 stdlib checks (19 passed, 3 expected failures). [Linux CI run 39571113046](https://github.com/mignoncharly/kaemmerei/actions/runs/39571113046) passed SQLite/PostgreSQL and direct pytest. At that point Windows error 87 and R01/R04/R10 were still open; U009 supersedes those statuses. Earlier [CI record](docs/evidence/phase1-ci-39571113046.json) is retained.

### Tasks

- [x] P01-T01: Record source revision if version control is available, Python/runtime versions, dependency manifests, migration head, and supported operating environments. Inventory tracked/untracked artifacts without exposing secrets. Record unavailable evidence explicitly.
- [x] P01-T02: Correct `tests/conftest.py::create_contract` using URL parsing of `Location` before extracting the ID. Replace obsolete `archived=1` assertions with the supported status filter. Keep test assertions focused on behavior.
- [x] P01-T03: Give tests isolated database, document storage, and configuration paths. Move document-storage configuration into the application settings/application instance so tests cannot write into the regular document directory through module globals.
- [x] P01-T04: Establish a regression matrix for guest, own-department writer, other-department writer, read-only viewer/reviewer, authorized approver, admin, inactive user/department, and scoped/unscoped/revoked/expired token. Include parent and child resource IDs and forged form fields.
- [x] P01-T05: Create PostgreSQL integration-test configuration using disposable databases and migration execution. Keep a fast SQLite suite, but do not use `Base.metadata.create_all` as migration verification.
- [x] P01-T06: Add verification jobs for clean migration to head, populated upgrade from baseline, application regression tests, and production configuration failure cases. Record exact commands and exit results when executed; never imply unrun checks passed.
- [x] P01-T07: Define domain/service boundaries for authorization, contract mutations, workflow, documents, reporting, and integrations. Extract only what subsequent tasks need; preserve route compatibility and avoid a large unrelated rewrite.
- [x] P01-T08: Rewrite the status statement in README/ARBEITSPLAN to distinguish implemented prototype behavior, known defects, accepted exclusions, and release gates. Keep their German language and cross-link this plan and HANDOFF.

### Verification and exit criteria

- Original CRUD/authentication tests collect and pass after harness repairs, or every remaining failure has a recorded cause and remediation task.
- Test artifacts remain inside disposable directories; no business database or regular document storage is touched.
- CI or a documented equivalent executes an actual Alembic upgrade on PostgreSQL.
- The regression matrix and release criteria are reviewed; initial failures are captured as evidence rather than hidden.

**Recovery:** Documentation/test refactors are reversible. Do not modify business schemas in this phase.\
**Handoff:** Record baseline commands, actual results, environment limitations, and the first authorization task to implement.

## Phase 2 — Enforce application authorization and manage identities

**Priority:** High. **Findings:** R01, R02, R10, R31, R32, R34, R37. **Entry:** Phase 1 baseline.

**Implementation update (U010, 2026-10-21):** P02-T01-T08 implemented. Local PostgreSQL: 66 passed, no failures/skips/xfails; SQLite: 65 passed and one PostgreSQL-only skip; both have 15 passing subtests. Final targeted Phase 2 PostgreSQL: 21 passed. Forward migration `0014_identity_authorization` preserves existing display values and grants no automatic approval. Adopted matrix, migration mappings, hosted evidence and policy boundaries: [Phase 2 report](docs/PHASE2_AUTHORIZATION.md). Technical defaults D01/D02 still require municipal acceptance; no business deployment or production approval.

### Tasks

- [x] P02-T01: Define a capability matrix. Keep existing `reviewer` read-only by default; introduce explicit approval capability and recipient membership rather than granting approval to all reviewers. Do not migrate existing reviewers into approvers automatically. Preserve administrators' documented powers while auditing decisions.
- [x] P02-T02: Centralize authorized contract queries and parent/child loading. Apply them to list, export, report, search suggestions, metadata dropdowns, documents, history, tasks, review inboxes, and APIs. Resolve both parent authorization and child ownership before returning data.
- [x] P02-T03: Fix unrestricted `stored_types` and `stored_people` queries. Distinguish deliberately shared reference catalogs from metadata derived from private contracts. Scope the latter to visible records, including an explicit archival policy.
- [x] P02-T04: Define department deactivation: deny department-user login and protected access when their department is inactive; revoke their sessions. Suspend department-scoped tokens consistently. Provide audited admin rename/deactivate/reactivate operations; prevent orphaning users or records.
- [x] P02-T05: Add maintained contact identities/catalogs with active state and optional user relationship. Preserve existing display names during backfill. A responsible/deputy label must not implicitly grant access. Specify approved, time-bounded delegation separately if required.
- [x] P02-T06: Implement recipient teams/membership and explicit review assignment. A user can see/act on an assigned review only under documented access rules. Cross-department assignments require a deliberate read grant or a globally authorized approver; a label alone must not reveal the contract.
- [x] P02-T07: Add authenticated self-service password change requiring the existing password, CSRF, password policy, session rotation/revocation, and an audit event. Add audited admin recovery/reset with forced change on first use; do not send passwords in application logs.
- [x] P02-T08: Reuse validation between CLI and web administration. Enforce department-role consistency, immutable/stable identity IDs, last-admin protection under concurrent changes, and session revocation on relevant permission changes.

### Verification and exit criteria

- A department-B-only type/contact does not appear anywhere in department A's response HTML, exports, suggestions, or derived lists.
- Guest, read-only, inactive, and other-department users cannot mutate any protected parent or child resource through direct POSTs.
- Existing reviewers retain read access but cannot approve without explicit assignment/capability.
- Department suspension, reactivation, membership changes, and password changes have consistent session behavior and audit evidence.
- Existing contact names remain readable after migration; delegation decisions are recorded in HANDOFF.

**Recovery:** Backfill contacts additively and preserve legacy display values until verified. Never restore broad reviewer approval as a rollback shortcut.\
**Handoff:** Attach the adopted matrix, migration mappings, and outstanding domain decisions.

## Phase 3 — Add database constraints, least privilege, and RLS

**Priority:** Medium findings; production control foundation. **Findings:** R09, R13, R14. **Entry:** Phase 2 capability matrix.

### Tasks

- [x] P03-T01: Compare migrated PostgreSQL and SQLite schemas against models. Inventory invalid legacy rows before constraints. Add the missing tax-reviewer foreign key through a forward migration; preserve valid historical identities and define handling of missing references.
- [x] P03-T02: Add constraints for role/department consistency, valid tax/review/payment/direction states, nonnegative amounts, date order, supported month ranges, positive versions, and automatic-renewal prerequisites. Require exactly one document source where applicable. Clean invalid rows through reviewed mappings, never silent deletion or invented financial values.
- [x] P03-T03: Separate migration/owner, web application, maintenance worker, and integration access roles as appropriate. Production application connections must not be superuser, table owner, or `BYPASSRLS`. Document grants and deny direct mutation of immutable history/audit records.
- [x] P03-T04: Implement PostgreSQL RLS for contracts and related documents, tasks, reviews, revisions, and change-feed visibility. Enforce parent ownership through policies. Support explicitly authorized global readers/admins, scoped department users, assigned grants, and integration principals. Use both visibility (`USING`) and write checks (`WITH CHECK`). Apply `FORCE ROW LEVEL SECURITY` where required by the owner model.
- [x] P03-T05: Design authentication bootstrap separately from business-data access. Session/token resolution must expose only the minimum credential/principal data needed. If narrow SECURITY DEFINER functions are used, fix their search path, restrict execution, qualify objects, and review ownership. Do not grant general credential-table reads to integration consumers.
- [x] P03-T06: Set validated request identity and capability context transaction-locally on the same connection used by protected queries. Default to denial when context is missing or invalid. Reset on rollback/commit and verify pooled connection reuse. Adjust current mid-request commits so context cannot disappear before subsequent reads.
- [x] P03-T07: Create append-only audit/event persistence with separate ownership and restricted insert paths. Store stable actor IDs, principal type, action, target, timestamp, outcome, correlation ID, and safe change metadata. Protect writes against application-role update/delete.
- [x] P03-T08: Document the SQLite boundary: local development relies on application authorization and cannot satisfy the PostgreSQL RLS gate. Document that shared-role RLS context is defense against omitted filters, not a security boundary against an attacker holding unrestricted application SQL execution or database credentials.

### Verification and exit criteria

- Tests using the actual application database role cannot read or write another department's data with deliberately unscoped SQL.
- Direct child-table queries, joins, updates that move departments, missing identity, and malformed context are denied appropriately.
- Alternating principals through one pool does not leak previous identity; bootstrap, token usage, audit insertion, and post-commit reads work under real grants.
- Clean and populated upgrade migrations pass; constraints reject invalid writes; ORM and migrated schemas have no unexplained differences.
- Audit update/delete attempts fail under application roles. Maintenance and backup jobs have explicitly reviewed permissions.

**Recovery:** Restore the application and schema as a compatible pair if needed. Never disable RLS or grant owner privileges to resolve an application error. Preserve a tested migration recovery procedure.\
**Handoff:** Record role names, policy coverage, bootstrap design, constraint repairs, and verification identities without credentials.

## Phase 4 — Protect approval, tax, archive, and concurrent mutations

**Priority:** High. **Findings:** R02–R04, R11, R12. **Entry:** Phases 2–3.

### Tasks

- [x] P04-T01: Create a single contract mutation protocol: authorize, lock/reload parent, verify expected version and archive state, mutate, record revision/audit/change events, then commit once. Child writes must participate in the same transaction and archive lock. Use PostgreSQL row locks; define an equivalent safe SQLite development path.
- [x] P04-T02: Keep the existing edit version for optimistic conflicts and add a content revision representing the material contract/document state. Define exactly which financial, party, date, tax-relevant, and document changes increment content revision. Workflow commentary alone must not invalidate itself.
- [x] P04-T03: Bind each approval decision to content revision, request, assigned recipient, actor, and decision timestamp. Define allowed transitions, authorized actors, required reasons, and reopening/withdrawal rules. Prevent accidental self-approval where the accepted policy requires separation of duties.
- [x] P04-T04: Implement the approved activation policy. Default pilot behavior: active status requires the configured mandatory approvals for the current content revision; legacy active contracts retain an explicit legacy/unverified marker until reviewed. Allow exceptions only through a named, audited capability with a reason.
- [x] P04-T05: On material changes, supersede affected approvals and require re-review. Preserve old decisions and their content references. Reopening tax review clears current completion metadata while preserving prior completion in history; only authorized tax capability can complete an assessment.
- [x] P04-T06: Add expected-version conflict protection to task/review edits. Preserve submitted values on conflict and provide a clear reload/reconcile flow. Prevent duplicate submission where a repeated request would create a second workflow action.
- [x] P04-T07: Make archived aggregates immutable through all normal mutation paths, including review decisions, document links, tasks, and background jobs. Hide editing controls. Any future archive correction must be a separate authorized, audited procedure, not an incidental endpoint bypass.
- [x] P04-T08: Backfill legacy review/tax state as unverified provenance where revision binding cannot be established. Do not claim an old decision approved today's content. Include a report of records needing reconciliation.

### Verification and exit criteria

- Approve revision N, edit a material field or add a material document, and confirm the old approval cannot authorize revision N+1.
- Two concurrent decisions/task edits do not silently overwrite each other.
- Archive racing with every child mutation produces one consistent authorized outcome; no mutation commits after the archive barrier.
- Reviewer, wrong-recipient, self-approval, missing-reason, stale-version, and unauthorized activation attempts are rejected.
- Reopening/recompleting tax assessment displays correct current metadata and preserves historical evidence.

**Recovery:** Use additive fields and explicit legacy states. A rollback must not reactivate stale approvals or bypass archive protection.\
**Handoff:** Record the state machine, material-field definition, legacy reconciliation count, and concurrency evidence.

## Phase 5 — Secure document storage and lifecycle

**Priority:** Medium; required before trusting business uploads. **Findings:** R15, R16, R33, R39. **Entry:** Phase 4 mutation protocol.

### Tasks

- [x] P05-T01: Move storage configuration into validated application settings. Keep private storage outside static/web roots. Verify resolved file paths remain under the configured storage root; require approved storage-key format and least-privilege filesystem access.
- [x] P05-T02: Add document state (`pending`, `quarantined`, `available`, `rejected`, `superseded`, `disposed` as needed), content digest, verified media type, scan result/version/time, and provenance. Existing unscanned files must be marked accordingly, not silently trusted.
- [x] P05-T03: Validate container contents for Office/OpenDocument uploads rather than accepting any ZIP prefix. Define the accepted macro/active-content policy. Integrate a maintained malware scanner and quarantine workflow; scanner failure must leave new files unavailable pending retry or explicit policy handling.
- [x] P05-T04: Implement recoverable file staging. Persist a pending metadata/job record and deterministic storage operation; make finalization/scanning retryable and idempotent. Expose only finalized clean content. Reconcile abandoned staging, orphan files, missing blobs, and digest mismatches without deleting unclassified files automatically.
- [x] P05-T05: Apply authorization and availability state checks to preview, download, API download, and range requests. Log permitted/denied access as required without logging document contents, raw tokens, or sensitive URLs. Consider a separate preview origin/sandbox for active formats according to security review.
- [x] P05-T06: Add audited replacement/supersession of documents and correction of DMS links. Preserve prior versions and invalidate affected approvals. External URLs remain links unless an explicitly scoped connector is implemented; use HTTP(S) validation and an approved DMS-domain policy if required.
- [x] P05-T07: Design retention classification, legal holds, disposal eligibility, authorized approval, deletion/anonymization jobs, and audit evidence. Cover blobs, metadata, revision snapshots, audit records, exports, backups, and external DMS ownership. Implement only approved retention rules; default to no destructive automatic disposal while those decisions are pending.
- [x] P05-T08: Document consistent database/document backup and restore, shared storage requirements for multiple workers, capacity monitoring, and integrity reconciliation commands.

### Verification and exit criteria

- Disguised ZIP containers, disallowed active content, rejected scans, and pending documents cannot be downloaded or previewed.
- Fault injection at staging, scanning, blob finalization, and database commit leaves recoverable states with no accessible uncommitted content.
- Reconciliation reports missing/orphan/mismatched content; repeated recovery jobs are safe.
- Supersession preserves evidence; holds prevent disposal. Restore recovers document hashes and matching authorized metadata.

**Recovery:** Preserve original blobs and mappings until migration and recovery verification complete. Scanner outage must not open quarantine. Destructive disposal requires the approved retention gate.\
**Handoff:** Record storage/scan policy, legacy-file status, recovery results, and retention decisions.

## Phase 6 — Make integration synchronization reliable

**Priority:** High. **Findings:** R05, R36, R41. **Entry:** Identity scope and aggregate event contracts from Phases 2–5.

### Tasks

- [x] P06-T01: Specify the API compatibility contract. Keep v1 available during an announced transition; introduce v2 if cursor/event semantics or fields would break existing consumers. Document included fields, permissions, errors, timestamps, retention, and removal semantics.
- [x] P06-T02: Emit aggregate change events transactionally for contract, document availability/link/supersession, archive, review/tax, and relevant task changes. Update aggregate `updated_at` in the same mutation transaction where v1 relies on it.
- [x] P06-T03: Implement stable event cursors and an initial-snapshot handshake. Do not use a raw sequence allocation as a commit-order watermark: concurrent transactions can commit out of order. Use a proven serialized publication stage/outbox publisher that assigns externally visible sequence numbers after committed changes, with idempotent publication and a resumable snapshot boundary.
- [x] P06-T04: Persist old/new department scope and minimal removal events on transfer, deletion/disposal, or grant changes. A former scope receives only the identifier and removal reason needed to purge its copy, never the new department or private payload. Explain how consumers reconcile access changes and expired event history through a fresh snapshot.
- [x] P06-T05: Bind opaque cursors to token/principal scope and API version; reject tampering and cross-scope reuse. Recheck current token and authorization state on each request. Specify behavior for concurrent snapshot changes, event replay, duplicates, and revoked access.
- [x] P06-T06: Define endpoint/field capabilities for metadata, finance, documents, tax, tasks, and decision/history access. Add omitted fields/endpoints only where accepted scope requires them; do not expand every existing token automatically.
- [x] P06-T07: Add token ownership, accountable service owner, expiry/rotation, explicit scopes, revocation reason, and audit trail. Use overlapping rotation where needed. Decide whether a disabled creator suspends a service token; avoid undocumented inheritance from personal account status.
- [x] P06-T08: Avoid committing a token usage timestamp before business reads. Batch or independently record last-used metadata so read requests do not create avoidable write contention or erase RLS transaction context.

### Verification and exit criteria

- A consumer synchronizes an initial snapshot, then sees a document-only change without a manual contract edit.
- Department A receives a removal after transfer; department B receives authorized content; A's event reveals no B-only data.
- Concurrent commits, updates during pagination, retries, equal timestamps, consumer restart, and retention expiry cause no silent omissions.
- Revoked/expired/suspended tokens fail consistently; cursors cannot cross scopes; v1 compatibility is verified.
- API examples and schema describe actual supported fields, scope, and removal behavior.

**Recovery:** Keep v1 and event replay available through migration. Never reset cursors silently; require explicit resynchronization when necessary.\
**Handoff:** Record versioning choice, cursor/publication design, event retention, token policy, and consumer recovery evidence.

## Phase 7 — Correct financial reports, dates, and Excel interchange

**Priority:** High for history; Medium for associated correctness. **Findings:** R06, R17–R20, R35. **Entry:** Schema/event foundations.

### Tasks

- [ ] P07-T01: Agree report definitions with finance: inventory vs committed spending vs actual payments, qualifying statuses, relevant dates, department attribution, annualization, and unknown values. Existing annual amounts are contract metadata, not evidence of cash payments.
- [x] P07-T02: Add explicit financial value basis (`net`, `gross`, `unknown`), currency if required, and effective dates for financial changes where needed. Preserve legacy values as unknown. Do not infer tax basis or convert historical amounts without evidence.
- [x] P07-T03: Rebuild historical totals from event/snapshot populations including archived and transferred contracts. Use department and financial direction at the historical instant. Distinguish recorded-at history from effective-at business history and disclose which report is available. Do not fabricate years predating evidence.
- [x] P07-T04: Treat unknown direction/basis separately. Define inclusion/exclusion of drafts, terminated/ended, future-start, and archived records for each report. Expose missing-data counts and reconciliation differences instead of coercing unknowns to zero or expense.
- [x] P07-T05: Centralize renewal/notice computation for list, details, reports, and API. Specify month-end/leap-year rules, original-date anchoring, notice-to-end relationships, terminated behavior, and missed-notice treatment. Keep display dates distinct from a legal conclusion that cancellation remains possible.
- [x] P07-T06: Validate supported date ranges and arithmetic results before persisting. Catch Excel/date overflow, non-finite numeric dates, impossible renewal outcomes, and malformed cells as row-level errors. Verify supported workbook date systems or reject unsupported systems explicitly; never silently interpret 1904 dates as 1900 dates.
- [x] P07-T07: Define Excel as create-only or an explicit controlled update mode. For create-only, clearly identify generated numbers and preserve an optional external reference; do not silently ignore a user-supplied identity column. For update mode, require authorized record identity, expected version, preview/diff, and conflict handling.
- [x] P07-T08: Make duplicate detection scoped, deterministic, and concurrency-safe according to the accepted identity rule. Natural duplicates can be legitimate: flag ambiguity instead of making an overly broad uniqueness constraint. Preserve all-or-nothing import behavior and audit provenance.
- [x] P07-T09: Keep string-safe XLSX export, bounded parsing, and ZIP limits. Add representative workbook fixtures for shared strings, formulas/cached values, duplicate headers, dates, invalid references, Unicode, numeric boundaries, and export/import expectations. Explain that Excel is not a backup of documents/history.

### Verification and exit criteria

- A prior-year contract still contributes to that year's accepted report after archival today; a transfer does not rewrite its former department attribution.
- Unknown direction/basis is visible and does not silently inflate expenses; report totals reconcile to an explicit fixture ledger.
- Leap days, month ends, termination, past notice dates, and min/max supported dates agree across views and cannot crash them.
- Invalid Excel dates/rows produce actionable errors with zero partial writes. Concurrent imports and record identity rules behave as specified.

**Recovery:** Preserve existing financial values and raw import provenance; publish report-definition changes. Version revised report semantics where users depend on prior exports.\
**Handoff:** Attach finance-approved definitions, known history gaps, reconciliation evidence, and Excel compatibility decisions.

**Phase 7 implementation note (U015):** P07-T02-T09 use explicit proposed technical defaults in [Phase 7 report](docs/PHASE7_FINANCE_DATES_EXCEL.md). P07-T01 remains unchecked because finance agreement has not been obtained. Final evidence: 170 collected; PG 168 passed + 2 local skips; SQLite 152 + 18; Phase 7 PG 19/19; all four hosted jobs passed for 2fd1bf8. See HANDOFF U015. Technical verification is separate from owner acceptance.

## Phase 8 — Repair frontend behavior and navigation

**Priority:** Medium. **Findings:** R21, R23–R28, R38. **Entry:** Stable service interfaces.

### Tasks

- [x] P08-T01: Remove inline chart styles using CSP-compatible markup, such as a stylesheet-backed percentage class set with bounded integer values. Keep the restrictive policy. Present exact values in accessible text/table form independent of bar graphics.
- [x] P08-T02: Normalize submitted booleans before rendering forms; avoid truth-testing raw strings. Preserve unchecked, checked, selected, empty, zero, and validation-error states correctly for contract and account forms.
- [x] P08-T03: Keep errors until correction or explicit dismissal. Success messages may expire when appropriate; give users time and an accessible announcement. Never hide substantive failure information automatically.
- [x] P08-T04: Add consistent HTML validation, permission, not-found, conflict, expired-session/CSRF, and upload error pages. Preserve safe entered values, provide recovery actions, and never echo passwords/tokens. Keep JSON errors for API clients through an explicit route/content contract.
- [x] P08-T05: Count distinct contracts on the approvals dashboard or relabel the metric as review count. Align labels and filters for tax assessment, contract lifecycle, and approval state. Show archived immutability and revision validity clearly.
- [x] P08-T06: Add server-side pagination, total count, stable sort/tiebreaker, query bounds, and filter-preserving links. Remove unreachable records behind the 500-item cap. Ensure export uses the same authorized filter specification, with its own capacity limits.
- [x] P08-T07: Add a personal task/review inbox based on actual assignment and capability. Include overdue review deadlines, not just contract dates/tasks. Avoid an inbox that grants broader contract visibility.
- [x] P08-T08: Repair German encoding/text corruption. Review role labels, activation/approval messages, UTC/local-time presentation, archive statements, and financial descriptions against implemented behavior.
- [x] P08-T09: Perform keyboard, screen-reader structure, focus, contrast, responsive layout, long-content, and validation recovery checks. Add an archive confirmation/recovery policy appropriate to its effect; preserve CSRF and version checks.

### Verification and exit criteria

- Chart widths render under the actual CSP without inline-style violations; values remain usable without graphics.
- Unchecked booleans remain unchecked after validation errors; accounts are never activated accidentally by rerendering.
- Errors persist and entered non-secret values survive validation/conflict recovery.
- Counts equal the destination population; every authorized record is reachable through pagination with filters intact.
- Read-only/archived/unauthorized users see controls consistent with server enforcement; direct requests remain independently protected.

**Recovery:** Keep service contracts stable; frontend rollback cannot remove server checks or weaken CSP.\
**Handoff:** Record browser/accessibility evidence, pagination contract, and remaining usability limitations.

**Phase 8 implementation note (U016):** P08-T01-T09 technically verified for source 6ebcaad. Final local 178 collected: PG 176 passed + 2 local skips; SQLite 160 + 18; 15 subtests each. Eight Phase 8 tests pass on both backends. All five hosted jobs, including real Chromium, passed. See [Phase 8 report](docs/PHASE8_FRONTEND_NAVIGATION.md). Local browser and manual AT/usability/production acceptance remain separate. R21 broader workload controls remain Phase 9.

## Phase 9 — Harden availability, deployment, and operations

**Priority:** High for availability. **Findings:** R07, R13, R21, R22, R30, R34, R40, R42. **Entry:** Core behavior stable.

### Tasks

**U017 implementation note:** Phase 9 in progress, base b962824, guards 1cecc54 and compatible patched dependencies 1649b15. Application ingress/shared budgets/synchronous handlers and partial capacity/TLS/health controls are implemented. All task and exit boxes stay open pending remaining work and evidence. See [Phase 9 report](docs/PHASE9_OPERATIONS.md). Five hosted jobs passed for 1649b15; no production deployment or Phase 9 exit.

- [ ] P09-T01: Enforce configurable total request bytes before multipart spooling, plus file counts, per-file bytes, field sizes, parse timeouts, upload concurrency, and storage quotas. Configure the reverse proxy and application boundary consistently. Handle streamed/chunked requests; do not trust Content-Length alone.
- [ ] P09-T02: Add shared/distributed login and API throttling with account, IP/network, principal, and global dimensions. Protect against password spraying and expensive unknown-user hashing without enabling easy permanent account lockout. Define trusted proxy sources before honoring forwarded client IPs.
- [ ] P09-T03: Move blocking DB/hash/filesystem/Excel work out of async event-loop paths using a consistent synchronous worker/thread model or true async services. Bound worker/thread queues. Separate long scans, exports, and notifications into retryable jobs.
- [ ] P09-T04: Optimize scoped aggregate queries, eager loading, and indexes using representative synthetic workloads. Bound export row/byte/time limits and stream or job large exports. Benchmark against a recorded expected concurrency, dataset size, and response-time target; agree those targets before the gate.
- [ ] P09-T05: Schedule session/login-attempt cleanup, document reconciliation, scan retries, event publication/retention, and expiry checks. Make maintenance idempotent, lock-safe, observable, and explicit about its database privileges.
- [ ] P09-T06: If external reminders are accepted scope, implement a scheduler, recipient resolution, deduplication, retries, escalation, acknowledgement, and delivery audit. Otherwise retain dashboard-only reminders and document that operational limitation. Do not send real messages during tests or without an authorized rollout.
- [ ] P09-T07: Provide production deployment configuration: explicit hosts, TLS termination and HTTP redirect policy, trusted proxy handling, secure cookies, HSTS after HTTPS works, database TLS validation, secret injection, request limits, private storage, process supervision, and restricted network/database accounts. Validate unsafe/missing configuration at startup.
- [ ] P09-T08: Add structured redacted logs, correlation IDs, administrative/authentication/document-access events, health/readiness checks, metrics, and actionable alerts. Cover authorization failures, login spikes, database pool exhaustion, job lag, scan failures, disk capacity, backup age, and event-feed delay.
- [ ] P09-T09: Deliver scheduled encrypted backups of database plus document storage with appropriate access/retention. Rehearse a consistent restore and compare IDs, hashes, permissions, and audit continuity. Record measured recovery point/time against approved RPO/RTO targets.
- [x] P09-T10: Define local-account vs SSO/MFA strategy. For local accounts, implement the required MFA/enrollment/recovery policy before broad exposure; for SSO, implement and verify the selected provider integration if in scope. Separate service tokens from human authentication.
- [ ] P09-T11: Create a dependency/update inventory and reproducible build/release manifest. Review current advisories during implementation rather than asserting vulnerabilities from version strings. Exclude virtual environments, wheel caches, temporary package metadata, databases, and documents from release artifacts; verify resolved paths before any cleanup.

### Verification and exit criteria

- Oversized/slow/chunked uploads are rejected before unbounded disk/memory use; quotas and concurrency limits work.
- Rotating usernames cannot bypass aggregate login protection; proxy headers cannot spoof the trusted client identity.
- Representative concurrent login, upload, export, and read traffic meets agreed targets without event-loop starvation.
- Failed jobs recover safely; monitoring detects failures and alerts reach the designated test destination.
- HTTPS/proxy/database TLS, secret handling, actual DB roles, scheduled cleanup, and backup restore pass deployment checks.
- Recovery measurements and remaining operational constraints are documented; no production secrets appear in artifacts.

**Recovery:** Release immutable application/configuration versions with compatible schemas; retain rollback artifacts and an operations runbook. Revert capacity/config changes without disabling security controls.\
**Handoff:** Record deployed configuration references, commands, targets/results, job ownership, and recovery measurements without secret values.

## Phase 10 — Close scope gaps, accept the pilot, and release

**Priority:** Release gate. **Findings:** R22, R29, R30, R33, R36 and all residual findings. **Entry:** Phases 1–9 verified or explicitly scoped as optional.

### Tasks

- [ ] P10-T01: Assign named accountable owners for the application, database, identity administration, approvals, privacy/records, backups, updates, incident response, and integration consumers. Record approvals with date and evidence reference.
- [x] P10-T02: Build an F1–F15 acceptance matrix with representative user journeys, permissions, known limitations, and evidence. Replace blanket completion claims with verified behavior and explicit release exclusions.
- [ ] P10-T03: Decide each connector's scope: H&H, SSO/LDAP, product-specific DMS, automatic document intake, and procurement integration. For an included connector, obtain official interface specifications/test access, define mapping, scopes, credentials, retries/idempotency, reconciliation, error handling, and monitoring; implement and verify it before claiming delivery. Otherwise retain a documented backlog entry and manual operating procedure.
- [ ] P10-T04: Approve retention/legal-hold/disposal and data-access policies. Verify the implemented controls match them, including exports, logs, event feeds, backups, and external systems. No automatic destruction while required policies are undecided.
- [ ] P10-T05: Run end-to-end acceptance using sanitized examples: create/import, assign/delegate, upload/scan, request/decide/reopen, material edit, tax assessment, activation, reporting, synchronize/transfer/remove, archive, recover, and authorized disposal where enabled.
- [ ] P10-T06: Complete an independent security/permission review and operational recovery rehearsal. Recheck every finding with evidence. Record newly discovered defects and reopen the affected phase rather than declaring a conditional pass.
- [ ] P10-T07: Prepare migration rollout, backup checkpoint, maintenance window, reconciliation, smoke checks, rollback/restore criteria, user communications, and support instructions. Pilot with named departments and least-privilege accounts before expanding access.
- [ ] P10-T08: Close or accept every Medium finding with owner, rationale, compensating control, expiry, and review date. No unresolved Critical/High findings. Required scope gaps cannot be waived by relabeling them as optional after implementation without product-owner agreement.
- [ ] P10-T09: Update README, ARBEITSPLAN, CHANGELOG, API documentation, operator runbooks, and HANDOFF to the actual released version. Include exclusion lists, commands, recovery instructions, ownership, and next review/update dates.

### Final acceptance criteria

- Zero unresolved Critical/High findings; all required phase gates have recorded verification evidence.
- Authorization and RLS are verified against actual production-role equivalents; approval/archive integrity holds under concurrent operations.
- Reports reconcile to approved definitions; synchronization converges without silent data loss or retained out-of-scope records.
- Document availability, scanning, recovery, retention/holds, and approved disposal behave as specified.
- Privacy/domain/operations/security approvals are named and dated. RPO/RTO and service targets are met.
- Pilot users can complete accepted F1–F15 journeys and understand excluded integrations and notification limits.
- HANDOFF records the release version, current deployment state, remaining backlog, owners, and next maintenance action.

**Recovery:** Stop rollout when a release gate fails. Follow the rehearsed application rollback or consistent database/document restore procedure; record actual outcome and reopen affected findings.\
**Handoff:** Provide final acceptance evidence, release identifier, approved residual risks, pilot outcomes, and operational ownership.

## 5. Decisions register

These are proposed implementation defaults, not claims of city approval. Each must be adopted or replaced with a documented decision before its dependent release gate. Safe defaults permit technical implementation to proceed without inventing legal or accounting policy.

| ID | Decision needed | Proposed implementation default | Owner role | Needed by |
|---|---|---|---|---|
| D01 | Reviewer vs approver responsibilities | Existing reviewer remains read-only; explicit assigned approval capability | Kämmerei/security | Phase 2 exit |
| D02 | Cross-department review and delegation | No implicit grant from contact/deputy/recipient text | Domain/identity owner | Phase 2 exit |
| D03 | Database isolation level | Production PostgreSQL RLS plus application authorization; restricted DB roles | DBA/security | Phase 3 exit |
| D04 | Mandatory approvals and material changes | Bind decisions to content; gate activation; mark legacy records unverified | Approval owners | Phase 4 exit |
| D05 | Upload content and scanning | Quarantine new files until clean; preserve legacy unscanned status | Security/operations | Phase 5 exit |
| D06 | Retention, holds, deletion, audit retention | No automatic destructive disposal pending approved rules | Privacy/records owner | Phase 5 design; Phase 10 release |
| D07 | API scopes, service ownership, event retention | Explicit scopes/expiry; stable feed; removal events; documented resnapshot | Integration/security owner | Phase 6 exit |
| D08 | Financial basis and historical semantics | Preserve unknowns; report recorded history honestly; no fabricated figures | Finance owner | Phase 7 exit |
| D09 | Date/renewal legal interpretation | One reviewed calculation specification; display limitations explicitly | Domain owner | Phase 7 exit |
| D10 | Excel update and identity semantics | Create-only with explicit generated-number/external-reference behavior | Product/data owner | Phase 7 exit |
| D11 | Hosting, load targets, RPO/RTO, alert ownership | Internal TLS service with measured recovery and agreed workload | IT operations | Phase 9 exit |
| D12 | SSO/MFA and account recovery | Explicit strategy; no assumption LDAP exists | IT identity/security | Phase 9 exit |
| D13 | Notifications and connector scope | Dashboard/manual workflows until a specific integration is accepted and verified | Product owner | Phase 10 scope acceptance |

## 6. Standard completion record

For each task or coherent change, add an update to HANDOFF with:

1. Date, update ID, implementer, phase/task IDs, and source revision if available.
2. Behavior changed and affected files/schema/configuration.
3. Migration/backfill and data impact, including legacy-state handling.
4. Verification commands, environment, actual outcome, and evidence location.
5. Remaining failures, risks, blockers, and decisions needed.
6. Recovery/rollback implications and deployment status.
7. Exact next action and owner.

Task implementation, verification, deployment, and acceptance are separate states. Completion requires the relevant phase exit evidence, not just merged code or a checked box.

### Phase 9 owner decisions recorded 2026-10-21 (U018)

D11: user selected native Windows, PostgreSQL and TLS reverse proxy. Initial acceptance targets approved: 10 concurrent users, 10,000 contracts, 50,000 document metadata rows; ordinary page p95 <2s, bounded export <15s; RPO 24h, RTO 4h. Actual measurements, custodians and alert ownership remain pending. D12: user selected local accounts with TOTP MFA and audited administrator recovery. Implementation and verification remain required. These decisions do not authorize production deployment or close Phase 9.

U019 P09-T10 technical verification: approved local TOTP/enrollment/owner recovery implemented at ece7797; 244 collected, native PG 242 passed/2 local skips, SQLite 219/25, 15 subtests each; explicit PG 23 passed; all five hosted jobs passed. Production key/custodian/ACL/device and operating procedure acceptance remains a separate Phase 9 exit gate. No production deployment authorized or performed.


U020 P09-T09: encrypted/signed owner-operated snapshot and new verified restore-bundle implementation; disabled 12-hour Windows task draft, mandatory actual encryption tests in both PostgreSQL CI jobs. Targeted 29 passed; full frozen-source/hosted evidence pending. P09-T09 remains unchecked until schedule/off-host recovery, representative RPO/RTO and operating acceptance. Provisional production operations/identity roles are documented in PHASE9_OPERATIONS; no municipal approvals apply to isolated development, login or local recovery, and no external workflow/escrow is activated.


U020 final checkpoint 92329b6: 262 collected; native PG 260 passed/2 local skips,
SQLite 236/26 explicit skips, 15 passing subtests each; explicit PG 24 passed;
backup/Windows 29 passed. All 17 backup cases executed on PG. All five exact-
source hosted jobs passed (39660619585). Final catalog 0 guarded DBs/0 generated
roles, control privileges unchanged. Encrypted restore technically verified on
tiny synthetic data; no production schedule/escrow/deployment or RPO/RTO
acceptance. Phase 9 remains open. Details and remaining follow-ups: HANDOFF U020,
docs/PHASE9_OPERATIONS.md and docs/evidence/phase9-u020-local.json.


U021: continuing Phase 9 entry work before Phase 10. Standalone DBA TLS gap
fixed; hash-pinned 30-package runtime and deterministic committed-source release
builder/manifest/verifier added. Fresh Windows installation/pip check and 29
targeted release/TLS tests passed. Packaged runtime, full tests and eight-job
current-source hosted evidence pending in HANDOFF. No production deployment or
Phase 9 exit; local development has no municipal approval dependency.


Phase 10 preparation: [acceptance worksheet](docs/PHASE10_ACCEPTANCE.md) maps
F1-F15 to actual journeys/permissions/regressions and records connector, owner,
pilot and release gaps. This is preparation only: Phase 9 entry gates remain
open; no production release, named appointment or external workflow is activated.


U021 final: P10-T02 technical matrix prepared in docs/PHASE10_ACCEPTANCE.md;
Phase 9 entry gates and Phase 10 release acceptance remain open. DBA TLS policy,
30-package hashed runtime and deterministic source release technically verified
at 3442ad8: native PG 290 passed/2 local skips, SQLite 266/26, 15 subtests each;
explicit PG 24, release/TLS/YAML 30. All eight exact-source hosted jobs passed
(39666552361). Final catalog 0 guarded databases/0 generated roles. Full evidence,
retained failures and remaining engineering/operating gates: HANDOFF U021.
No production rollout, external workflow or named responsibility assignment.
