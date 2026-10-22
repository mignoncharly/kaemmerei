# U023 candidate verification and remaining actions

Verified implementation: `af290a445026e99cab6622c056993409ffa7de7e`. It descends from verified `05648eda3ce6ddb9fe7e33082593e294522fbf24` and preserves documentation follow-up `8ca205c`. Later evidence/documentation commits do not relabel unexecuted tests as passes.

Status: **PREPARED_NOT_ACCEPTED**. [Machine-readable candidate evidence](evidence/u023-candidate.json), [full procedures and R43 impact/remediation](SYNTHETIC_PILOT_ACCEPTANCE.md), [12 participant scenarios](pilot/scenarios-v1.json).

## Executed at the candidate revision

| Selection | Passed | Skipped | Passing subtests | Outcome |
|---|---:|---:|---:|---|
| PostgreSQL full, final serial rerun | 362 | 2 | 15 | pass |
| SQLite full | 328 | 36 | 15 | pass |

Both final selections have zero failures/errors. The earlier PostgreSQL full run failed with fresh-connection timeouts during contract fixture setup and role cleanup (360 passed, one failure, two errors, two skips); it is retained in the machine record with its JUnit hash. The pool-reuse case passed independently, then the entire serial run passed with unchanged connect/statement timeouts. No RLS assertion bypass or timeout relaxation was used. Root cause of the brief connection unavailability is not established; intended patched-host stability/recovery verification remains required.

A diagnostic mistakenly printed one generated test-role secret. All four leftover roles were retired only after matching OID/random marker/restricted attributes, confirming the disposable database was already absent and checking zero cross-database dependencies. No unrelated role/service/ACL changed. No real municipal credential was involved. Raw pytest logs/JUnit stay private; share only curated sanitized evidence. Final catalog: **zero guarded databases and generated roles**, unchanged control attributes; user-started cluster left running.

Both actual encrypted restore sizes executed. Representative 10k-contract/50k-document backup 4.412s, restore 9.081s, snapshot age 13.515s. All restored blob hashes, IDs/history, MFA ciphertext/replay state and restricted access checked. These local measurements do not establish scheduled off-host 24h RPO/4h RTO acceptance.

Mixed workload: 10 concurrent users, 10k contracts, 50k document rows, 20k revisions, 1k tasks/reviews each, 500 inert PDFs, four varied statuses, 450 authenticated timed operations; isolation passed. Scanner explicitly synthetic, HTTP in-process; no actual TLS/network/AV/device throughput claim.

| Operation | Requests | p95 seconds | Target seconds | Outcome |
|---|---:|---:|---:|---|
| dashboard | 50 | 0.668 | 2 | pass |
| reports | 50 | 1.465 | 2 | pass |
| history_detail | 90 | 0.603 | 2 | pass |
| bounded_export | 50 | 0.542 | 15 | pass |
| upload_scan | 50 | 2.252 | 15 | pass |
| task_create | 50 | 1.577 | 15 | pass |
| review_create | 50 | 1.480 | 15 | pass |
| login | 10 | 0.901 | 15 | pass |
| download | 50 | 0.534 | 2 | pass |

Ordinary-page <2s and bounded-export <15s targets retained. Other operations have a separate labelled 15s engineering cap.

## Skip review

The [original U022 case-by-case audit](evidence/u023-u022-skip-review.json) binds the old source and both retained JUnit hashes. Current candidate audit is in `.verification/u023-rc/evidence/skip-review.json` and hash-bound by the candidate manifest.

