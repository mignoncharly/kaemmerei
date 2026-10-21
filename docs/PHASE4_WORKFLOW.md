# Phase 4 — Bound approval, tax, archive and concurrent mutations

Date: 2026-10-21. Tasks P04-T01–T08 from the existing remediation plan.
This implements pilot defaults for D04; it does not record municipal approval or
production deployment. No business database or document collection was migrated.

## Mutation protocol

Existing routes remain in place and call `app/workflow.py`. Input is parsed before
locking. Writers acquire the existing identity guard, revalidate membership and
(for secured PostgreSQL) database request identity, lock/reload the parent, reject
archived state, enforce capability and expected version, persist the mutation,
revision/audit/trigger events, and commit once. Errors roll back the transaction.
Assignment uses the same guard/parent ordering. PostgreSQL uses the narrow Phase 3
parent lock under actual restricted logins. SQLite obtains its writer lock through
the guard UPDATE before reloading/checking state; it does not pretend to implement
PostgreSQL row locks or RLS.

The guard currently serializes aggregate writers across contracts as well as
identity writers. This is a deliberate conservative implementation, with a
throughput limitation to measure in Phase 9. Network upload parsing precedes the
lock; existing local upload finalization remains Phase 5 work. Future jobs must
use the mutation protocol, not independent read/check/write code.

Database triggers independently lock/check parents for child writes on PostgreSQL
and reject archived parent/child writes on both backends. Task/review/document
inserts, updates and deletes cannot commit against an archived parent. Contract
updates cannot alter an already archived row. There is no archive correction route.

## Versions and material content

The existing contract `version` remains the edit/archive conflict counter.
Material document additions also advance it. Tasks/reviews have separate positive
starting versions and their edits/assignments require the submitted version. Each
successful edit increments its version; concurrent/repeated stale writes return
409. Missing versions return 400. Conflict pages retain escaped submitted fields,
show the current version and provide a reload/reconcile link; no automatic rebase
or silent resubmission occurs.

`content_revision` starts at 1. Material changes include designation/type/partner,
contract dates and notice/renewal fields, financial amount/direction/interval,
budget assignment, date description, department, contact/deputy and all newly
uploaded or linked contract documents. `MATERIAL_FIELDS` is the authoritative list.
One edit/upload request advances content once, even for multiple files. Tasks,
review commentary/decisions, lifecycle status and tax assessment commentary do not
invalidate their own content. Changes to their underlying financial/date/party
inputs do invalidate it.

Material changes reopen requests as superseded, increment request versions and
retarget them to the new content. Old status/result/binding is retained in revision
history and immutable decision rows. A verified active contract becomes
`in_progress`/pending. Old approvals cannot activate the new content. Completion
metadata on a completed tax assessment is cleared and assessment reopens; its
previous actor/time/result remain in the pre-change revision snapshot.

Create-only workflow forms carry fresh UUID submission IDs. Under the shared
writer lock, IDs are checked against actor/contract revision history and recorded
transactionally. A repeated ID returns 409 and creates no second action. Edit
replays are rejected by versions. IDs are unique per rendered form; they do not
replace CSRF. The ordinary regression helper submits current form fields explicitly;
Phase 4 missing/stale/replay regressions bypass that helper.

## Approval policy and state machine

| Current request state | Allowed next state | Requirements |
|---|---|---|
| open / in_review | open, in_review, approved, changes_requested, rejected, withdrawn | Existing read scope and explicit decision authority; reason required |
| terminal state | open only | Administrator, expected version and reason; activation invalidated |
| terminal state | any direct replacement decision | Rejected with 409; reopen first |
| archived parent | any mutation | Rejected with 409 |

This table describes manual transitions. Material supersession is a separate
automatic transition: all existing requests, including withdrawn requests, reopen
against the new content. This conservative re-review rule is part of the D04 pilot
default and must be reviewed by the approval owners.

Approval additionally requires an explicitly assigned account/team. The actor must
be neither the contract creator nor the last material editor. Administrators cannot
bypass independence or assignment to approve. Department accounts with explicit
approval capability still need active team membership, assignment and existing read
scope. Assignment creates no read grant. An administrator may reassign/clear a
request with its current version; this reopens it and invalidates activation.

Each transition creates an immutable `review_decisions` row: request/contract IDs,
request version, content revision, actor, assigned team/account, UTC time, state and
reason. Decisions have unique request/version identities, no application UPDATE or
DELETE grants, append-only triggers and parent-scoped RLS. The NOLOGIN audit owner
owns the table; runtime ownership remains forbidden. Detail pages display binding,
provenance and decision history. These records preserve the authority at decision
time; later account deactivation does not erase historical evidence.

New contracts and imports default to draft. An explicit newly active create/import
is rejected: imported status is not evidence of an approval. Activation through
edit requires current approved decisions for **every** configured recipient in
`MANDATORY_REVIEW_RECIPIENTS` (default `Kämmerei`). Empty/unknown recipient settings
fail startup. No activation-exception capability or bypass endpoint is provided;
exceptions require a separately approved, implemented and audited policy.

Legacy active rows retain `legacy_unverified`; nonmaterial saves do not invent
approval provenance. Material edits invalidate their legacy activation and require
review. New decisions bind the current content rather than retroactively claiming
that old decisions approved it. D04 owners must accept or replace these pilot rules
before business deployment, including the mandatory recipients and independence rule.

## Tax capability and legacy reconciliation

The pilot `tax_assess` capability belongs to administrators. Department writers
cannot change assessment status/result or complete an assessment. Reopening clears
current completion actor/time; recompletion requires an administrator and a result,
and records a fresh actor/time. A material change cannot complete its own assessment
in the same edit: the new saved content must be assessed subsequently.

