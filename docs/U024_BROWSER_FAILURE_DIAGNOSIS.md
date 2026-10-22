# U024: latest local browser failure and correction

Date: 2026-10-22. Corrected engineering revision: `7d6e82caab258f654d4a310142efba24998919c5`.
This is a local correction and verification record, with no push, deployment or hosted CI claim.
The approved synthetic-only pilot and outstanding municipal decisions remain unchanged.

## Confirmed failure in the specified local run

Investigated the exact run `u023-browser-5be2a5aac1e448108ca587c2624e8150`, timestamp
2026-10-22 09:05:22, source `41055a7ff4c6c0b7f49afc0f8a553200c6ecd88f`.
Its private-wrapper log is a parent runner summary; the actual exception is in that same
run's `execution/private.log`. No earlier U023 run was substituted for this investigation.

The child exited 1 with `AssertionError: pilot_clean_document_listed`, in
`pilot_browser_checks.journeys`, original line 40, via the runner's `check` helper.
The failing operation was `page.get_by_text('synthetic.txt', exact=True).count() > 0`.
The visible document metadata includes a decorative icon and a space before the filename,
so an exact text match for the filename alone finds no element. A disposable Fachbereich
HTTP reproduction confirmed status 303, a stored document in state `available`, correct
attachment download bytes, and the rendered icon-prefixed filename. The verification
selector was defective; this evidence does not establish a document-storage failure.

This local run reached the actual browser journeys: Edge startup, driver startup,
Python dependencies and source validation were not its failing operations. There is no
permission exception in this run's traceback. Parent exit 2 denotes failed verification;
it is different from child exit 1. Zero checks in the old wrapper report did not mean
no scenarios ran: the runner only wrote `result.json` after complete success, and the
wrapper's normal nonzero-child branch neither propagated diagnostics nor retained counts.

Original artifacts retained locally, unchanged. SHA-256:

| Artifact within the specified run | SHA-256 |
|---|---|
| private-wrapper.log | `37cf33db9df2a6df3d204dd0daf7fb6be3bb936e68a4e4f9a1863fab29d48e50` |
| execution/private.log | `4530f173a0196251165bb410ed5c933ce8aa637b479bbe3a9083a4902a030039` |
| execution/sanitized-report.json | `384f5289625def8263d7c58582f3050e37bd3abb26cf5706399e284a541c8445` |

Raw logs and exception messages are not copied into this document or shareable reports.

## Implemented corrections

- `scripts/pilot_browser_checks.py`: explicitly verify upload HTTP 303, match the
  filename suffix in document metadata, require exactly one matching document row,
  and download from that row. Keep the original upload/content/security protections.
- `scripts/verify_phase8_browser.py`: defer browser dependency imports into the
  reporting boundary; record dependency, driver, launch and journey stages; write a
  structured failed `result.json` with completed checks and a named failed assertion.
  Only full successful execution can write status `passed`.
- `scripts/browser_diagnostics.py`: fixed diagnostic categories and summaries;
  no exception text, authenticated URLs or variable configuration values. Validate
  source, format, synthetic scope, freshness, unique check IDs and minimum completed
  checks, including `source_unchanged`. A zero child exit with no valid passing result
  cannot establish verification.
- `scripts/run_pilot_verification.py`: propagate validated browser diagnostics and
  partial counts, reject false success, report source-validation/process-launch errors.
- `scripts/Invoke-PilotBrowserVerification.ps1`: preserve parent/child exit distinction,
  propagate safe error codes, stages, counts and failed-check identifiers; classify
  missing/malformed child reports and source/launcher failures. Source-check output
  stays in local private logs. UTF-8 BOM retained for Windows PowerShell 5.
- `tests/test_browser_diagnostics.py`: real HTTP reproduction, structured failure and
  redaction checks, false-pass prevention, runner failure injection and actual Windows
  PowerShell launcher tests with explicitly simulated child processes.

No PostgreSQL configuration, installation, service, Windows ACL, browser security option,
website or external workflow was changed. The pre-existing uncommitted
`Start-TestDatabase.ps1` whitespace edit remains unstaged and unchanged.

## Execution evidence and status

**VERIFIED:** root cause above, synthetic HTTP upload/list/download, failure-reporting
regressions, actual PowerShell parsing and failure propagation. Exact-source targeted
regression evidence is recorded in `docs/evidence/u024-browser-fix.json`: **112 passed,
4 skipped, zero failures/errors**, with source unchanged before/after execution.
The four skips are real ClamAV, Windows symlink creation, and two PostgreSQL-only MFA
checks in this explicitly SQLite targeted selection. They are not browser passes.

**IMPLEMENTED BUT UNVERIFIED:** corrected end-to-end browser scenarios. The simulated
launcher tests are diagnostic contract tests, never browser acceptance evidence.
No full PostgreSQL, mixed benchmark, recovery or hosted CI result from U023 is relabelled
as a test of this correction. Application runtime and database code were not changed.

**EXTERNALLY BLOCKED:** a separate managed-environment rerun at corrected source,
`u023-browser-d440ba05748f49afb72c8153155fc744`, stopped before Edge launch:
`PermissionError`, WinError 5, `automation_driver_permission_denied`,
`failing_stage=automation_driver`. It retained two successful fixture checks and produced
both `execution/browser/result.json` and the sanitized parent/wrapper reports. This
new managed-environment limitation is distinct from the user's specified local failure.
No permissions bypass was attempted. Browser acceptance remains unpassed.

## One next command

From the repository directory in the normal authorized Windows PowerShell session:

```powershell
.\scripts\Invoke-PilotBrowserVerification.ps1 -ExpectedSource ((git rev-parse HEAD).Trim()) -Channel msedge
```

Use the existing Python environment and installed Edge. No administrator session,
ACL changes, installation, execution-policy override or browser security changes are
required by this command. It creates a fresh UUID run under `.verification`; it does
not overwrite the failed run or touch PostgreSQL.

Share only that run's `sanitized-report.json` (the JSON printed by the command).
Expected fields: `format`, exact `source`, `status`, `exit_code`, `synthetic_only`,
`check_count`, `result_sha256`, `error_code`, `failing_stage`, `diagnostic_summary`,
`child_exit_code`, `failed_check`. Failure codes and stages must be non-null on failure;
completed counts may legitimately be zero for dependency/startup failures. The child
browser result also records a fixed exception type and numeric Windows error, if any.
A passing wrapper requires actual scenario execution and a valid source-bound passing
browser result; it does not by itself sign municipal participant acceptance or authorize
real data. No municipal decision or credentials are needed to perform this technical rerun.
