# Phase 8 — Frontend behavior and navigation

2026-10-21; P08-T01–T09, findings R21, R23–R28, R38. Implementation follows the
existing ten-phase plan. No database schema, business data, production privileges,
deployment or native PostgreSQL cluster change. Phase 7 D08–D10 and all earlier
owner decisions remain unapproved. This report separates implementation, actual
verification and remaining usability/operational acceptance.

## Changes

| Task | Behavior |
|---|---|
| T01 | Charts use external stylesheet classes `pct-0` through `pct-100`. The restrictive CSP is preserved. Exact financial groups/counts/values remain in semantic tables independently of bars. |
| T02 | One form presentation helper normalizes `automatic_renewal`, `is_active`, `can_approve` to actual booleans. Missing/unchecked/`0` stays false on validation errors; explicit true stays true. Empty/zero values and selections are preserved. |
| T03 | No notification expires automatically. Errors and substantive warnings remain. Success has an explicitly labelled close button, a polite status region and safe focus return. |
| T04 | HTML routes return consistent recovery pages for permission, not-found, CSRF/session, conflict, upload/size and parameter errors. `/api/` errors stay JSON by explicit route contract. Recoverable fields are allowlisted/bounded; passwords, CSRF/session/token credentials, unknown fields and file bytes are never echoed. |
| T05 | Approval dashboard counts distinct contracts, matching the destination population. Draft/in-progress inventory is labelled separately from review state and tax assessment. Stale revision evidence is marked. Terminal decisions expose only explicit administrator reopening; self/unassigned approval is omitted. Archive immutability remains server-enforced. |
| T06 | List and export use one authorized filter specification. Count, bounded pagination and stable `(updated_at DESC, id DESC)` ordering replace the old 500-record cap. Links preserve filters/page size. Exports fail explicitly above 5,000 records. |
| T07 | Personal inbox includes only currently assigned open tasks and currently actionable reviews at the current content revision, with active authority and parent access. Archived/closed/stale reviews are excluded; overdue review/task dates are explicit. Administrators no longer get every review labelled as personally assigned. |
| T08 | Actual double-decoded German validation text repaired without rewriting valid UTF-8. Financial/date/import explanations and recovered field labels are German. Timestamp displays retain explicit UTC; history machine timestamps carry `Z`. Raw API codes/history metadata remain stable. |
| T09 | Skip link, keyboard focus indication, scoped table headers, persistent feedback, contrast/overflow/reflow improvements and an explicit archive confirmation/recovery explanation. Real browser verification job added; actual results below, no accessibility certification inferred. |

## Navigation and export contract

- Default page size 50; accepted integer page sizes 1–100, HTML selector 25/50/100.
  Page numbers are 1–1,000,000; invalid integers/ranges return HTML 422. A requested
  page beyond the current last page is clamped to the last page, including empty
  results. Offset pagination does not promise a fixed snapshot during concurrent
  updates; refresh/count/order are evaluated for each request.
- Search and filter input lengths are bounded before queries. Department identifiers
  must be ASCII positive integers within the signed 32-bit range. Invalid values
  normalize to the documented empty filter; a department user can never override
  their authorized department using a URL parameter.
- Archived status clears dashboard focus. Other combined filters intersect. Search
  matches escaped literal text and existing status/tax labels. Both list and export
  use exactly the same normalized authorized predicates and order.
- Dashboard cards describe the complete authorized nonarchived population; their
  links reset other filters. An approval is counted once per contract even when it
  has multiple open review rows. Personal inbox and dashboard are different views.
- XLSX export ignores page/page-size and exports the complete matching population,
  up to 5,000 rows. Above that, HTML 413 asks for narrower filters; no truncated file
  is returned. Import remains limited to 500 rows and is not an export reader or a
  full-fidelity restore. Broader byte/time/concurrency limits and query performance
  are Phase 9 work; no production capacity target is claimed here.

## Error and archive behavior

Ordinary validation rerenders its existing form with safe values and a persistent
error. A conflict or HTTP error provides allowlisted read-only values where the request
has parsed them, plus links to reload/reconcile or sign in. Guest/expired-session
requests retain the existing sign-in redirect; there is no unauthenticated draft
storage, so unparsed values can require re-entry. Reloading never automatically replays a mutation.
Credentials and uploads must be entered again. Fields are allowlisted and capped
at 5,000 characters; the helper is shared with workflow conflicts and upload/token
administration handlers. Responses retain status codes and relevant authentication
headers. Parameter validation returns a bounded generic JSON error on API routes,
without reflecting raw invalid credential/query values. Trusted-host rejection
remains the middleware's own early response.