- **34 SQLite backend-specific skips** have passing PostgreSQL counterparts: restricted logins/RLS/context/catalog, concurrent transactions/publication, historical authorization, shared maintenance coordination, actual PostgreSQL mixed load, MFA serialization, encrypted PostgreSQL recovery/TLS guard and actual server identity. They are expected backend selection, not missing PostgreSQL coverage.
- **Two unique local environment gaps occur in both suites**: `test_actual_linked_storage_is_rejected` cannot create a native symlink under this identity; `test_real_clamav_engine_with_current_official_database` lacks a real configured engine. They remain unexecuted coverage. Adapter/path/failure tests do not substitute for them. Use an already permitted test host/CI for actual links; verify intended Windows storage independently. No permission/security-setting changes made.
- The required scanner runner reports EXTERNALLY_BLOCKED with `executed=false`, not a pass/ordinary skip. No ClamAV executable on PATH or observed standard locations. Official portable-signature retrieval through the ordinary local network path failed (URLError), and no GPG verifier was on PATH; no executable downloaded/installed. Official [downloads](https://www.clamav.net/downloads) list maintained releases; operator must verify provenance and current official definitions before required actual-engine/HTTP and heuristic/throughput checks.

## Auditable local candidate

Source bundle: [source.zip](../.verification/u023-rc/source.zip), 128 files plus manifest, 1057338 bytes. SHA-256 `7ce079d0f3af9dface7c994362c9833aeae745dfe17bbb239cb2084b97fb2eba`. Two committed-source builds are byte-identical. Manifest integrity, isolated packaged startup/migration at `0027_child_read_admission`, imports under the reused U021 isolated locked-runtime environment without pytest/httpx/PyYAML, and pip check passed. A new cross-OS clean-install result is still required from final-source CI.

[Candidate manifest](../.verification/u023-rc/candidate.json), its `candidate.sha256` sidecar and `evidence/*.json` bind source, lock/workflow/artifact/JUnit/result hashes, final and earlier failed outcomes, recovery and explicit gates. Initial assembly encountered a direct diagnostic folder without a wrapper report; incomplete scratch output was preserved, collector corrected to select actual report files, then the complete candidate assembled successfully. No source/test outcome changed for that correction.

Eight expanded CI jobs must run on the final candidate commit: locked-release Linux/Windows, release reproducibility, frontend browser, document scanner, native PostgreSQL, SQLite and PostgreSQL service. Configuration parsed locally and now requires native floors, actual-scanner HTTP checks under restricted PostgreSQL roles and the mixed workload. **Current hosted CI: NOT_RUN.** Prior hosted success at `3442ad8` supplies no current-source CI pass. Pushing/dispatching any external run still requires authorization.

## Remaining action ledger

| Classification | Gate / exact next action | Responsible role |
|---|---|---|
| VERIFIED | Current local suites, mixed workload, encrypted recovery, strict native parser/old-version rejection, scanner adapter/failure controls, evidence validator, actual PowerShell syntax and local read-only inventory execution | Engineering; evidence above |
| IMPLEMENTED BUT UNVERIFIED | Expanded browser journeys: run tracked wrapper normally using the command below, return sanitized report; managed driver fails CreateFile WinError 5. Participant and manual screen-reader checks remain separate. | Product owner/local authorized operator; engineering reviews result |
| IMPLEMENTED BUT UNVERIFIED | Eight hosted CI jobs on exact final candidate source; record run IDs/outcomes/artifacts. Authorize publishing an isolated review branch/CI run, or provide an approved equivalent runner, before engineering acts externally. | Product owner authorization, then engineering |
| EXTERNALLY BLOCKED | R43: authorize/provide reviewed patched server and matching native tools (existing 18 branch: 18.6+), then native attestation, actual roles/revocation, TLS, workload and recovery/stability checks. Observed server/pg_dump/pg_restore/psql remain 18.3; loaded libpq separately 18.4. No exploit confirmed or native upgrade performed. | Authorized system administration with product owner authorization |
| EXTERNALLY BLOCKED | Actual scanner: approved maintained clamscan, current official signatures/update provenance and scan-identity access; execute required real engine/HTTP check, then actual-host encrypted/macro/limit and throughput acceptance. No endpoint-security exclusion or daemon exposure. | Authorized scan/host operator and engineering |
| EXTERNALLY BLOCKED | STRATO: supply exact non-secret tariff/category/OS from existing product overview, then authorized read-only host inventory/capability references. Verify persistent native service, isolation from website, VPN/firewall/TLS, ACL/quota and recovery. SFTP alone is insufficient; no connector/browser account surface available here. | Product owner and authorized host operator |
| EXTERNALLY BLOCKED | Actual native link rejection and intended Windows reparse/storage checks using an already permitted identity or CI; no ACL/Windows/browser bypass. | Engineering and authorized test-host operator |
| EXTERNALLY BLOCKED | Select Fachbereich and execute/review 12 cases with actual participants and dated evidence; validator currently records 12 NOT_RUN, zero passes, no formal authorization. | Responsible Kämmerei representative, selected users, product owner/operator |
| EXTERNALLY BLOCKED | Written finance/deadline/records answers and relevant municipal confirmation, then separate real-data authorization. Pending packets retain null expected outputs; manual fields remain; disposal disabled. | Kämmerei and municipality; engineering versions/tests approved rules afterward |
| EXTERNALLY BLOCKED | Actual-host operating adoption/off-host recovery, independent security/permission review and municipal production authorization | Provisional municipal IT/System Administration, independent reviewer and municipality |

Safe browser command in the normal authorized PowerShell terminal:

```powershell
cd C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase
.\scripts\Invoke-PilotBrowserVerification.ps1 -ExpectedSource ((git rev-parse HEAD).Trim()) -Channel msedge
```

It records actual HEAD and fails on changed/uncommitted verification code. A later documentation-only HEAD is recorded as such; engineering must verify code identity against this freeze rather than silently reattribute older tests. No elevation, ACL edits, ExecutionPolicy bypass, credential request or browser security flags.

**Four statuses:** development verified locally; synthetic pilot scope approved but formal technical/participant acceptance open; real-data authorization not granted; broader production not approved. No external push/CI dispatch/deploy, website change, real municipal records, notifications, production escrow or disposal. Existing unrelated launcher whitespace remains unstaged.
