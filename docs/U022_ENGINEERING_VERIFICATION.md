# U022 engineering verification — 22 October 2026

Verified implementation: `05648eda3ce6ddb9fe7e33082593e294522fbf24`; migration head `0027_child_read_admission`.
Subsequent documentation/evidence changes do not relabel the tested revision.
[Machine-readable sanitized results](evidence/phase9-u022-local.json) include JUnit hashes, recovery properties, platform/probe/catalog and artifact provenance.

## Executed checks

| Selection | Passed | Explicit skips | Passing subtests | Seconds |
|---|---:|---:|---:|---:|
| Actual native PostgreSQL | 343 | 2 | 15 | 830.73 |
| SQLite development | 309 | 36 | 15 | 256.04 |

No failures/errors. PostgreSQL skips concern native symlink privilege and missing actual ClamAV; SQLite additionally skips explicitly PostgreSQL-only checks. Warnings retained: Starlette/httpx deprecation, SQLite datetime adapter deprecation and Windows pytest-cache permission warning. No check was suppressed.

Commands: `python -u -m pytest --database postgresql -q --junitxml=.verification/u022-pg-final.xml` (with existing test passfile, dedicated loopback admin URL, `REQUIRE_BACKUP_ENCRYPTION=1`); same selection with `--database sqlite` and `.verification/u022-sqlite-latest.xml`. Credentials are not part of this report. Existing cluster was accessed read-only first; no launcher setup/reinitialization/ACL/service change.

## Mixed workload

`python -u -m scripts.benchmark_phase9 --mixed --output .verification/u022-mixed-thin.json` ran without competing regression suites. 10 concurrent restricted department users; 10,000 contracts, 50,000 document rows, 20,000 revisions, 1,000 tasks/reviews each, 500 inert PDFs (32,789,000 bytes). Four varied statuses exercise dated reminders; unknown/zero/known values remain distinct. 450 timed authenticated operations; department isolation passed. Synthetic scanner explicitly used.

| Operation | Requests | p95 seconds | Target seconds | Outcome |
|---|---:|---:|---:|---|
| dashboard | 50 | 0.972 | 2 | pass |
| reports | 50 | 1.866 | 2 | pass |
| history_detail | 90 | 0.892 | 2 | pass |
| bounded_export | 50 | 0.926 | 15 | pass |
| upload_scan | 50 | 3.095 | 15 | pass |
| task_create | 50 | 2.714 | 15 | pass |
| review_create | 50 | 2.631 | 15 | pass |
| login | 10 | 1.194 | 15 | pass |
| download | 50 | 0.917 | 2 | pass |

This is in-process HTTP against actual restricted PostgreSQL logins; no claim about production TLS/network, actual antivirus throughput or MFA-device timing. Writes/login have a separate 15s engineering cap. Prior five failed workloads and diagnostic plan/profile remain retained in `docs/evidence/phase9-u022-*before.json` and interim evidence; no timeout, throttling, authorization or target was weakened.

Performance changes: bounded multi-cutoff historical projection, statement-scoped child read admission preserving original RLS, thin reminder/task projections, 100-row report pages and 10-row dashboard previews. Full scoped totals and expiring populations are preserved and regressions verify page disjointness, scope, tasks and finance totals. No new financial interpretation.

## Maintenance, failure and encrypted recovery

Full suites exercise scan retries/idempotence/overlap/recovery, atomic event sequencing, local job failure/staleness/lock evidence, backup signature/hash/age/tamper, reconciliation, denied operations and actual restricted-role/MFA/security regressions. Windows task drafts remain disabled and unregistered. A current-source actual libpq refusal was detected with sanitized unhealthy output and external delivery false.

Both actual encrypted restore sizes executed. Representative backup: 4.672s; restore: 10.915s; snapshot age: 15.628s (targets 24h RPO/4h RTO). New positively identified disposable target only; all file hashes, IDs/history, MFA ciphertext/replay state and department access checked. Final read-only catalog verified zero guarded databases/generated roles and unchanged control attributes. Cluster left running.

Source built twice identically: 122 files plus manifest, 1014624 bytes, SHA-256 `99af0e49085406c03221b8a11c2107448ff4b7f1eb9cefee7728e80796bc9a08`. Manifest integrity and isolated packaged startup/migration passed under locked runtime, with no test dependencies. `pip check` passed. Artifact is local preparation, not an authorized deployment.

## Engineering and release statuses

| Status | Actual state |
|---|---|
| Development | Implemented and verified locally at the revision above |
| Synthetic technical pilot | Scope approved; local automated checks passed; actual host/scanner/browser and participant acceptance remain open |
| Real-data pilot authorization | Not granted; written data/records and relevant municipal confirmation pending |
| Broader production approval | Not granted; independent review and municipal release gates remain |

Precise outstanding dependencies:

- Existing STRATO product/tariff and authorized host inventory: Windows/native services, isolated site paths/identities, VPN/firewall, proxy/TLS and database verify-full, private ACLs, quotas and supervision. [Read-only assessment](HOSTING_ASSESSMENT.md). No credentials or platform substitution needed for this record.
- Native PostgreSQL server/client patch verification and applicability review; observed 18.3 fails enforced production floors. [R43/advisories](NATIVE_SECURITY_BASELINE.md). No exploit asserted and no native upgrade performed.
- Current-source normal-terminal browser evidence (`.verification/Invoke-U022BrowserCheck.ps1`), actual current ClamAV, representative host/network/MFA-device checks and manual accessibility/participant acceptance. Existing automated local skip/driver failure is not a pass.
- Actual host adoption of disabled task drafts, failed/stale response, off-host backup/custody/schedule and host-level restore/proxy-switch rehearsal. Local recovery measurements do not establish scheduled off-host protection.
- Written Kämmerei finance/deadline decisions and municipal records/data confirmation, translated through immutable [versioned case packets](DOMAIN_RULE_REQUIREMENTS.md); pending expected outputs remain null. Disposal disabled.
- Named selected Fachbereich/test participants and actual recorded F1–F15 business journeys; product connector scope decisions; independent security review and formal authorizations. Provisional operational roles remain valid; no new Judith permissions.

No push, external workflow/CI dispatch, deployment, website change, real municipal records, notifications, production recovery escrow or disposal occurred. The unrelated user launcher whitespace change remains unstaged.
