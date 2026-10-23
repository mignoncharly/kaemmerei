# Isolated Windows synthetic-pilot host requirements

Preparation only, 2026-10-22. No provisioning, deployment, service changes or remote
assessment is authorized by this document. The owner is establishing the STRATO
product/tariff in the authenticated account. [Completed access assessment](STRATO_HOSTING_ASSESSMENT.md)
confirms access, not Windows/application hosting. No further STRATO discovery is needed now.

## Candidate and isolation boundary

Approved application candidate: `3d4a180297db801293e4b86e42e9f60a55fbca86`;
hosted ten-job CI and nine preserved artifacts are [verified for that source](U026_HOSTED_CI_EXECUTION.md).
Working-tree inspection tools/documents do not create another CI-verified release.
Use an isolated clean checkout of the agreed verification revision when later running
source-bound commands. The current workspace contains uncommitted inspection sources;
`source_identity` must reject them. Do not remove/stash the owner's changes or weaken
the guard to make a run pass. Any revised application candidate needs its own checks.

The host must provide native Windows administration, a supported native PostgreSQL
installation and a TLS reverse proxy. Confirm entitlement and actual OS before deciding
whether a separate Windows VM/server allocation is necessary. A separate database or
SFTP directory on a managed webhosting account does not supply this boundary.
No silent Linux/container substitution, purchase or change to the existing projects.

| Required capability | Concrete acceptance evidence before participant access | Owner / current status |
|---|---|---|
| Host/product/administration | Non-secret tariff/category, actual Windows OS/build/lifecycle, authorized operating role and service/task-management entitlement | Owner/operator; UNVERIFIED |
| Resource isolation | Reviewed CPU/RAM/disk allocation and quotas; no reuse of existing projects' ports, service identities, binaries, databases, config or private storage without explicit review | Operator/engineering; UNVERIFIED |
| Application runtime | Native supported Python, hash-locked runtime installation, package/startup/schema checks against recorded candidate; persistent process supervision and reboot/restart evidence | Engineering after scoped provisioning approval; NOT_RUN on target |
| Private access boundary | Internal/VPN-only reachability; non-member/external denial; no public bypass to ASGI, PostgreSQL, management or scanner interfaces | Operator/security reviewer; NOT_RUN |
| TLS proxy | Approved certificate/hostname/trust chain, HTTPS secure cookies, caller-forwarded-header rejection, loopback ASGI binding and trusted proxy scope | Operator/engineering; NOT_RUN |
| PostgreSQL | Intended executing server, pg_dump/pg_restore/psql and independently loaded libpq inventory; approved patch floor; restricted per-function roles/RLS; actual verify-full TLS sessions and negative-hostname/CA tests | R43/TLS procedure; OPEN |
| Local MFA/accounts | Individual synthetic accounts, TOTP, revocation/recovery, configurable provisional business roles and department separation | Operator/engineering; NOT_RUN on target |
| Private storage | Existing approved least-privilege ACL design, symlink/junction rejection, staging/quarantine isolation, reviewed free space/quota and upload limits | Operator/engineering; NOT_RUN on target |
| Real scanner | Maintained native engine, provenance and official current definitions, actual scan identity, clean/EICAR/HTTP checks, failure/retry and inert heuristic fixtures | Scanner procedure below; OPEN |
| Workers/monitoring | Review disabled task templates and separate identities/config references; process lifecycle, failed/stale-job detection and local operator observation; no external notification activation | Provisional operator/engineering; NOT_RUN on target |
| Encrypted recovery | Coherent DB/documents/config/key references, isolated destination, local key custody, timed new-target restore and database/document/MFA/RLS integrity | Operator/engineering after exercise approval; NOT_RUN on target |
| Capacity/workload | Existing representative mixed workload: 10 users, 10k contracts, 50k document metadata plus approved inert blobs; record concurrency, latency, storage, memory and scan/backup overlap on actual allocation | Engineering after test-window approval; NOT_RUN on target |

CPU/RAM/disk quantities are not invented minimums or guarantees. Size the requested
allocation from the preserved representative benchmark, document volume/backup copies
and operator-agreed headroom; verify under the approved target workload before accepting
capacity. Do not run that workload or recovery exercise on existing STRATO projects.

Review templates, never live configuration: `deploy/windows/web-config.example.json`,
`Caddyfile.example`, `Invoke-Ohvr.ps1` and the disabled task generator. Fill non-secret
host requirements in [host-evidence.template.json](pilot/host-evidence.template.json).
Keep credentials, passfiles, certificate/private keys and MFA material outside Git and
shared evidence. The reverse-proxy example alone supplies neither VPN isolation nor DB TLS.

## R43 verification handoff

