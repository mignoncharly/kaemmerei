# Phase 10 — acceptance and release preparation

Date: 2026-10-21. Plan: [ten-phase remediation plan](../REMEDIATION%20PLAN%20PHASES.md).
Current evidence: [HANDOFF](../HANDOFF.md), [verification matrix](VERIFICATION_MATRIX.md),
[Phase 9 operations](PHASE9_OPERATIONS.md).

**State: preparation only. No pilot, production deployment or release acceptance.**
Phase 9's required engineering and operating gates remain open. This matrix
organizes reviewable Phase 10 work; it does not waive the entry criteria or
convert technical tests into business approval. Local development, test login,
routine use and local administrator recovery require no municipal approval.

## 1. F1–F15 acceptance matrix — P10-T02 preparation

Automated references below are repository regressions with prior technical
evidence in HANDOFF U009–U020. U021 current-source full and hosted evidence is
recorded separately when complete. Each row still needs pilot/business review;
there is no blanket F1–F15 completion claim.

| Function | Sanitized journey and required permission | Automated evidence | Current limitation / pilot check |
|---|---|---|---|
| F1 Contract register | Active department user creates, finds and edits its own contract; stale edit conflicts; admin archives; other department cannot read metadata or modify it | `test_app.py`: `test_create_edit_archive_history_and_conflict`, `test_department_isolation_and_server_side_ownership`; `test_phase4.py` archive races | Archive preserves records. Pilot must confirm field meanings, search and conflict recovery. |
| F2 Documents | Authorized uploader stages a synthetic PDF; unavailable/infected scan denies download; clean bytes/hash permit scoped download; replacement preserves predecessor | `test_phase5.py`: scan denial, verified download, replacement, recovery and actual scanner tests; `test_phase9_backup.py` encrypted restore | Production scanner/storage/ACL/capacity acceptance open. Generic external links do not implement a product-specific DMS adapter. |
| F3 Departments | Admin renames, suspends and reactivates a department; IDs/records persist; suspended membership loses access | `test_phase2.py`: `test_department_admin_suspension_revokes_sessions_and_reactivation_preserves_records`, scoped catalog tests | User labels and contacts do not grant delegation or read access. Confirm operating ownership and lifecycle procedure. |
| F4 Accounts and roles | Admin provisions individual synthetic accounts; ordinary user changes password; local operator recovery revokes sessions and requires replacement; TOTP enrollment/challenge/replay checks apply when enabled | `test_phase2.py` password/recovery/last-admin tests; `test_phase9_mfa.py`; `test_mfa_codec.py`; `test_phase3.py` actual restricted roles | Development remains usable without mandatory MFA rollout. Production requires explicit MFA policy and protected external key. Custody/adoption and device usability remain open. |
| F5 Dates | Enter month-end/leap-day examples; compare form, detail and API values for fixed term/renewal/notice | `test_phase7.py`: calendar anchors, date validation/display/API consistency | D09 legal interpretation remains unapproved. Calculated dates are estimates, not legal advice or proof of valid notice. |
| F6 Reminders | View overdue/next-90-day contract deadlines and overdue tasks within authorized scope | Baseline dashboard tests; `test_phase8.py` filter/inbox contracts; `test_phase9_queries.py` dashboard query bounds | Dashboard/manual follow-up only. No email/push, delivery guarantee, escalation or external notification activated. D13 required before any expansion. |
| F7 Dashboard/search | Browse more than one page, retain filters and compare counts/export population; unauthorized scope stays absent | `test_phase8.py`: `test_scoped_pagination_beyond_old_cap_and_export_parity`; `test_phase9_queries.py` scoped aggregates | Initial undated read benchmark passed after retained earlier failures. Representative mixed workload and manual usability/AT acceptance remain open. |
| F8 Tasks/status | Authorized writer creates/assigns a task, changes state with expected version; stale/concurrent update conflicts; archive prevents mutation | `test_phase4.py`: task versions, concurrent task updates, archive races; `test_phase8.py` personal inbox | Assignment never grants contract access. Confirm task vocabulary, responsibility and manual follow-up in the pilot. |
| F9 History | Create/edit/upload/decide/archive synthetic records; inspect actor, time and field changes; restore retains revision IDs/audit continuity | `test_app.py` lifecycle/history; `test_phase3.py` append-only audit; `test_phase6.py` child events; `test_phase9_backup.py` restored revisions | Recorded history does not reconstruct unrecorded past states. Retention, audit access and operational adoption remain D06 work. |
| F10 Financial data | Enter income/expense, zero/unknown values and net/gross/unknown basis; reconcile scoped totals and missing counts | `test_phase7.py`: `test_financial_reconciliation_preserves_unknowns`; `test_phase9_queries.py` SQL group equivalence | D08 finance agreement remains open. No payment ledger, appropriation accounting or automatic tax conversion. |
| F11 Tax review | Admin completes assessment with required basis/result; ordinary department cannot assess; reopening clears current completion metadata | `test_phase4.py`: `test_tax_reopen_clears_current_completion_and_department_cannot_assess`; `test_phase8.py` tax capabilities | The application records an assessment; it does not supply a binding §2b tax decision. Domain/finance sign-off remains open. |
| F12 Approval | Assign active eligible team/account with existing read scope; independent assignee decides current content; stale/self/wrong-recipient requests fail; material edit invalidates approval; activation requires current configured approvals and clean documents | `test_phase2.py` membership/assignment tests; `test_phase4.py` approval/content/activation/concurrency; `test_phase5.py` scan gate | D01/D02/D04 municipal policy adoption remains open. No approval override or notification delivery assumed. |
| F13 Excel | Export scoped filtered population as literal-safe XLSX; import sanitized create-only rows atomically; generated numbers rejected, external references scoped | `test_phase7.py`: XLSX Unicode/formula/header, atomic import, external identity and concurrent import; `test_phase8.py` export parity | Export max 5,000; import max 500. No automatic update mode or document/history backup. D10 acceptance remains open. |
| F14 Reports | Compare known/unknown totals; transfer and archive a record and verify historical department/population against recorded revisions | `test_phase7.py`: `test_history_population_department_transfer_and_archive`; financial and narrow PG history tests | No invented pre-history or future full-year actuals. D08 sign-off and representative report load remain open. |
| F15 API/synchronization | Explicit scoped/expiring service token snapshots and pages changes; transfer emits minimal removal; consumer restarts after expiry/retention; revoke denies reuse | `test_phase6.py` snapshots, late commits, scope/removal, reauthentication, rotation/revoke; actual RLS `test_phase3.py` | API v2 is not a delivered H&H/procurement/DMS product adapter. V1 consumers require deliberate migration. D07 profiles/consumer adoption and operating schedules remain open. |

