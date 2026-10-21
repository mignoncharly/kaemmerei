# Phase 7 — Financial inventory, calendar estimates and Excel interchange

Date: 2026-10-21. Tasks P07-T01–T09; findings R06, R17–R20, R35.
Engineering implementation and verification are tracked in HANDOFF U015. D08
(finance), D09 (legal calendar interpretation) and D10 (interchange identity)
remain proposed technical defaults, not municipal approval. No business database
has been migrated and no production deployment has been performed.

## Diagnosis and changes

The old report population contained only today's visible nonarchived contracts.
It then applied financial deltas from those contracts' revisions, so archiving or
transferring a contract could erase its former department's history. Empty direction
was classified as expense. Missing amounts were silently summed as zero. Dates in
detail views renewed terminated contracts while reminders did not. Calendar and
Excel serial arithmetic could overflow, formula caches could masquerade as literal
input, and supplied contract numbers were ignored during create-only imports.

| Task | Delivered technical behavior | Remaining adoption boundary |
|---|---|---|
| P07-T01 | Versioned inventory definition below, explicit inclusion/unknown rules | Finance owner must approve; task checkbox remains open |
| P07-T02 | `value_basis=net/gross/unknown`; legacy default unknown; preserved amounts | No multicurrency or effective-at accounting requirement is approved |
| P07-T03 | Latest recorded full snapshot at cutoff, independent of current contract population; historical department filtering | Gaps before full recorded evidence remain unknown |
| P07-T04 | Direction/basis breakdown, known/missing counts, reconciliation groups | Inventory is not a cash or commitment ledger |
| P07-T05 | One calendar service for reminders, list/report, detail and APIs; termination and overflow behavior | Legal owner must approve interpretation |
| P07-T06 | Date/notice/first renewal bounds before persistence; invalid numeric serials and month values rejected | Legacy uncomputable dates display an error instead of a fabricated date |
| P07-T07 | Explicit create-only import, generated contract numbers, preserved external reference | Product/data owner must adopt identity semantics |
| P07-T08 | Scoped exact external identity, unique index, writer guard, atomic imports, description ambiguity flags and provenance | Reference-free repeated imports deliberately create new records |
| P07-T09 | Literal string export, bounded ZIP/XML, strict references/headers/shared strings, explicit formula/1904 rejection | Excel is not a document/history backup |

## Inventory v2 specification (D08 proposed)

- The unit is a recorded contract, not a payment, invoice, budget reservation or
  independently verified obligation. Values remain EUR metadata as in the existing
  application. No currency conversion, annualization, VAT inference or net/gross
  conversion occurs. There is no evidence for a separate effective-at ledger;
  effective dates and retroactive financial corrections are not invented.
- Current inventory includes every authorized nonarchived contract, including
  draft, in_progress, active, terminated, ended and future-start contracts. Archived
  records are excluded from the current inventory. A status/date filter must not
  be inferred from the label “annual value.”
- Annual amounts are grouped by historical/current department, direction and value
  basis. Unknown direction has its own group and never increases expenses. Unknown
  basis is a separate group. Zero is a known value; absent, malformed or nonfinite
  amounts are missing and excluded from sums, with counts alongside them.
- The headline direction totals combine recorded value bases and are explicitly
  labelled as inventory metadata; the basis tables provide comparable subtotals.
  They must not be used as approved budget or payment totals. Contract value totals
  also disclose missing amounts. Sum the displayed known groups to reconcile the
  headline totals; compare record/known counts to detect exclusions.
- Historical observations use the last complete `created`, `updated` or `archived`
  contract snapshot recorded by the cutoff, ordered by `(created_at, id)`. Snapshot
  completeness requires department and annual-value keys. Child-only revisions are
  not contract snapshots. Prior observations survive today's transfer/archive.
- Each of the previous four years uses 31 December UTC; the current year stops at
  now. This is recorded-at history, not proof of the transaction's commit time or
  the legal effective time. Pre-evidence years and years with no reconstructable
  nonarchived observations are explicitly unknown; their chart rows are omitted.
  No opening balance or retrospective baseline is fabricated.

### Historical authorization

Migration 0020 adds `ohvr_security.financial_history(timestamp)` in PostgreSQL.
It selects the latest state across all contract revisions **before** restricting
the historical department. Runtime callers receive only grouped department ID,
direction, basis, record count, known count and annual sum; no contract IDs, names,
partners, document metadata, raw revisions or destination department metadata.
It resolves the authenticated, active session again, rejects guests, forced password
changes, tokens and future cutoffs, fixes its search path and revokes PUBLIC access.
The integration/audit/maintenance roles are not granted execution. Current contract
and revision RLS are unchanged. A former department can see its former aggregate
without receiving access to the transferred contract's current metadata.

