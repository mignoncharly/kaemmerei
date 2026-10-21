# Phase 5 — Private document lifecycle and recoverability

Date: 2026-10-21. Scope: P05-T01–T08; findings R15/R16/R33/R39.
Engineering verification and hosted results are recorded below and in U013 of
[HANDOFF](../HANDOFF.md). D05 security/operations policy and D06 records/privacy
acceptance remain pending. No business database migration or deployment performed.

## Implementation and migration

- `app/documents.py`: confined private storage, bounded static container validation,
  ClamAV adapter, durable lifecycle processing, verified attachment/range responses,
  access evidence and non-destructive reconciliation.
- `app/document_routes.py`: authorized/versioned replacement, DMS correction and
  administrator hold placement, using the existing aggregate mutation protocol.
- `app/main.py`, templates and workflow: staged uploads, state display, safe DMS
  links, availability gates and approval invalidation. No inline preview route.
- `app/config.py`: validated absolute storage/scanner paths and scanner limits.
  `app/cli.py`: explicit operator recovery and read-only reconciliation commands.
- Forward migration `0018_document_lifecycle`: digest, verified media, scanner
  result/version/time, provenance, predecessor, version, hold and retention class;
  durable `document_jobs`; forced PostgreSQL parent-scoped RLS; narrow audited
  document access function. SQLite rebuild restores archive/event triggers.
- Existing records become `legacy_unverified`, including external links. No
  invented scanner history, digest, retention classification or historic actor.
  Legacy bytes remain in place. Normal access does not silently approve them.
- Reapply reviewed role provisioning after migration for the new table/function;
  startup checks now require nine forced-RLS tables and current migration head.
  Existing migration history remains unchanged. Downgrade is refused; use forward
  repair or a compatible, verified database-and-document restore.

## Content policy and threat boundary (D05 pending)

25 MiB per file. Accepted extensions: PDF, DOCX/XLSX/PPTX, ODT/ODS/ODP, UTF-8
TXT/CSV, PNG/JPEG/GIF. Legacy DOC/XLS/PPT and RTF are rejected. Office/OpenDocument
must have the expected internal media/main parts and parseable bounded XML;
encrypted ZIP, traversal, duplicate members, symlinks, extreme expansion, XML
entities, macros, executable embedded parts, OLE objects, external relationships
and recognized dynamic external Office fields are rejected. This conservative
policy can reject legitimate documents; convert to an accepted passive format
through an approved external process. It is not a general document sanitizer.

Only a successful real scan of the exact buffered bytes permits publication.
Missing/failed scanner, invalid/stale definitions, timeout, storage error or
integrity conflict leave content quarantined and retryable. Infected content is
rejected and retained, never downloaded. The maintained ClamAV CLI is called with
stdin bytes, resource limits, encrypted/limit/macro alerts and no shell. Scanner
output is not logged; persist a bounded version string and classified result.
Definition age defaults to 72 hours (configurable 1–168); timeout defaults to 60
seconds (1–300). Freshness is checked before each scan; keep definitions updated
through official FreshClam management. No unauthenticated scanner TCP service.

Antivirus and static checks do not prove a file harmless. Downloads are attachment
only, `nosniff`, private/no-store, restrictive sandbox CSP; no PDF/Office inline
preview. A future preview origin/rendering service requires a separate review.
The default storage ACL protects against ordinary other OS identities; it cannot
protect against the application service identity, machine administrator or an
arbitrary code execution compromise. POSIX production root/staging/blobs must be
owner-only. Windows production directories must already be provisioned with only
the service identity, SYSTEM and Administrators allowed; startup reads and rejects
broader root/subdirectory ACLs and never silently changes existing ACLs. Operators
must ensure existing files inherit those private ACLs. Production Windows ACL
provisioning has not been exercised by this restricted development session.

Web, API and range requests share existing department/parent-child authorization
and lifecycle/integrity checks. Bytes are bounded, read once and hash/size checked
before returning any content. Access events contain principal IDs, requested
document ID, permitted/denied outcome and correlation; no content, secret or DMS
URL. Unauthorized references do not expose the actual parent. The outcome records
authorization/integrity, not proof a client completed the transfer.

## Durable state, retry and replacement

1. Write exclusive random-key staging file, fsync, static validate and hash.
2. Commit document metadata and job in the same database transaction. If this
   transaction fails, retain a validated staging file for reconciliation rather
   than risk deleting bytes after an uncertain commit.