The archive UI uses an expanded confirmation explanation and required checkbox.
Its normal service contract remains the existing authenticated, CSRF-checked,
expected-version POST, so this UI step cannot be mistaken for an authorization
boundary. The archive form's field bound accommodates its actual hidden fields
and confirmation. The complete aggregate becomes immutable. There is no ordinary
unarchive route or destructive recovery shortcut; accidental archival requires an
approved administrative correction, preserving the original record/history.

Current review action choices mirror existing server restrictions. They do not
replace the server checks. Reassignment, approval, archived access and direct
mutation denial continue through the existing locked authorization protocol.

## Verification approach and environment limitations

`tests/test_phase8.py` runs on migrated SQLite and actual restricted PostgreSQL
LOGIN roles. Synthetic fixtures verify unchecked account/contract recovery,
noncredential conflict/CSRF recovery, HTML vs JSON errors, literal escaping,
507 authorized contracts beyond the old cap, stable paging/totals, cross-department
isolation, export parity/capacity, distinct approval counts, CSP classes, personal
assignment/capability/revision rules and archive controls/direct server protection.

`scripts/verify_phase8_browser.py` serves a disposable synthetic SQLite fixture
on an ephemeral loopback port and drives a real Chromium engine. It checks rendered
chart widths under actual CSP, persistent validation feedback after five seconds,
checkbox state, keyboard skip/focus behavior, semantic table headers, archive
confirmation and 390/320 CSS-pixel reflow. Screenshots and a JSON result are test
artifacts, not municipal records. The server and fixture are closed after the run.
Browser dependencies are isolated in `requirements-browser.txt`, not runtime
requirements. CI installs the matching Chromium binary using official Playwright
tooling. Local Chrome/Edge channels are supported without replacing the user's
browser profile.

Local browser surface inventory was empty. Normal pip setup could not reach the
configured proxy; official PyPI wheel metadata and SHA-256 were checked, with
verification-only wheels extracted into ignored workspace scratch after pip's
private temporary ACL also failed. Actual local Playwright execution then failed
with Windows named-pipe `PermissionError: WinError 5` before any browser started.
No Windows DACL, subprocess security policy, browser sandbox or application security
control was weakened. This is separate from the resolved PostgreSQL token error 87.
Local browser acceptance is explicitly unverified; the required hosted Linux browser
job is authoritative for the automated rendered checks.

No live assistive-technology session, complete WCAG audit, all-device visual review
or municipal usability sign-off is inferred from automated checks. Manual screen
reader interaction, representative real workflow usability and operational workload
acceptance remain release activities. Existing local ClamAV/symlink/production ACL
and retained Phase 5 synthetic-filesystem limitations remain documented.