SQLite uses the same internal financial projection with application authorization;
it does not provide a database role/RLS boundary. Explicit development PostgreSQL
owner configurations use that trusted projection; there is no restricted-role
failure fallback. Production still requires the existing restricted-role settings.

## Calendar specification (D09 proposed)

- Supported calendar years are 0001–9999. Month arithmetic clamps the day to the
  destination month's last valid day. Every renewal uses the original contractual
  end-date anchor, avoiding February-to-March drift. Periods are whole months 1–120;
  notice months are 0–120.
- The displayed renewal is the first anchored end date on or after today. A missed
  notice date remains visibly missed; the system does not invent a later legal
  cancellation opportunity or silently renew based on the notice deadline.
- Terminated/ended contracts retain their original end date and have no calculated
  cancellation deadline. Draft/ended records produce no operational reminders.
  A notice date before the start date is possible metadata, not a legal finding.
- Validate notice subtraction and the first renewal before saving. Historical or
  later unrepresentable calculations return a visible error and null estimates,
  never a 500 or a clamped invented date. Raw contractual dates remain preserved.
- Detail, reminder and API calculations share `app/dates.py`. API `calendar_estimate`
  includes `legal_cancellation_verified=false`. Stored v2 snapshots retain their
  snapshot-time estimate; a new retrieval recalculates it. Existing snapshot payloads
  remain valid without the additive optional estimate.

## Excel create-only contract (D10 proposed)

- Import only creates records. `Vertragsnummer` is generated by the server; a
  nonblank supplied number is an error. There is no hidden update mode. Unknown
  nonblank headers, including `id`/`contract_id`, must be removed explicitly.
- `external_reference` is optional, trimmed, at most 120 characters, exact and
  case-sensitive. Its scope is department, including archived records. The same
  reference in another department is permitted. Legacy records remain NULL.
  The scoped unique index enforces this even outside the UI; ordinary create/edit
  forms and immutable revisions preserve the reference. Changing it is a material
  edit and does not bypass approval/version requirements.
- Imports recheck identities after the existing global writer/identity guard.
  Concurrent imports of a reference have one winner. A duplicate within the workbook
  or authorized database rejects the complete import. No partial contracts/history
  survive validation failure.
- Description/type/partner/start/department matches are ambiguous, not unique
  identities. Legitimate repeats are allowed and flagged in the persistent result
  warning and immutable revision provenance. Without external references, repeating
  a file creates new records; operators must review before repeating an import.
- Each created revision preserves workbook SHA-256, worksheet row, accepted raw
  mapped strings, normalized contract snapshot and ambiguity flag. Original workbook
  bytes are not retained as a document. Original raw strings may contain personal
  metadata and inherit the existing protected history/privacy/backup policy.
- Exported strings, including leading `=`, remain literal inline strings. An export
  is not directly reimportable: remove generated contract numbers deliberately;
  existing external references will still prevent duplication. There is no claim
  that documents, decisions, history, tokens or attachments round-trip through Excel.
- Limits: 10 MiB upload, 20 MiB declared aggregate ZIP expansion, 1,000 ZIP members,
  500 contract rows. Duplicate ZIP paths, unsupported worksheet targets, row/cell
  inconsistencies, invalid/duplicate column references, duplicate recognized headers,
  invalid shared-string indices, error cells and formulas (even cached) are rejected.
- Only the 1900 workbook date system is accepted. 1904 workbooks are rejected with
  conversion instructions, including when they contain text dates, so system choice
  is never silently misinterpreted. Accepted day serials are whole 1–2958465 excluding
  fictitious day 60; early dates correctly distinguish 59 and 61. Nonfinite, negative,
  fractional and overflowing serials are row errors. ISO and supported German-style
  literal dates are validated as actual dates before writing. Oversized numeric month
  exponents are bounded before integer conversion.

## Migration and operational recovery

Forward revision `0020_financial_reports` adds only columns, a check, a unique index
and the narrow PostgreSQL function. No existing amount, direction, revision or blob
is rewritten. The additive SQLite DDL preserves existing audit/archive/sync triggers.
Legacy basis remains unknown; no reference or historic financial basis is guessed.
Normal deployment must use the existing trusted migration-owner process followed
by the explicit runtime-grant configuration so new columns/function are accessible
only to intended roles. Do not run that process against business data without the
existing backup, recovery and owner acceptance gates.

Recovery is forward-only. Preserve references, basis and raw import provenance.
An older application must not overwrite new metadata or mislabel the report semantics.
If operational recovery is needed, use a coordinated verified database/document
backup or reviewed forward repair, not a destructive downgrade. No native test
cluster change, production grant change or new Docker requirement was introduced.