3. Read/verify exact bytes, release database locks, then perform external scanning.
4. Reacquire identity and parent locks; revalidate authority, archive state and
   current document. Verify the source bytes again. HTTP processing awaits a
   thread-pool worker so the scanner cannot block the ASGI event loop. Atomically rename within the
   same filesystem (legacy flat file recovery copies and retains the original).
5. Commit available state, scan evidence, job outcome and audit together. A crash
   after file publication but before commit leaves an unavailable metadata state;
   retry recognizes the final path and safely completes publication.

Repeated completion is idempotent. Concurrent recovery may duplicate scanning but
cannot bypass publication checks. A slow scan holds no database writer lock; an
archive completed during scanning prevents later publication. Initial processing
runs after upload commit; interrupted/unavailable attempts require operator retry.
There is no new unattended scheduler; job queue monitoring and retry scheduling
are explicit operational responsibilities until Phase 9.

Replacement creates a new ID/key/hash and keeps the predecessor bytes and metadata.
The old available version remains current until the new one scans clean, then
becomes superseded. An outstanding replacement blocks another replacement/link
correction of that predecessor. A legal hold survives supersession. Upload/link
correction changes content revision and invalidates approvals; approval/activation
also reject unavailable or unverified current documents. Superseded bytes are
retained but not served by ordinary download routes. No administrative historical
download or archive mutation bypass has been introduced.

External DMS URLs are HTTP(S), without credentials/control characters; production
requires HTTPS. `DMS_ALLOWED_HOSTS` optionally restricts exact hostnames. Empty
means any otherwise valid host, and must be accepted or tightened under D05.
Correction creates a successor and retains the previous URL. Links are never
fetched by this application; no DMS connector, SSRF fetch or remote scan implied.

## Operator configuration and reproduction

