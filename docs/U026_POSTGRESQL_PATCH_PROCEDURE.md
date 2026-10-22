# R43 PostgreSQL 18.6 maintenance proposal — not authorized or executed

Reviewed 2026-10-22 against the official [version policy](https://www.postgresql.org/support/versioning/),
[minor upgrade procedure](https://www.postgresql.org/docs/18/upgrading.html),
[18.4 notes](https://www.postgresql.org/docs/release/18.4/) and
[18.6 notes](https://www.postgresql.org/docs/release/18.6/).
The published current 18-series minor is **18.6**, also the repository floor.
Recheck at approval: a newer minor needs release-note/provenance review. No installer
was downloaded or run. This proposal does not authorize maintenance.

## Scope and read-only preflight

Prefer an independently provisioned patched synthetic host if approved. Otherwise
the operator must identify the Windows machine, architecture, distribution, exact
cluster, data/tablespace locations, port, shutdown/start mechanism, executable
consumers, maintenance window, encrypted backup destination and rollback owner.
The native test cluster need not be a Windows service. Shared Program Files binaries
may serve unrelated clusters: inventory consumers and approve scope before replacement.
SFTP/STRATO access supplies neither this authorization nor proof of Windows hosting.

Keep the existing website, unrelated services, ACLs and Start-TestDatabase.ps1 unchanged.
Never reinitialize existing data. A same-major minor update does not use initdb or
pg_upgrade. Approval must separately identify installation and stop/start scope.

With the operator's existing local control URL/passfile, use a new output each time:

```powershell
python -m scripts.pilot_verification --expected-source ((git rev-parse HEAD).Trim()) --output .verification/r43-before-UNIQUE.json native --bin 'C:\Program Files\PostgreSQL\18\bin' --server
```

This executes version commands and read-only SHOW queries. An unreachable server is
unknown; postgres.exe --version identifies an installed binary, not a running server.
Inventory pg_dump, pg_restore, psql and the separately loaded psycopg/libpq. Do not
start a stopped cluster merely to obtain this observation without authorization.

Review read-only extension/index/plugin catalogs in **each affected actual database**;
the control database cannot establish absence elsewhere. The 18.6 release notes call
out non-default logical decoding output_plugin_libraries, pgcrypto PGP ciphertext
created with unsupported ciphers, failing scripted COPY FROM STDIN terminators, GIN
table reltuples and btree_gist/ltree index conditions. Review applicability/version
conditions before scheduling repairs. Do not automatically reindex, reencrypt, alter
parameters or enable ignore-cipher-failure. App Fernet/age use does not establish
that separate pgcrypto use is absent. Existing R43 RLS-plan and pg_dump impacts remain
documented in SYNTHETIC_PILOT_ACCEPTANCE.md; this is not exhaustive advisory clearance.

## Backup and go/no-go after scoped authorization

1. Verify space, maintenance identity and protected encrypted destination. Pause only
   the identified application writers/jobs; retain external-workflow/disposal-disabled
   settings. Do not change unrelated applications or the website.
2. Create a coherent encrypted DB/document backup with trusted patched matching clients
   after authorized provisioning. Include recovery roles/grants, migrations, config,
   document hashes and key references. Global dumps may contain credential hashes:
   never print dumps/keys. Vulnerable pg_dump must not consume untrusted metadata merely
   to make a pre-upgrade backup.
3. After clean authorized shutdown retain a recoverable cold copy/snapshot of PGDATA,
   external tablespaces, config, compatible extension libraries and original binaries.
   Preserve owner/ACL metadata with the approved backup method, without re-ACL changes.
   A live directory copy alone is not a consistent backup.
4. Rehearse restore into a new isolated target; verify IDs/history/blob hashes, MFA state
   and restricted access. Prior U023 measurements do not verify this maintenance backup.
   Without verified backup and rollback targets, stop preparation before installation.
   Keep keys under provisional local custody; no new external escrow.

## Authorized execution sequence — not executed here

- Verify approved vendor package architecture, digital signature, independently recorded
  SHA-256 and 18.6 component versions. Exact installer/hash and extension/runtime review
  are still operator dependencies, not invented approved artifacts.
- Cleanly stop only the selected cluster after writer pause and verify it is stopped.
- Update compatible 18-series binaries using the distribution's supported maintenance
  mechanism. Preserve data/config/port/identity/permissions; do not apply defaults to
  another service or replace shared binaries beyond approved scope.
- Restart the selected cluster and recycle old application/database sessions. Verify
  the executing server and pg_dump/pg_restore/psql at 18.6+, matching major. Native
  installation changes do not update psycopg's independently bundled libpq; review it
  separately before any dependency change.

## Post-upgrade tests and rollback

At the final candidate run native attestation; full restricted PostgreSQL, MFA/RLS,
revocation and pool-reuse regressions; actual scanner HTTP checks; encrypted DB/document
backup and isolated restore; serial mixed 10-user/10k-contract/50k-document benchmark;
monitoring failure/recovery; intended-host TLS/negative hostname, service restart,
quota and read-only ACL checks. Observe fresh-connection stability after the earlier
recorded timeout. Retain source-bound sanitized reports and private raw logs.
Commands are the tracked native/postgresql/mixed/scanner runners and exact final CI
workflow. Baseline success does not automatically close R43 host review or acceptance.

Keep writers paused until go/no-go. On startup, version, integrity, access or restore
failure, preserve diagnostics and stop only the selected upgraded cluster. The
authorized operator restores compatible original binaries/config plus the verified
pre-maintenance cold state, tablespaces, documents and key references to the reviewed
target. Never overwrite a running cluster. Rehearse isolated recovery first. If writes
resumed, agree reconciliation before a rollback that could discard them. No automatic
destructive rollback script is supplied or executed.

An 18.3 rollback reintroduces known exposure: keep it isolated with no real-data use,
production opening or R43 closure, and schedule a newly approved remediation.

## Intended-host evidence worksheet (prepare now; execute only after approval)

The successful STRATO SSH/SFTP assessment does not identify Windows, a PostgreSQL
installation, service rights or a maintenance target. Await the owner's product/tariff
evidence; do not use additional server probes or existing website databases to fill gaps.
Use [the isolated Windows requirements](WINDOWS_SYNTHETIC_PILOT_REQUIREMENTS.md).

| Receipt | Required contents / pass condition | Current state |
|---|---|---|
| Scope | Approved Windows host/cluster references, distribution/architecture, shared binary consumers, responsible operator, window and exact permitted actions | NOT_PROVIDED |
| Native inventory | Installed binaries separately from executing server, version numbers/digests for pg_dump/pg_restore/psql, loaded psycopg/libpq implementation/version, matching major and approved patched minor | NOT_RUN on intended host |
| Vendor/update review | Approved package signature/hash/source, extension compatibility and release-note applicability decisions; no automatic repairs | NOT_PROVIDED |
| Protected backup | Coherent encrypted DB/documents/config/role/key-reference receipt, validated isolated restore and cold rollback target; no secrets in shared record | NOT_RUN on intended host |
| Actual TLS sessions | App-role session encryption and verify-full CA/hostname success; incorrect CA/hostname rejected with no plaintext fallback | NOT_RUN on intended host |
| Post-maintenance regressions | Source-bound restricted PostgreSQL/RLS/MFA/pool tests, scanner, monitoring/restart, workload and encrypted restore; zero unexplained required skips | NOT_RUN on intended host |
| Closure decision | Operator/engineering review links all receipts, observations, exceptions and residual gates; no automated R43 closure from a version-only pass | OPEN |

The existing native probe only permits an existing loopback control URL; `SHOW ssl`
reports server capability, not negotiated encryption or application verify-full policy.
Do not repoint it to remote STRATO or weaken its endpoint/source controls. Version
baseline success deliberately keeps `r43_closed: false`. No new TLS sessions, database
catalog reads, fixture writes or maintenance were executed for this worksheet.