## Reproduce

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql tests/test_phase8.py
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql
# Separate verification environment with requirements-browser.txt installed:
python scripts/verify_phase8_browser.py --channel chrome
```

Hosted browser setup: `python -m pip install -r requirements-browser.txt`,
`python -m playwright install --with-deps chromium`, then
`python scripts/verify_phase8_browser.py`. No Docker is required for local native
PostgreSQL or browser verification.

## Initial evidence state (superseded; retained history)

Initial broad SQLite regression selection: 70 passed, one explicit PostgreSQL-only
skip. Phase 8 initially 6/6 passed on both backends; a later export-capacity/action
choice regression expands it to 7 items. Full final suites and hosted browser/job
results remain pending and will be recorded after execution. No xfail or warning
suppression. Initial export-reader-cap/team-fixture failures were corrected without
changing application safety limits.

Source references: [official Playwright browser/channel installation](https://playwright.dev/python/docs/browsers),
[official launch API](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch).
These support the verification setup, not certification of this application's UI.

## Recovery and next phase

No schema migration. Frontend rollback must retain the current server authorization,
CSRF, version/archive, credential redaction and strict CSP checks. Pagination/filter
and explicit export-capacity behavior are user-visible compatibility changes and
must be retained or deliberately reviewed. Phase 9 covers availability controls,
deployment settings, maintenance, observability and operational recovery targets.

### Intermediate verification progress (superseded)

Final implementation source: `6ebcaad00e8dae84f41a5b0480c3793598541f5a`.
The review also removed editable tax-assessment controls for department users,
removed direct new-contract activation from UI choices, clarified reader versus
explicit review capability, labelled notice/end deadlines accurately and clarified
terminated end-date presentation. These are presentation changes; server authority
and activation/tax/archive rules remain independently enforced. The targeted Phase 8
selection now has eight items and passes on both backends. Earlier complete suites
passed 159 SQLite + 18 explicit skips and 175 PostgreSQL + two local skips before
these final presentation checks; they remain intermediate evidence, not final-source
full-suite claims.

The real hosted browser job passed for final source 6ebcaad in run 39635885108;
complete final run conclusions are still pending. Earlier runs 39634529672 and
39635125218 were superseded/cancelled by the workflow concurrency policy, although
the first browser job succeeded. No cancelled overall run is classified as passed.

Selected static palette contrasts against white were calculated: secondary text
#405966 7.40:1, focus #005e78 7.31:1, overdue text #8a2929 8.64:1. This is a bounded
palette check, not a full contrast or WCAG certification. The browser job exercises
actual layout/CSP/focus/reflow; screenshot archive contents have not been manually
inspected. Local browser failure and assistive-technology/manual acceptance remain
explicitly separate. Failed local pip attempts left temporary tool setup files;
no forced cleanup or permission workaround was performed. Ignored verification
artifacts and tools are not application runtime dependencies or release content.

### Final hosted evidence

[Run 39635885108](https://github.com/mignoncharly/kaemmerei/actions/runs/39635885108)
completed success for exact final implementation `6ebcaad00e8dae84f41a5b0480c3793598541f5a`.
All five actual job conclusions and steps were inspected: frontend-browser, SQLite,
PostgreSQL 18 service, native-postgresql and document-scanner. Dependencies,
migrations, full Python suites, explicit PostgreSQL and Phase 4/5/6/7/8 regressions,
real Chromium checks and actual ClamAV/current definitions passed. Five artifact
metadata entries were inspected, including browser screenshots/result output;
archive contents and screenshots were not downloaded or manually inspected.
Metadata is preserved in `docs/evidence/phase8-ci-39635885108.json`.

Final local SQLite: 178 collected, 160 passed, 18 explicit skips, 15 passing subtests
(341.85s), no failures/errors/xfails. At that checkpoint final local PostgreSQL was still in progress; its actual
completed result is recorded in the final engineering acceptance table below.

## Final engineering acceptance

Exact application/test source: `6ebcaad00e8dae84f41a5b0480c3793598541f5a`.

| Gate | Actual result |
|---|---|
| Full SQLite | 178 collected; 160 passed, 18 explicit skips; 15 subtests; 341.85s |
| Full native PostgreSQL 18.3 | 178 collected; 176 passed, two local skips; 15 subtests; 1019.38s |
| Phase 8 SQLite / restricted PostgreSQL | Eight passed on each backend; no skips; 24.17s / 97.59s |
| Explicit PostgreSQL selection | 16 passed, 162 deselected; no skips; 110.71s |
| Migrations / actual roles / restore | Existing head 0020 clean, populated, repeated upgrades and restricted-role/restore regressions preserved |
| Hosted | All five jobs passed for exact source; run 39635885108 |
| Browser rendering | Hosted Chromium CSP, errors, checkbox state, keyboard/focus, semantics and 390/320 reflow passed |
| Final catalog | Zero harness databases and zero generated runtime roles; control privileges unchanged |
| Local browser / manual AT / full WCAG / municipal usability | Explicitly unverified, not inferred from hosted automation |
| Production migration/deployment | Not performed; earlier owner decisions and operational release gates remain open |

No failures, errors or xfails. Local PostgreSQL skips are the known missing actual
ClamAV installation/configuration and Windows symlink permission; hosted jobs cover
real scanning and Linux link behavior. SQLite additionally skips actual PostgreSQL
checks. Starlette/AnyIO deprecation and managed pytest-cache ACL warnings remain
unsuppressed. Verification durations include overlapping local runs and are not a
capacity or response-time benchmark. Final metadata/hashes/contrast and catalog:
`docs/evidence/phase8-local.json`; hosted jobs/steps/artifact metadata:
`docs/evidence/phase8-ci-39635885108.json`. Archives/screenshots were not manually
inspected. Earlier progress entries above are retained as history and superseded
by this final table. Documentation-only updates do not change tested source.

**Outcome:** Phase 8 is technically verified. R23-R28 and the planned R38 navigation
scope are corrected; R21 pagination/export row bounds are corrected while broader
unbounded dashboard/report loading, export bytes/time and workload controls remain
Phase 9. Next technical action: P09-T01. No production readiness or owner acceptance
is established by this report.