Follow [the scoped maintenance procedure](U026_POSTGRESQL_PATCH_PROCEDURE.md), including
the new evidence worksheet. Reviewed target remains PostgreSQL 18.6 or a separately
reviewed later approved minor in major 18; recheck release notes/provenance at maintenance.
The prior workstation 18.3 clients and separately bundled libpq 18.4 are historical,
not an inventory of the intended host. Hosted 18.6/16.15 results do not patch it.

After host selection, an authorized operator first supplies installation/cluster and
shared-consumer references, trusted package/signature/hash, a maintenance window and
encrypted-backup/rollback receipts. Engineering reviews these before requesting the
exact installation/start-stop scope. No installer, restart, reindex or ACL change now.

The tracked `pilot_verification native --server` probe is deliberately restricted to
an existing loopback control endpoint. It checks versions and `SHOW ssl`; it does not
prove that an application session uses verify-full or validate a remote intended host.
Do not broaden the probe to the STRATO host, put credentials in arguments or turn off
TLS to get a result. Pair native inventory with separately approved app-role session
TLS/CA/hostname evidence and the regression/restore/workload receipts. Its report
deliberately leaves `r43_closed: false`; formal closure needs that complete review.

## Scanner verification handoff

Provisioning is a separate approved operating action. Review maintained Windows binary
architecture/vendor signature/SHA-256, official definition provenance/age, freshness
update method, scan identity, protected staging/quarantine and capacity. No new scanner
installation, signature update or system scan is performed in this preparation.

The versioned [engine policy](pilot/scanner-engine-baseline-v1.json) currently accepts
reviewed 1.4.6+ or 1.5.4+ within those branches and expires 2026-11-22. Re-review before
expiry or on another branch; do not relax alerts, file limits, freshness or signature
requirements. Preserve existing ACLs and stop if the selected identity lacks access.

After authorized provisioning and exercise scope, from the clean agreed source with
operator-supplied absolute `CLAMAV_EXECUTABLE`/`CLAMAV_DATABASE_DIR` settings:

```powershell
$source = (git rev-parse HEAD).Trim()
$receipt = Join-Path '.verification' ('scanner-host-' + [guid]::NewGuid().ToString('N'))
python -m scripts.scanner_readiness --expected-source $source --output ($receipt + '-preflight.json')
if ($LASTEXITCODE -eq 0) {
    python -m scripts.run_pilot_verification --expected-source $source --selection scanner --output ($receipt + '-integration')
}
```

The first command only inventories version/definition hashes; READY_FOR_REAL_ENGINE_TESTS
is not detection or official-signature/freshness acceptance. The second creates synthetic
test resources and scans clean/EICAR fixtures; it is **not read-only infrastructure
discovery** and must run only on the approved isolated target after exercise authorization.
Missing engine/definitions, required-test skips, infected download, ranged bypass or a
signature/freshness failure blocks acceptance. Mocked and hosted Linux tests do not close
the native Windows target gate. Keep EICAR bytes and raw outputs out of shared evidence.

The runner's `scanner` selection uses SQLite for its actual-engine HTTP fixture; it
does not establish PostgreSQL scanner/RLS integration. After the same preflight and
with the dedicated restricted loopback PostgreSQL test fixture already authorized,
set `REQUIRE_REAL_CLAMAV=1` for the source-bound `postgresql` selection as well. This
requires the actual-engine case on PostgreSQL rather than accepting its normal skip.
Keep that test database separate from the empty participant register and other projects.
The PostgreSQL selection also requires provisioned native encrypted-backup tools;
missing prerequisites remain a failed/blocked exercise, not a substitute backend.

Record separately: exact clean HTTP bytes, infected-state denial including ranges,
unavailable engine/definitions and retry recovery, inert encrypted/macro/container-limit
fixtures, native path rejection and throughput while representative workers/backup run.
Do not replace reviewed fixtures with municipal files or recursive server-wide scans.

## Release and participant boundaries

No deploy/provisioning authorization follows from these requirements. The operator's
scoped proposal must list target, action, affected resources, backup/rollback, window
and stop criteria. Preserve the other STRATO projects and the current database/ACLs.
Retain provisional operational responsibilities; Judith receives no new permissions.

Start empty, then synthetic contracts only for Kämmerei plus one Fachbereich, internal/
VPN access and local TOTP accounts. All twelve participant scenarios remain NOT_RUN.
Finance/deadline interpretations and records/retention decisions remain municipal
dependencies; manual entry remains available, unvalidated results non-authoritative
and disposal disabled. External notifications and production recovery-key escrow stay
off. Independent security review, formal synthetic acceptance, real-data authorization
and broader production approval remain separate decisions.