Referenced test files reside in [tests](../tests). PostgreSQL/RLS evidence requires
the actual PostgreSQL selections; a SQLite pass cannot satisfy that column.

## 2. Connector scope ledger — P10-T03 preparation

| Capability | Delivered technical boundary | Decision / operating constraint |
|---|---|---|
| H&H finance connector | No product adapter implemented | Interface specification, test access and included/excluded scope decision pending. Manual data entry/export is interim behavior, not accepted equivalent delivery. |
| SSO / LDAP | User selected local accounts with TOTP and audited administrator recovery (D12) | No SSO provider/LDAP server is assumed. Local-account strategy is the selected implementation; future provider integration needs explicit scope and verification. |
| Product-specific DMS | Allowlisted external links and audited link correction | No product API upload/search/lifecycle connector. Product/interface/access and scope decision pending. |
| Automatic document intake | Authorized manual upload and durable scan retry | No mailbox/folder ingestion, OCR routing or automatic classification. Scope/interface decision pending. |
| Procurement integration | Read-only versioned register API | No implemented procurement-system adapter or write-back. Product/API/mapping/reconciliation and scope decision pending. |
| External reminders | Dashboard warnings/manual follow-up | No external messages, escalation or delivery audit. User explicitly left production notifications inactive. |

No missing required scope is silently relabeled optional. For each proposed
connector, record an explicit dated product decision; included scope needs real
specification, least-privilege credentials, idempotency/reconciliation, failure
handling, monitoring and verified test access before delivery can be claimed.
Do not request or put credentials in this ledger.

## 3. Ownership and approval record — P10-T01/T04/T08

Role assignments below are proposals, not confirmed appointments or approvals.
No named individuals or existing dedicated IAM team are assumed. No one has been
contacted and no external approval workflow has been activated.

| Responsibility | Proposed role / unresolved decision | Approval evidence |
|---|---|---|
| Application/domain scope and pilot | Product/domain owner to be designated | Not recorded |
| Database/RLS/deployment | Authorized database/system administration to be designated | Not recorded |
| Operational alerts/recovery | Municipal IT Operations / System Administration, user-proposed provisional role | Municipal confirmation not recorded |
| Sensitive administrator recovery/key custody | Authorized identity/access or IT Security Administration; proposed dual authorization for sensitive production recovery | Municipal confirmation, custody procedure and production activation not recorded |
| Business approvals / finance / dates | Authorized domain/finance approval roles to be designated; D01/D02/D04/D08/D09/D10 | Not recorded |
| Privacy, records and retention/disposal | Authorized privacy/records role to be designated; D06 | Not recorded |
| Integration consumers and update/incident response | Accountable consumer/security/operations roles to be designated; D07/D13 | Not recorded |