## Reproduce verification on Windows

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database sqlite
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql tests/test_phase7.py
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql -m postgresql
```

The launcher configures the dedicated role and passfile in that terminal. The managed
agent used the already running positively identified native cluster and existing
passfile. It did not reinitialize/stop the cluster or print secrets. All tests use
uniquely named, positively identified disposable databases and synthetic records.

## Verification state

Targeted Phase 7 on final source 2fd1bf8: native PostgreSQL 19/19 passed, SQLite 18 passed and one explicitly
PostgreSQL-only authorization skip. Broader schema/application security selections
also passed on both backends. Final exact-source outcomes and evidence are recorded below. Initial
failures (test fixture keyword override, missing export columns, missing-amount
rendering) were corrected and rerun; no xfail or warning suppression was introduced.

Hosted workflow explicitly selects Phase 7 on both service and native PostgreSQL in
addition to the full suites. YAML inspection is not a hosted pass. D08–D10, production
rollout, browser accessibility/CSP work in Phase 8 and operational acceptance remain
open regardless of successful engineering tests.

### Intermediate verification progress (superseded by final results below)

Implementation source: `2fd1bf85406895254d070453bbc1ced03fe7ff72` (main).
Final full SQLite: 170 items collected, 152 passed, 18 explicit skips, 15 passing
subtests, zero failures/errors/xfails (129.17s). Phase 7 PostgreSQL: 19 passed
(33.18s); SQLite: 18 passed and one PostgreSQL-only skip (7.39s). Explicit
PostgreSQL selection: 16 passed, 154 deselected (100.19s). JUnit hashes and
counts are recorded in `docs/evidence/phase7-local.json`. Final full PostgreSQL
and the complete hosted run are still pending; intermediate full PostgreSQL
167 passed + 2 skips is retained as earlier evidence, not exact final-source proof.

The import identity guard now precedes row ownership/tax validation, closing a
membership-change race during workbook parsing on both backends. The regression
changes membership after parsing begins and proves ownership uses the refreshed
membership. Legacy upgrade assertions preserve unknown basis and NULL references.

### Hosted verification

[Run 39629880926](https://github.com/mignoncharly/kaemmerei/actions/runs/39629880926)
completed successfully for exact implementation source `2fd1bf8`. Direct GitHub
run/job API evidence confirms all four jobs: SQLite, PostgreSQL 18 service, native
PostgreSQL without Docker and real ClamAV/current definitions. Dependency setup,
migrations, complete suites, explicit PostgreSQL security selections and explicit
Phase 7 selections on both PostgreSQL environments passed. Four artifact metadata
entries were inspected; artifact archives were not downloaded. Job/step conclusions
are retained in `docs/evidence/phase7-ci-39629880926.json`.

## Final acceptance checklist and outcome

Exact application/test source: `2fd1bf85406895254d070453bbc1ced03fe7ff72`.

| Check | Actual result |
|---|---|
| Full SQLite | 170 collected; 152 passed, 18 explicit skips, 15 subtests; 129.17s |
| Full native PostgreSQL 18.3 | 170 collected; 168 passed, 2 local skips, 15 subtests; 441.32s |
| Phase 7 restricted PostgreSQL | 19 passed, no skips; 33.18s |
| Phase 7 SQLite | 18 passed, one PostgreSQL-only skip; 7.39s |
| Explicit PostgreSQL security/lifecycle | 16 passed, 154 deselected; 100.19s |
| Clean/populated/repeated Alembic head 0020 | Passed, including preserved legacy unknown basis/NULL references and schema equality |
| Historical archive/transfer reconciliation | Passed through actual HTTP/report and restricted PostgreSQL roles |
| Concurrent/atomic import and membership change | Passed on both backends |
| Hosted CI | Four jobs completed success for 2fd1bf8; run 39629880926 |
| Final read-only safety catalog | Zero harness databases, zero generated runtime roles; control role privileges unchanged |
| Municipal D08-D10 adoption | Unapproved; P07-T01 remains open |
| Production migration/deployment | Not performed or authorized by this evidence |

No test failures, errors or xfails. Local PostgreSQL's two skips are actual ClamAV
not installed/configured and Windows symlink creation not permitted for this identity;
ClamAV and Linux link checks have hosted coverage. SQLite's other skips explicitly
require PostgreSQL. Starlette/AnyIO BlockingPortal deprecation and managed pytest
cache ACL warnings remain unsuppressed. Earlier Phase 5 retained synthetic filesystem
residues and production scanner/private ACL limits are unchanged; no cleanup bypass.

JUnit hashes/counts and final catalog: `docs/evidence/phase7-local.json`. Hosted
run/job/step/artifact metadata: `docs/evidence/phase7-ci-39629880926.json`. No artifact
archive contents were inspected. Documentation-only commits after 2fd1bf8 do not
change the tested application or tests.

**Engineering outcome:** Phase 7 is technically verified. Owner acceptance and
production readiness remain open. Next technical task: P08-T01 (CSP-compatible
frontend chart behavior), preserving all existing access and transaction safeguards.