Migration `0017_bound_workflow` is additive. Existing active/tax/review state is
preserved as `legacy_unverified`; old review content revision remains NULL. It
does not synthesize approval decisions, actors, assignments or historical content
versions. `material_actor_id` stays unknown on old rows until a material edit.
Existing migration files and Phase 3 rules remain unchanged.

```powershell
# Privileged operator environment only; never inject the owner URL into web workers.
& $python -m app.cli workflow-inventory
```

The reconciliation report returns only sorted IDs for legacy active contracts,
completed legacy tax assessments and unverified reviews. A business-data inventory
has not been run. Counts cannot be claimed as zero for an uninspected database.
Populated synthetic migration tests verify the unverified markers and unchanged
private labels; clean schema equality checks continue on both backends.

After migration, rerun the reviewed role-grant configurator for head 0017 to grant
new columns/table/sequence access and transfer decision ownership. Upgrade application,
schema and grants as one compatible deployment. SQLite rebuild restores contract
event triggers before adding archive barriers. Downgrade is refused; recover through
reviewed forward repair or a verified matching application/database/document backup.
Never delete decisions, reactivate superseded approvals or disable RLS for recovery.

## Verification

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
$python='C:\kämmerei\.venv\Scripts\python.exe'
& .\scripts\Start-TestDatabase.ps1 -Python $python
& $python -m pytest -q -ra
& $python -m pytest -q -ra --database postgresql
& $python -m pytest -vv -ra --database postgresql tests/test_phase4.py
& $python -m pytest -q -ra --database postgresql -m postgresql
```

All Phase 4 tests use actual restricted PostgreSQL LOGIN roles when PostgreSQL is
selected, and application authorization on SQLite. Concurrent requests use separate
clients/sessions and a synchronized start. Review/task races require exactly one
success and one conflict; archive races cover task create/edit, request create/edit,
assignment, upload, link, contract edit and tax edit. Either pre-archive mutation can
win; after the successful archive barrier every repeated mutation must fail, and
archive must be the last revision. Approval N/material N+1, document invalidation,
replay IDs, terminal reopening, unauthorized/self approval, immutable decisions and
tax history are also checked. CI explicitly runs the Phase 4 PostgreSQL selection
in both service and native jobs, in addition to the full suites.

### Actual results

Source `f0d998f862941e04cbe5f120c2fa18de6c1986b7`; Windows, Python 3.14.3,
pytest 9.1.1, PostgreSQL 18.3. [Local evidence](evidence/phase4-local.json) contains
JUnit hashes; ignored XML remains on this workstation.

| Check | Selected | Passed | Skipped | Failed / xfailed | Seconds |
|---|---:|---:|---:|---:|---:|
| Full PostgreSQL | 99 | 99 | 0 | 0 / 0 | 202.79 |
| Full SQLite | 99 | 87 | 12 PostgreSQL-only | 0 / 0 | 65.80 |
| Final Phase 4 PostgreSQL selection | 18 | 18 | 0 | 0 / 0 | 58.80 |
| Phase 4 SQLite selection | 18 | 18 | 0 | 0 / 0 | 21.80 |
| Explicit PostgreSQL security/lifecycle selection | 12 | 12 | 0 | 0 / 0 | 35.90 |

Both full suites additionally passed 15 subtests. The explicit PostgreSQL selection
deselected 87 ordinary tests; the dedicated Phase 4 selection separately ran all 18
workflow/race tests under actual restricted logins. No warnings were suppressed.
Two remain: Starlette/AnyIO deprecated BlockingPortal alias and managed Windows
pytest-cache ACL. Final read-only catalog check found zero harness databases and
zero generated temporary roles. Existing native cluster, private passfiles, binary
identity checks and unrelated launcher edit are preserved. No Docker dependency added.

Hosted [run 39606147120](https://github.com/mignoncharly/kaemmerei/actions/runs/39606147120)
completed successfully for the source SHA above. All three jobs passed: SQLite,
PostgreSQL 18 service and native-postgresql. Dependency installation, migrated
verification, full pytest, explicit PostgreSQL security selection and both explicit
Phase 4 selections succeeded. Run/job/step conclusions and all three artifact
metadata were inspected directly via GitHub API; archives were not downloaded.
[Hosted evidence](evidence/phase4-ci-39606147120.json) records the exact results.

**Phase 4 technical gate is verified locally and in hosted CI.**

### Acceptance checklist

- [x] Shared parent/identity lock and one-commit mutation protocol across existing writers.
- [x] Content-bound immutable decisions and configured independent approval gate.
- [x] Material/document changes supersede prior approval and reopen completed tax assessment.
- [x] Terminal reopening, unauthorized tax/self-approval and stale versions rejected.
- [x] Input-preserving conflict page and duplicate child-action protection.
- [x] Concurrent decisions/tasks and nine archive races pass on both backends.
- [x] Synthetic legacy values preserved as unverified; reconciliation command available.
- [x] Full suites and actual hosted Phase 4 source pass without failures or xfails.
- [ ] D04 municipal adoption and business legacy reconciliation/migration/grants.
- [ ] Production recovery/load/operations and release acceptance.

## Remaining boundaries

D04 municipal approval, production legacy inventory/migration/grants and recovery
rehearsal remain open. Shared-login GUC security boundaries from Phase 3 still apply.
Document scanning/quarantine, durable storage staging/recovery and retention remain
Phase 5; externally reliable event publication/cursors remain Phase 6. No legal or
tax acceptance is implied by the pilot workflow. No deployment has been performed.