Use secrets/process-manager configuration already established in Phase 3. Do not
print database URLs/passfiles. `.env.example` documents nonsecret setting names;
the application does not automatically load `.env` files.

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database sqlite
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra tests/test_phase5.py --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -m postgresql --database postgresql
```

The existing launcher sets TEST_POSTGRES_ADMIN_URL and PGPASSFILE for this terminal.
It uses the dedicated native cluster and never requires Docker. Do not reinitialize
the working cluster. Real scanner verification additionally requires an installed
supported ClamAV engine, absolute `CLAMAV_EXECUTABLE`, a private managed definition
directory in `CLAMAV_DATABASE_DIR`, and a successful official FreshClam update:

```powershell
$env:REQUIRE_REAL_CLAMAV='1'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q tests/test_phase5.py -k real_clamav
```

Use the official Windows installation/signature management instructions linked
below; engine installation/production definitions are not performed here. No
synthetic scanner option exists in application configuration. Test fixtures inject
a clearly named synthetic scanner; that validates lifecycle behavior, not malware
detection. The separate hosted scanner job requires real clean/EICAR results and
current official definitions, and fails rather than skips when unavailable.

For a configured operator process (review target identity/settings first):

```powershell
& 'C:\kämmerei\.venv\Scripts\python.exe' -m app.cli document-reconcile
# Replace 123 with the authorized document ID from the reconciliation report:
& 'C:\kämmerei\.venv\Scripts\python.exe' -m app.cli document-recover --document-id 123
```

With enforced database security these commands require the explicit privileged
operator connection, never injected into web workers. Reconciliation reports
IDs/approved random keys for missing, mismatched, pending, orphan and unsafe
entries. Preserve unknown files. Investigate ownership, interrupted writes and
backup lineage before any separate authorized cleanup. Archived legacy files
remain unavailable: a records-approved archival correction procedure is required;
normal recovery does not defeat the archive barrier.

## Retention and disposal design (D06 pending)

Default classification is `unclassified`; eligibility is always false. An admin
may place a hold on a mutable current document; repeat placement conflicts, and
hold survives replacement. There is no release, deletion/anonymization endpoint
or destructive job. Archived hold placement needs an explicitly approved records
procedure; all disposal remains blocked globally in the meantime.

Before implementing disposal, the records/privacy owner must approve a matrix:

| Surface | Required decision and evidence |
|---|---|
| Current/superseded/quarantined/legacy blobs and metadata | Class, legal basis, trigger date, duration, scope, hold priority, accountable owner |
| Revision snapshots and immutable audit | Separate retention/legal basis; authorized minimization compatible with integrity; no broad history deletion |
| Exports and downloaded copies | Ownership and recall limitations; export retention and user obligations |
| Backups/replicas | Expiry, immutability, restore reapplication of holds/disposal tombstones, no false claim of immediate erasure |
| External DMS | System of record, delegated authority, connector confirmation and independent DMS holds |

Proposed future process: classify -> compute eligibility excluding any hold ->
records approval + independent authorized executor -> dry-run exact IDs/versions/
hashes/surfaces -> durable idempotent disposal job -> revalidate holds/version at
execution -> record minimized signed/append-only evidence and reconciliation ->
separate backup/DMS expiry confirmation. Failures retry without broad deletion;
two-party authority, retention periods, tombstone content and anonymity requirements
are decisions, not implemented permission grants. Existing audit append-only
controls must not be disabled to implement disposal.

## Consistent backup, restore and capacity

Stop accepting writers and drain upload/recovery/import workers before taking a
database-and-entire-storage snapshot. Include staging, blobs and retained legacy
files plus schema/role configuration, scanner provenance, hold and job metadata.
Keep the pause until both snapshots finish (or use a separately reviewed atomic
snapshot/manifest protocol). A DB-only backup is insufficient. Store backups with
private access, encryption, retention and restore credentials governed by operations.

Use matching PostgreSQL major pg_dump/pg_restore. Forced RLS means a dump using a
runtime role can be incomplete: the test uses the trusted owner with a deliberate
full-scope policy and `--enable-row-security`, not web/integration credentials.
Confirm full table/row counts and a hash manifest before accepting a backup; that
option alone does not establish completeness. Restore into an identified empty
isolated database and a fresh private storage directory, with application writers
stopped. Restore schema/data/security objects, provision target least-privilege
roles explicitly, run schema/role checks and reconciliation, verify hashes and
authorized/unauthorized downloads, then authorize cutover. Never overwrite a live
database or copy blobs into an unverified web root.

The automated synthetic round trip actually uses SQLite backup or PostgreSQL
custom-format pg_dump/pg_restore, copied storage, matching hash and allowed/denied
downloads. It does not establish production RPO/RTO, encryption/key recovery,
full-volume restore performance, or business-data completeness. Restored test app
uses the trusted test owner; production restricted role reprovisioning remains an
operator release step, already separately regression tested by Phase 3 fixtures.

Multiple workers must share the same private filesystem and database; staging and
blobs must support same-filesystem atomic rename. Independent worker-local storage
will produce missing blobs and is unsupported. Do not use a public static alias.
Monitor filesystem free bytes/inodes, database growth, pending/retry age/count,
orphans/missing/mismatches, scan failures/timeouts and definition age. Alert before
capacity exhaustion and on any integrity mismatch. Run read-only reconciliation
on a recorded schedule and after restore. Production thresholds, alert delivery,
queue automation and concurrent throughput/load testing remain Phase 9 work.

## Verification evidence and limits

Final full-suite, explicit PostgreSQL, hosted and cleanup results are appended
after execution; see `docs/evidence/phase5-local.json` and U013. No skipped check
is counted as a passing scanner, RLS, filesystem or production verification.

Development Windows issue discovered during verification: Python 0700 mkdir
created a DACL inaccessible to this managed restricted token. Development now
inherits workspace ACLs; production still demands operator-provisioned private
ACLs. One known empty failed fixture directory remains inaccessible:
`.verification/tmp/ohvr-test-b759c159c20640fba62b270da31292cf/documents`.
No contract bytes were written there. Normal operator cleanup may remove this
exact empty directory after checking it is empty; the agent did not broaden ACLs.
Two failed synthetic restore fixture directories also remain under the same
ignored temporary root: `ohvr-test-56ef7cdaa45a4cdaa9067d62e93034cf` and
`ohvr-document-restore-f608d2338d404f8180d987543699761b`. Automatic approval review
rejected their narrowly targeted recursive cleanup because sandbox approval is
disabled. No alternative deletion method was used; operator cleanup remains.
The native PostgreSQL cluster, identity guard, passfiles and services are preserved.

### Primary references

- [ClamAV scanning and limits](https://docs.clamav.net/manual/Usage/Scanning.html)
- [Official signature management](https://docs.clamav.net/manual/Usage/SignatureManagement.html)
- [ClamAV CLI macro-alert option](https://github.com/Cisco-Talos/clamav/blob/main/docs/man/clamscan.1.in)
- [PostgreSQL 18 pg_dump and row security](https://www.postgresql.org/docs/18/app-pgdump.html)
- [Official signed PostgreSQL Ubuntu packages](https://www.postgresql.org/download/linux/ubuntu/)