Routine authenticated password change is self-service. Lost-factor administrator
recovery is a separate privileged action with identity verification and audit.
Local development/test recovery uses the secure local procedure without municipal
approval. Future sensitive production recovery may require the proposed additional
authorization; that workflow and MFA-key escrow remain inactive.

Retain existing non-destructive defaults: legal holds/predecessors/history remain;
there is no automatic record/document/audit/backup disposal pending adopted policy.
Session/login-attempt housekeeping is not permission to purge business records.
Never use ordinary Excel exports as backups.

## 4. Sanitized end-to-end pilot worksheet — P10-T05

**Manual pilot: Not run.** Automated component/concurrency/restore evidence exists,
but does not represent an observed departmental pilot or independent acceptance.

Use newly provisioned isolated pilot resources and synthetic records only until
production rollout is separately authorized. Record source/artifact digest, schema
head, platform, actual restricted-role identities, scan definition freshness and
timestamp before a run. Do not record passwords, tokens, MFA seeds, personal
contract data or recovery credentials.

1. Provision synthetic active departments A/B and individual admin/department/
   reviewer accounts; verify inactive membership and unauthenticated denial.
2. Create a contract in A; find/filter/page it; deny B detail/API/child metadata.
3. Import valid create-only rows; reject one invalid batch atomically. Reconcile
   generated numbers/external references and export literal-safe scoped XLSX.
4. Assign task and review explicitly. Confirm assignment alone grants no access;
   stale, self and unauthorized decisions fail server-side.
5. Upload a harmless synthetic file with a test scanner; observe quarantine,
   retry/recovery and clean download/hash. Retain a replaced predecessor/hold.
6. Complete independent review and administrator tax assessment; activate only
   when configured content/document gates pass. Material edit requires new review.
7. Reconcile financial values/unknown counts, recorded history and dates with the
   approved business examples; record disagreement without adjusting expected data.
8. Snapshot/synchronize with a synthetic limited service credential. Transfer A
   to B; old scope receives minimal removal, new scope upsert; revoke/expiry deny.
9. Archive; verify ordinary contract/review/task/document changes are denied and
   recorded history remains visible only to authorized readers.
10. Exercise local account recovery/MFA challenge revocation using disposable
    keys. Ordinary login requires no external organizational approval.
11. Rehearse encrypted consistent backup and restore to a positively identified
    NEW empty target; compare IDs, hashes, audit continuity and restricted access.
    Measure representative RPO/RTO against 24h/4h targets; tiny fixture timings
    are not this acceptance.
12. Keep disposal disabled until its policy/control gate is approved. An enabled
    authorized disposal journey requires separate evidence; do not simulate a
    pass by deleting files manually.

For every step record: expected result, actual result, evidence reference,
pass/fail/not-run, issue ID, role performing the test and review date. A failure
reopens its remediation phase. No medium-risk acceptance is inferred from silence.

## 5. Release gate and rollback worksheet — P10-T06/T07/T09

| Gate | Current state / required evidence |
|---|---|
| Critical/High findings | Required unresolved availability/load/operations findings remain Phase 9 work; no zero-high claim |
| Independent security review | Not performed; this implementation/test work is not an independent review |
| Phase 9 operations | Monitoring/backup age, remaining maintenance scheduling, mixed workload and representative recovery remain open |
| Native deployment | No production service/proxy/TLS/certificate/ACL/quota/firewall acceptance or deployment |
| Dependency/release integrity | U021 runtime lock, source manifest and packaged-runtime checks; exact-source evidence recorded in HANDOFF after verification. Wider tool/advisory/update operations remain open |
| Business/privacy/records/consumer approvals | Not recorded; proposals above do not count as approvals |
| Manual usability/AT / departmental pilot | Not run / not accepted |
| Production migration and reconciliation | Not performed; no business database has been migrated by this work |
| Release authorization | Not recorded; no deployment or external notifications activated |

Before an authorized rollout, bind a reviewed immutable source artifact/digest,
compatible migration head, tested runtime lock, operator configuration references
and backup checkpoint. Plan a maintenance window, reconcile legacy exceptions and
prepare restricted-role smoke checks. Define stop criteria for migration/inventory
failure, access leakage, scanner failure, data/hash divergence or service targets.
Preserve the prior artifact/configuration and original instance. Recovery follows
the rehearsed compatible application rollback or consistent database/document
restore; do not disable RLS or downgrade/drop schema objects as a shortcut.

Record release communications/support arrangements only after recipients and
rollout are authorized; this document authorizes no messages. Close each residual
medium finding with owner role, rationale, compensating control, expiry and review
date. Required Critical/High fixes and scope gates remain release blockers.
