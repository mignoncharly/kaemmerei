# Phase 9 - Availability and operations

2026-10-21, update U017. **In progress, not accepted.** This continues the existing
ten-phase plan after U016; it does not start Phase 10 or authorize a deployment.
Implementation base: `b962824`; advisory guards: `1cecc54`; compatible patched dependency source: `1649b15`. Local verification results are recorded below
when execution finishes. The initial push failed through the configured proxy; a normal retry succeeded.
Hosted run [39644065729](https://github.com/mignoncharly/kaemmerei/actions/runs/39644065729)
passed all five jobs for guarded source 1cecc54. Patched dependency run
[39645201928](https://github.com/mignoncharly/kaemmerei/actions/runs/39645201928)
passed all five jobs for 1649b15. [Verified run/job/step/artifact metadata](evidence/phase9-ci-39645201928.json).

## Implemented controls

| Area | Actual behavior |
|---|---|
| Request ingress | Outer ASGI middleware counts actual streamed bytes before starting multipart parsing. Declared length cannot bypass this; duplicate, negative and inconsistent lengths fail closed. Total receive plus parse deadline defaults to 30 seconds. |
| Capacity | Immediate 503 with Retry-After when 16 active requests or four multipart requests are admitted; no application admission queue. Counters remain held through response/background completion and release on errors. These counters are per process. |
| Forms | Default multipart aggregate 32 MiB, five files, 25 MiB per file, 40 fields, 64 KiB per field, 256 bytes per field name. Non-multipart requests additionally have a fixed 1 MiB ceiling. URL-encoded separator bombs are rejected before per-field allocations. Route limits remain stricter where configured. |
| Parser cleanup | Opened multipart files close after success, rejection, timeout or cancellation, including unfinished parts absent from FormData. This uses the opened-file list in pinned Starlette 0.50.0; reverify on parser upgrades. |
| Private storage | Staging checks an application quota of 10 GiB and a 256 MiB free-space reserve. Counts root legacy files, staged/blobs and orphan files; does not remove anything. Existing database identity mutation lock serializes application upload writers. External writers and multipart temporary storage still require operator volume quotas. |
| Login | Database-backed 15-minute account/IP/network/global reservations before Argon2: 32/32/128/512 respectively, plus existing eight failed username/IP pairs. IPv4 /24 and IPv6 /64 network budgets; only digests persisted. Successful login does not reset spraying budgets. No permanent account suspension introduced. Password-change pair protection remains. |
| API | Shared one-minute credential/IP/global budgets 120/240/1200 include invalid credentials and rotating tokens. Atomic PostgreSQL SECURITY DEFINER reservation under a short advisory lock; integration has no direct login-attempt table grants. SQLite uses the existing identity lock. Counter transaction completes before the business read. V2's required second authorization check does not reserve twice or commit its synchronization transaction. |
| Blocking work | All POST handlers now use synchronous FastAPI worker execution. Middleware parses once; workers access the parsed form and perform DB/hash/Excel/file work off the event loop. Existing staged jobs and fail-closed scanner behavior remain. Long scans still run within request workers: durable background scheduling is unfinished. |
| Database capacity | PostgreSQL defaults: pool eight per engine, overflow zero, pool wait five seconds, connect timeout five seconds, SQL statement timeout 15 seconds and lock timeout five seconds. Integration inherits the configured limits. Pool exhaustion returns a generic 503. |
| Export | Existing 5,000-row rejection preserved; department eager loading avoids an export N+1 query. Additional 8 MiB source-text/output bounds and cooperative 10-second row assembly / 15-second completion checks. These checks reject late completion; they are not a preemptive CPU timeout for XML/ZIP generation. |
| Proxy/TLS | Forwarded identity ignored unless the actual socket peer matches explicit configured proxy networks. Trusted proxies must overwrite a single X-Forwarded-For address and X-Forwarded-Proto value. All-address trust rejected. Production rejects HTTP at the application boundary and requires verify-full PostgreSQL TLS plus an absolute CA path on web/integration URLs; CLI-selected operator URL revalidated. |
| Observability | Server-generated X-Request-ID also enters database request context. Structured request records contain event, correlation, status, milliseconds and body byte count only. No URL/query, body, credentials or client identity. `/health/live` returns 204; `/health/ready` probes both engines with SELECT 1 and returns 204/503. Readiness is connectivity, not a scanner/backup/maintenance readiness certificate. |

Defaults are engineering capacity bounds, **not agreed workload or recovery targets**.
Repeated failures can temporarily deny an account/network access until its window
expires; D11 load testing and operational review must assess these tradeoffs.
Single-process admission protects each worker; installation-wide request/storage
quotas, trusted TLS termination and process supervision are deployment work.

## Database and rollout implications

Additive Alembic `0021_availability` adds composite key/time and cleanup-time
indexes to login_attempts and the narrow PostgreSQL API reservation function.
No business records are backfilled, removed or reclassified. Existing RLS,
archive/workflow checks, synchronization barriers and native cluster safeguards
remain. Runtime role grants must be reapplied after the migration so integration
can execute the new function. Web/audit roles cannot execute it; PUBLIC is revoked.

The existing role provisioning script incorrectly pinned head 0019 even after
0020 was introduced. It now compares the database revision with `migration_head()`.
This resolves that deployment blocker without silently migrating an existing DB.

For an authorized application rollout: take the approved consistent backup first;
run existing owner migration/inventory steps; apply existing DBA-reviewed role
configuration with the named application DB and four existing roles; validate
restricted runtime startup and API smoke tests. Never point provisioning or
integration tests at postgres/template databases. Production rollout and actual
TLS/CA/proxy/service tests have **not** been performed by this update.

Forward-only migration: retain new indexes/function when rolling back application
code; do not drop counters, disable RLS or restore an older incompatible schema.
Rollback artifacts and a consistent database/document restore remain release gates.

## Reproduction on the native Windows test installation

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra tests/test_phase9.py --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra -m postgresql --database postgresql
```

Launcher sets TEST_POSTGRES_ADMIN_URL and PGPASSFILE in the current terminal;
never print their contents. Tests use only positively identified, newly generated
test DBs and generated restricted roles. No Docker, cluster initialization or
service replacement is required. Historical Windows token error 87 remains resolved.
The known managed-agent launcher ACL boundary is separate from cluster readiness.

`.env.example` documents the new settings. Example server boundary for an
operator-provisioned private TLS proxy (not a deployment or service install):

```powershell
& 'C:\kämmerei\.venv\Scripts\python.exe' -m uvicorn app.main:app `
  --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers `
  --limit-concurrency 32 --backlog 32 --timeout-keep-alive 5 --no-access-log
```

Disable Uvicorn's automatic forwarded-header rewriting; otherwise socket-peer
validation cannot establish which proxy supplied the identity. Set trusted networks
to actual proxy addresses only. Proxy must enforce the same body ceiling and an
overall slow-body deadline, overwrite forwarded headers, restrict backend exposure,
redirect external HTTP to HTTPS, use a verified certificate and enable HSTS only
after HTTPS verification. Multipart aggregate 32 MiB intentionally rejects five
25 MiB files in one request: use smaller batches. A disk quota for private
application storage **and the process temporary directory** is still required.
Do not expose debug logs or proxy access logs containing query/token/body values.
The `ohvr.requests` logger must be explicitly configured at INFO with a message-only
handler in the service logging configuration to collect the JSON records. Default
Python logging can suppress INFO; no deployed collection/alert pipeline is claimed.
Uvicorn access logging is disabled above because its default request line can
include a query string. Restrict logs and their approved retention operationally.

## Verification status

Targeted regressions cover streamed/declared/slow requests, field/file limits,
parser timeout cleanup, admission recovery, proxy spoofing and HTTPS enforcement,
login spraying across application instances with expiry, concurrent API admission,
restricted integration table denial, v2 double-authorization compatibility, sync
POST handlers, liveness during blocked hashing, redacted correlation and storage
quota/legacy accounting. Production TLS configuration is checked without claiming
an actual deployed TLS handshake. Existing full suites remain the regression gate.

During development, an invalid direct-ASGI test supplied mixed-case headers
contrary to ASGI; corrected the harness. Testing then found and fixed multipart
exception handling, inactive-account/admin denial ordering and the v2 second-write
transaction issue. Earlier runs with those defects are failed intermediate evidence,
not acceptance passes. Final counts and evidence references are appended below.

## Remaining Phase 9 tasks and exact next work

| Plan task | State / next implementation and verification |
|---|---|
| P09-T01 | Application controls implemented; actual proxy/volume/temp-storage quota and slow/chunked deployment probes outstanding. |
| P09-T02 | Shared budgets implemented; distributed spraying/load review and installation-specific trusted proxy verification remain. |
| P09-T03 | Synchronous handlers/admission implemented; separate scan/export job scheduler, bounded claims/retries and failed-job recovery gate outstanding. |
| P09-T04 | Export bounds/eager department loading implemented; unbounded dashboard/report/import-comparison populations and historical aggregate cost still need scoped SQL optimization. Establish and record D11 dataset/concurrency/latency targets before benchmarking. |
| P09-T05 | Existing narrow purge/reconcile/recovery commands remain; scheduled coordinator, lock-safe retry claims, heartbeats and expiry/publication monitoring outstanding. No automatic event/cursor/audit deletion while D06/D07 retention undecided. |
| P09-T06 | Dashboard/manual reminders retained and explicitly documented. No external messages sent, configured or claimed. D13 notification/product scope adoption outstanding. |
| P09-T07 | Application proxy/TLS/URL validation implemented; actual target hosting, private volume/temporary ACLs, secret injection, certificate/DB TLS, supervision and network restrictions need provisioned-target evidence. |
| P09-T08 | Correlation/log redaction and basic health checks implemented; metrics, actionable thresholds and alerts for auth/pool/job/scanner/disk/backup/feed failures still outstanding. Test destination/owner not assigned; no alert-delivery claim. |
| P09-T09 | Existing synthetic consistent DB/blob restore regression retained; scheduled encrypted backup/access/retention/restore automation and approved/measured RPO/RTO remain outstanding. No production backup or restore occurred. |
| P09-T10 | D12 local-account versus SSO/MFA/recovery policy unapproved; no provider selected, no MFA enrollment/recovery implementation. Broad human access remains blocked. Existing service tokens remain separate from browser sessions. |
| P09-T11 | Current primary review, compatible patched dependencies, installed/runtime inventories and OSV query for 28 Windows runtime versions completed (below). Development/OS/tool scans, transitive hash lock, reproducible release manifest and verified artifact exclusion/build remain outstanding. No blanket vulnerability-free claim. |

Next engineering work starts with P09-T03/T05 durable maintenance/job execution, followed by
P09-T04 workload optimization, P09-T08 alert delivery and P09-T09 encrypted recovery
automation. Obtain D11/D12 target/identity/recovery decisions and accountable owners
in parallel; do not infer them from engineering defaults. Keep R07/R21/R22 and the
phase exit gate open until these remaining controls have actual evidence. Newly
reviewed dependency advisories are tracked as High finding R42 (U017), separate
from baseline R40 distribution hygiene.

## Current dependency advisory review and compatible upgrade

Primary maintainer advisories reviewed on 2026-10-21, initially against Starlette
0.50.0 and python-multipart 0.0.29. This is a focused review, not an exhaustive
dependency vulnerability scan. [Installed name/version inventory](evidence/phase9-dependency-inventory.json)
contains no package paths, credentials or authenticated source URLs and is **not**
a reproducible release lock.

| Advisory | Maintainer affected/patched range | Application action / residual |
|---|---|---|
| [Multipart quadratic semicolon parsing](https://github.com/Kludex/python-multipart/security/advisories/GHSA-5rvq-cxj2-64vf) - High | Below 0.0.30 / fixed 0.0.30 | Installed 0.0.29 affected. URL-encoded bodies now use bounded Python parse_qsl with explicit ampersand separator, bypassing QuerystringParser entirely. Semicolons in a value remain a value; encoded semicolons work. Regression patches the vulnerable parser to fail if called. Patched dependency adopted below. |
| [Starlette URL-encoded limits ignored](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq) - High | 0.4.1 to below 1.3.1 / fixed 1.3.1 | Installed version affected. Ingress counts bytes/fields before parsing, uses bounded standard parser and enforces decoded field bytes. Does not rely on ignored framework parameters. Compatibility upgrade is pinned/adopted below. |
| [Windows StaticFiles UNC credential disclosure](https://github.com/Kludex/starlette/security/advisories/GHSA-wqp7-x3pw-xc5r) - High | Below 1.1.0 / fixed 1.1.0 | Installed version affected on Windows. Outer boundary rejects backslash/drive/noncanonical paths before StaticFiles or filesystem resolution. Regression traps realpath to prove no resolution occurs for these inputs; no real SMB host contacted. Patched dependency adopted below; block outbound SMB for service identity as deployment defense. |
| [Host poisons request.url.path](https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr) - Moderate | Through 1.0.0 / fixed 1.0.1 | Existing explicit TrustedHost retained; new raw Host ambiguity/duplicate rejection precedes routing. All security path decisions use ASGI scope path instead of reconstructed URL. |
| [Non-slash path poisons URL authority](https://github.com/Kludex/starlette/security/advisories/GHSA-jp82-jpqv-5vv3) - Low | Below 1.3.0 / fixed 1.3.0 | Boundary requires a single initial slash; rejects malformed/double-slash paths before URL reconstruction/routing. |
| [Multipart unbounded headers](https://github.com/Kludex/python-multipart/security/advisories/GHSA-pp6c-gr5w-3c5g) - High | Below 0.0.27 / fixed 0.0.27 | Installed 0.0.29 is outside this reported range; total ingress limits add application bounds. This says nothing about other advisories. |

The initial distributions were in affected ranges; the application guards above
were implemented before upgrade. Repository and adopted environment now use patched
versions below. Those controls remain as defense at the application boundary.
The original FastAPI constraint (Starlette <0.51) was respected by selecting a
compatible FastAPI upgrade, rather than forcing a new Starlette under the old pin.

Retrieval history: initial Git network failure recovered on a normal retry.
Inherited PIP_NO_INDEX and unsuccessful package retrieval produced no usable wheels;
failed responses were preserved with .invalid suffix and never executed. Subsequent
permitted direct downloads matched official PyPI SHA256. No TLS/proxy/ACL/sandbox
control was disabled, and no third-party package source was patched in place.

### Adopted patched package set and advisory evidence

After normal repository access recovered, direct downloads through the permitted
public download tool succeeded and matched official PyPI SHA256. Source 1649b15
pins FastAPI 0.158.0, Starlette 1.9.0, python-multipart 0.0.32 and its required
OpenTelemetry API 1.44.0. Official FastAPI metadata accepts Starlette >=0.46.0;
the old FastAPI <0.51 constraint no longer applies. No SDK/exporter or external
telemetry delivery is configured. No third-party source was patched in place.

The first candidate ran in an ignored package overlay, preserving the shared
virtual environment during compatibility checks: 31 focused checks, full SQLite
181 passed + 18 skips, and 21 actual-role PostgreSQL checks passed. The verified
wheels were then adopted into the project virtual environment. The first offline
installer attempt left FastAPI incomplete; a normal offline retry repaired it.
Two obsolete pip backup directories were preserved under ignored
`.verification/phase9-adoption-backups`, after checking resolved source/target paths;
the two backup directories were moved intact; no backup files were deleted or ACLs weakened. `pip check` now reports no broken
requirements, without invalid-distribution warnings. All four actual installed
versions match their pins and the verified wheel digests in the inventory.

[Installed before/after inventory and wheel provenance](evidence/phase9-dependency-inventory.json)
and [28-package runtime closure](evidence/phase9-runtime-dependencies.json).
A real [OSV querybatch](https://google.github.io/osv.dev/post-v1-querybatch/) query
returned zero matches and no pagination for those exact 28 Windows runtime versions:
[request and response evidence](evidence/phase9-osv-runtime.json). This excludes
OS/PostgreSQL/Python/browser/development tooling and unknown vulnerabilities; it is
not an exhaustive security certificate or a transitive release hash lock.

All five exact-source hosted jobs passed for 1649b15. Final direct virtual-environment
runs (without the candidate overlay) and native cleanup evidence are recorded
below. HTTPX test-client compatibility deprecation and managed pytest cache ACL
warnings remain unsuppressed. R42's reviewed affected ranges are corrected; recurring
scans, wider tool/OS review, transitive hash lock, reproducible release manifest and
distribution exclusion checks remain P09-T11 tasks. Phase 9 exit remains open.

## Verified checkpoint: adopted environment, source 1649b15

| Selection | Collected | Passed | Skipped | Passing subtests |
|---|---:|---:|---:|---:|
| Native PostgreSQL full | 199 | 197 | 2 | 15 |
| SQLite full | 199 | 181 | 18 | 15 |
| Explicit PostgreSQL | 16 | 16 | 0 | 0 |
| Phase 9 PostgreSQL | 21 | 21 | 0 | 0 |
| Phase 9 SQLite | 21 | 21 | 0 | 0 |

All final selections had zero failures/errors/xfails. Two local PostgreSQL skips concern real ClamAV configuration and Windows symlink privileges; corresponding hosted gates passed. [Local evidence](evidence/phase9-local.json) records timings, JUnit digests and read-only cleanup: zero guarded databases/generated roles, unchanged control privileges. [Exact-source hosted evidence](evidence/phase9-ci-39645201928.json) records five successful jobs. Artifacts were not downloaded.

User selected native Windows/PostgreSQL/TLS proxy (D11 platform) and local accounts with TOTP MFA and audited administrator recovery (D12 scope). Production deployment, workload/recovery targets and owner acceptance are separate gates. MFA implementation and operating configuration remain in progress.

## U018: native Windows operating draft and durable scan batches

D11 initial targets were explicitly approved by the user on 2026-10-21:
10 concurrent users, 10,000 contracts, 50,000 document metadata rows, ordinary
page p95 below 2 seconds, bounded exports below 15 seconds, RPO 24 hours and
RTO 4 hours. These are targets. Actual measurements and recovery evidence must
meet them before acceptance. Alert recipients, recovery/key custodians and
operational ownership remain to be assigned.

### Scan scheduling and privilege boundary

Production upload/create/replacement routes now commit quarantine and DocumentJob
records and return without running antivirus. Development retains existing inline
behavior; DEFER_DOCUMENT_SCANS=1 exercises deferred behavior locally. Downloads
remain denied until verified publication. Existing manual document-recover is
retained for deliberate privileged recovery.

Run the separate coordinator with explicit schema-operator credentials:

```powershell
& 'C:\kaemmerei\.venv\Scripts\python.exe' -m app.cli scan-pending --limit 10 --seconds 120
```

Use the actual Python path in your installation, including its Unicode spelling;
this example uses an ASCII installation path only as a deployment example.
APP_ENV/PGPASSFILE and URLs are injected securely into that operator process.
It must connect directly to PostgreSQL (session advisory locks require session
continuity; transaction-pooling proxies are unsupported). Web/integration and the
limited authentication-maintenance role do not own document_jobs and are denied
coordinator execution. No new runtime grants or schema migration are introduced.

A database-wide nonblocking advisory lock prevents overlapping coordinators. A
fixed maximum batch is selected in SQL; reservations increment attempts and commit
before external scanning, so interruption consumes a persisted retry. Retry delays
are 1, 2, 4 and 8 minutes, with five automatic attempts. Exhausted jobs remain in
quarantine for explicit operator investigation/recovery. State transitions and
hash/storage checks remain the existing document publication implementation;
automatic processing also rechecks live uploader access after scanning. Archived
contracts and revoked/inactive uploaders never gain publication from the worker.
Re-running a completed job has no publication effect. No files or records are
purged by the coordinator.

The seconds limit bounds new scan starts, not an in-flight scanner: one bounded
scanner timeout plus publication/database work can extend the batch. Windows task
execution is capped separately. CLI emits counts only, with exit 2 for retry,
exception or exhausted work; no exception details/credentials/content are logged.
A missing scheduler leaves files quarantined rather than bypassing the scanner.
Queue admission limits, externally monitored heartbeat/age, and other long jobs
remain open parts of P09-T03/T05/T08.

### Reviewable Windows files (not installed)

- deploy/windows/Invoke-Ohvr.ps1: data-only per-role JSON configuration, explicit
  local/reparse-free paths, removes inherited database credentials/settings,
  refuses privileged URLs in web configuration, launches one loopback web worker
  with Uvicorn proxy rewriting and raw access logs disabled. Never use execution
  policy bypass. Provision signed/approved scripts according to municipal policy.
- deploy/windows/web-config.example.json: non-working example hostnames and paths;
  no passwords. Provision private role-specific configuration/passfiles separately.
- deploy/windows/logging.json: enables ohvr.requests INFO redacted JSON, rotates
  10 MiB files with seven backups under logs/. Create/protect that directory before
  service start; Windows and proxy/error logs also need explicit ACLs/retention.
- deploy/windows/Caddyfile.example: optional native TLS proxy draft, explicit
  municipal certificate/key injection, matching 32 MiB body limit, receive/header
  deadlines, fixed-host HTTPS redirect and overwritten client/proto headers.
  No proxy access log containing URI/query values is enabled. No proxy binary or
  certificate was installed; live validation is pending.
- scripts/render_windows_tasks.py: renders disabled Task Scheduler XML, never
  registers/runs a task. Least-privilege named Windows account, IgnoreNew overlap
  policy, hidden noninteractive PowerShell, restart-on-failure and execution limits.
  Web starts at boot; scan repeats every two minutes, auth purge/status hourly and
  reconciliation daily at 03:00 local time. DST/missed-run behavior must be rehearsed.

Example review artifact (no registration; output must not exist):

```powershell
& $Python -m scripts.render_windows_tasks --role scan --python $Python --project $Project `
  --config 'C:\ohvr-private\scan.json' --account 'MUNICIPAL\ohvr-scan' `
  --output '.verification\scan-review.xml'
```

Use separate accounts/config/passfiles for web, schema-operator scan/reconcile and
limited maintenance purge. Operator configs add only MIGRATION_DATABASE_URL;
purge configs add only MAINTENANCE_DATABASE_URL. The common web/integration
settings are required by existing Settings validation; credential files must grant
only the roles that process actually uses. Restrict private JSON/passfiles and
certificate keys to their individual service account and approved custodians.
The operator account/owner credential is a deliberate higher-privilege process;
a future narrower scanning role must not be described as already implemented.

Before any registration: confirm selected host and CA chain, firewall PostgreSQL
and 8000 from remote clients, deny outbound SMB for the web identity, validate
Caddy against the chosen maintained binary, set private volume ACLs and OS
volume/temp quotas, test restart/reboot/failure, and establish monitoring. Caddy
supervision also needs a reviewed native task/service definition. Review generated
XML in Task Scheduler; definitions intentionally remain disabled. No passwords
belong in XML or command arguments. Registering tasks/enabling exposure is a
separate deployment action after identity/recovery/security gates pass.

References: [Microsoft task XML schema](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema),
[Caddy body limits](https://caddyserver.com/docs/caddyfile/directives/request_body),
[global server deadlines](https://caddyserver.com/docs/caddyfile/options),
[upstream header handling](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
Generated XML semantic/schema acceptance and actual proxy/service behavior remain
unverified; Python structural tests and the real Windows PowerShell parser are
separate evidence, not a claim of operational acceptance.

### Reproduce the approved synthetic workload

```powershell
& $Python -m scripts.benchmark_phase9 --output '.verification/phase9-workload.json'
```

Requires the same restricted native test URL/passfile as pytest. It accepts no
business database URL; the existing UUID/OID/owner/comment guard creates/migrates
an isolated database, seeds synthetic contracts and external document metadata,
uses ten independent local accounts through actual restricted PostgreSQL web
roles, then positively identifies and cleans up its own database/roles. It does
not load external documents, scan real files, disable database triggers or contact
the example DMS. Results cover in-process HTTP/database/template time, excluding
TLS/network/device/antivirus and production disk throughput. Failed targets return
exit 2 and must remain recorded. The benchmark is opt-in, not silently executed
as part of ordinary unit tests.

D12 scope is approved: local TOTP MFA with audited administrator recovery.
Enrollment, step-up/challenge sessions, replay prevention, seed/key protection,
recovery/session revocation and cross-backend/RLS regressions still require
implementation. Password-only human authentication is not accepted for broad
production exposure. No MFA success is claimed from this scope decision.

### Measured read-load failure and targeted correction

[Initial 10,000/50,000/10-account result](evidence/phase9-workload-before.json)
failed: list p95 10.35s (40 HTTP 200 and 10 HTTP 503), reports p95 6.80s;
detail p95 0.55s and bounded export p95 5.24s passed their respective thresholds.
The dataset is deliberately an initial undated-draft/read-load baseline: no
revision history/tasks/reviews or file bodies. Passing this baseline does not
establish representative mixed-workload acceptance.

The list previously loaded every contract just to count statuses. Status counts
now execute in scoped SQL, reminders only materialize dated candidates, listing
and report department relations are eager-loaded, and approval counts use COUNT
DISTINCT rather than a Python list. Large dated reminder sets and report/history
population aggregation remain open optimization work.

Migration 0022_read_admission adds an archived/end-date index and a SELECT-only
contract RLS optimization: the exact existing read_department rule is evaluated
for the department catalog once per statement and the resulting authorized IDs
are used by an uncorrelated InitPlan. It preserves the owner CASE, forced-password
and token/user scope checks, and leaves mutation policies unchanged. STABLE is
not IMMUTABLE: results are not cached between requests/principals. Actual-role
regressions compare the old rule with the new array for admin, reviewer and both
department principals and inspect EXPLAIN VERBOSE for the InitPlan.

The first plan-assertion test failed because ordinary EXPLAIN JSON omits function
output expressions; VERBOSE was required. This was a test evidence correction,
not disabling an authorization assertion. Corrected query tests passed 2/2.
Migration and role configuration must be applied in the same reviewed maintenance
window: rerun scripts/configure_database_roles.py after upgrade so existing runtime
roles receive EXECUTE on the new private helper before web traffic resumes. No
business database has been migrated or granted anything during this work.

The first optimized rerun is retained in
[evidence/phase9-workload-read-optimized.json](evidence/phase9-workload-read-optimized.json):
list p95 0.33s, all 50 HTTP 200, but reports still p95 5.14s and failed. Detail
p95 0.54s and export p95 2.67s passed. Reports were then changed to scoped SQL
financial groups, known/unknown amount counts, contract totals and open-review
counts; only dated contracts and open tasks are materialized for reminders.
Zero remains a known amount; missing/invalid amounts remain excluded/unknown.
Task/contract department eager loading preserves the report labels without N+1
queries. Regression compares SQL groups with the existing reference aggregation
for global and department scope, including zero versus missing annual values.
A further workload rerun and frozen-source full suites are required below.


## U018 frozen-source verification (c349996)

[Final initial read-load run](evidence/phase9-workload-aggregated.json):
10,000 contracts/50,000 external metadata records/10 independent accounts,
50 requests per operation. All 200 returned 200. p95 list 0.361s, reports
0.242s, detail 0.542s, bounded export 2.747s. Both earlier failed results remain
retained. This is the explicitly described undated baseline, not a representative
mixed workload, network/TLS benchmark or operational Phase 9 acceptance.

[Local evidence](evidence/phase9-u018-local.json): full 219 collected;
PostgreSQL 217 passed + 2 local skips, SQLite 196 passed + 23 explicit skips;
15 passing subtests each; explicit PostgreSQL 21 passed. Zero failures/errors/
xfails. Clean/populated/repeated migrations, actual restricted roles, existing
security regressions and synthetic PostgreSQL restore passed in the full suite.
Read-only catalog after all runs: zero guarded databases and generated roles;
control privileges unchanged. Existing HTTPX deprecation/cache ACL warnings remain.
The explicit run additionally collected seven new, deselected MFA codec tests;
these are not part of the 219-item checkpoint suite or the 21-item selection.

[Hosted exact-source evidence](evidence/phase9-ci-39650882010.json): all five
jobs passed for c3499965fa619b48e126d18e0ddb8103c9b03828. Job/step conclusions and
artifact metadata inspected; archives not downloaded. Subsequent MFA work needs
its own tests/CI; none of these results certifies MFA or production deployment.


## U019: local TOTP, encrypted seed custody and audited operator recovery

D12 implementation follows the user's selected local-account strategy. Migration
0023_human_mfa adds a separate encrypted-credential table, owner-only rollout
policy, pending challenge identity, factor verification/attempt fields and session
revocation indexes. It retains existing data and does not automatically enable
MFA, enroll accounts, invent secrets or revoke business sessions on upgrade.
Production startup now requires the explicit enabled database policy and a usable
private key file; there is no password-only production fallback. Migration/grants
were exercised only on marked disposable databases, not a business database.

### Authentication and database boundary

A valid password issues a new five-minute challenge cookie with no authenticated
user_id. It grants no ordinary contract/metadata/administrative access. Both web
application checks and PostgreSQL principal resolution require a verified factor
when rollout is enabled or the account already has an enrolled factor. Successful
TOTP verification consumes the challenge and grants a newly rotated full session
in the same transaction. Service tokens remain separate, with existing scoped,
expiring, accountable API-v2 authorization; a browser's pending MFA does not turn
a valid service credential into human authentication.

Enrollment requires an explicit operator authorization following out-of-band
identity verification, valid for 24 hours, plus a fresh password challenge. Only a
CSRF-protected POST starts setup. The manual authenticator secret appears only to
that password-proven unenrolled account; it is not displayed again after confirmed
enrollment. No external QR/image service receives it. Server-side checks enforce
six ASCII digits, 30-second TOTP steps and a +/-1-step clock window. A persisted
last-step counter and the shared identity lock prevent cross-session/worker replay;
a process-local cache is not the authority. Five wrong codes burn the challenge;
existing shared account/IP/network/global budgets also limit verification. These
are temporary windows, not permanent account suspension.

PostgreSQL mfa_credentials and mfa_policy have forced owner-only RLS and no direct
web/integration/maintenance grants. Narrow fixed-search-path definer functions
bind material/confirmation to the exact live pending cookie, active user and
active department. PUBLIC execution is revoked; integration/audit roles cannot
call human MFA functions. SELECT policy optimization preserves the principal
checks. Missing policy fails closed. Password, role, membership and recovery
revocations include pending sessions; ordinary department password changes keep
the verified factor on the newly issued session. Enrollment revokes other full
and pending sessions. Existing R01/R04/R10 safeguards remain required regressions.

### Key material and recovery

PyOTP 2.10.0 supplies OTP primitives; cryptography 50.0.2 supplies authenticated
Fernet/MultiFernet encryption for these small seed messages. Ciphertext is bound
to user ID so swapping database ciphertext between accounts fails authentication.
The keyring is an absolute local JSON file containing 1-5 Fernet keys; the first
encrypts and the remaining keys permit managed rotation/recovery. Keys must be
outside served paths and document backups, and outside the project/release in
production. Existing read-only private Windows ACL checks are reused for the key
file and directory at production startup; no ACL is weakened or rewritten. Files
must be regular, nonlinked and bounded. The web process needs read access to its
keyring, not access to migration-owner credentials.

Recovery is an operator/DB-owner command, not a factor-disable or emergency-login
browser endpoint. It records a nonsecret case reference and explicit verified-
identity assertion, clears the old factor, revokes all affected sessions, sets
mandatory password change, and grants a new time-limited enrollment window. It
never reactivates an inactive account or department. Human MFA events and operator
authorization/recovery/rotation are audited without passwords, OTPs, seeds,
ciphertext or key values in event details. Named custodians, independent identity
verification procedure, actual private Windows ACL/key provisioning and device
usability acceptance remain operational approval gates.

### Review-only rollout commands (not executed on business data)

Use a reviewed maintenance window with web traffic stopped; inject per-role
configuration/passfiles through the approved native launcher/secret mechanism.
Do not put passwords, keys or authenticated URLs in commands, task XML or chat.

1. Provision a separate private key directory for the intended service identity
   and approved administrative custodians. Generate a new file under the intended
   identity or use the approved secret provisioning mechanism. This command checks
   the private parent ACL, never overwrites an existing file and never prints key
   contents:

   ```powershell
   & $Python -m app.cli mfa-key-create --output 'C:\ohvr-private\keys\mfa.json'
   ```

2. Record MFA_KEY_FILE in protected role configuration; web REQUIRE_MFA=1 is
   explicit, and production requires it even if omitted. Escrow key material
   separately with authorized custodians; a database/document backup alone cannot
   recover encrypted seeds. The scan/purge operator may reference the nonsecret
   key path for Settings validation without reading the key; rotation requires
   explicitly authorized key custody.
3. Under the explicit migration-owner configuration, upgrade the reviewed named
   application database, then rerun role grants. Substitute actual approved names:

   ```powershell
   & $Python -m app.cli init-db
   & $Python scripts/configure_database_roles.py --database $ApplicationDatabase `
     --web $WebRole --integration $IntegrationRole --maintenance $MaintenanceRole `
     --audit-owner $AuditOwnerRole
   ```

   Verify the supplied owner URL uses verify-full and the intended CA; the grants
   command refuses postgres/template databases and requires the current head.
4. After each real identity check, authorize enrollment (the case reference is
   nonsecret; examples are not real employee/case values):

   ```powershell
   & $Python -m app.cli mfa-enroll-authorize EMPLOYEE_USERNAME `
     --reference APPROVED_CASE_ID --identity-verified
   & $Python -m app.cli mfa-enforce --reference APPROVED_ROLLOUT_ID `
     --confirm-session-revocation
   ```

   MFA enforcement intentionally revokes human/guest sessions. Confirm a verified
   administrator can enroll and use the protected recovery procedure before
   broader rollout. Check production key/policy/TLS/host/private-storage startup,
   then expose only through the approved TLS proxy after release gates pass.
5. Device loss: verify identity through the approved independent procedure, then:

   ```powershell
   & $Python -m app.cli mfa-recover EMPLOYEE_USERNAME `
     --reference APPROVED_RECOVERY_CASE_ID --identity-verified
   ```

   The user needs their password, a new authenticator enrollment and the forced
   password-change flow. If the password is also lost, use the existing separately
   controlled change-password command with its secure local prompt. No replacement
   password or bypass session is printed or sent.
6. Rotation: securely provision a keyring with new primary and retained old keys;
   restart every web worker to load both before re-encrypting rows. Under explicit
   owner/key-custodian credentials, repeat bounded batches using the returned
   last_user_id, without logging or displaying keys:

   ```powershell
   & $Python -m app.cli mfa-key-rotate --after-user-id 0 --limit 100
   ```

   Preserve prior keys in protected recovery escrow for retained database backups;
   remove them from active keyrings only after verifying live rows and the approved
   recovery/retention procedure. This work never automatically deletes old keys.

### Dependency and verification evidence

Official wheel hashes were checked before ordinary offline installation; no
third-party package source was changed. Existing CFFI 2.1.1 satisfies cryptography.
Installer temp-directory cleanup warnings were retained; external temp directories
were not deleted. [Wheel provenance](evidence/phase9-mfa-dependency-provenance.json),
[30-version runtime closure](evidence/phase9-mfa-runtime-dependencies.json), and
[actual OSV query/response](evidence/phase9-mfa-osv-runtime.json) show zero matches,
no query errors and no pagination for that scope. This is not an OS/tooling review
or a reproducible transitive hash lock.

Targeted checks cover RFC vectors, encryption/tamper/account binding/rotation,
CSRF, five-minute/five-attempt challenges, persisted replay, simultaneous
submission, operator-only setup/recovery, inactive departments, ordinary user
password-change revocation, service-token separation, missing policy and real
PostgreSQL private-table/function denials. A synthetic real pg_dump/pg_restore
round trip preserves encrypted seed, replay step and MFA audit IDs; its dump is
not an encrypted production-backup acceptance or a measured RPO/RTO certificate.

Investigation history: an initial exact Cache-Control string assertion failed
because existing layers both supply no-store; the check now verifies its actual
cache-control semantics. A service-token test used a v2 capability at a v1-only
endpoint and correctly received 403; it now exercises API v2. No application
authorization was weakened to satisfy either assertion. Corrected targeted MFA/
codec runs passed 21 on PostgreSQL, then 24 including startup-policy cases; the
added restore/missing-policy selection passed 3. Final full/current-source results
and hosted CI must be recorded below before technical completion is claimed.

Primary references: [PyOTP API/security guidance](https://pyauth.github.io/pyotp/),
[Fernet and key rotation](https://cryptography.io/en/50.0.2/fernet/),
[RFC 6238](https://www.rfc-editor.org/rfc/rfc6238),
[OWASP MFA recovery guidance](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html).


### U019 final technical verification: ece7797

[Local final evidence](evidence/phase9-u019-local.json): 244 collected, PostgreSQL
242 passed/2 local skips, SQLite 219 passed/25 explicit skips, 15 passing subtests
each. Explicit PostgreSQL 23 passed. All 25 MFA/codec cases executed in full PG;
SQLite explicitly skips concurrent PG and actual restricted-role MFA cases.
Zero failures/errors/xfails. Clean/populated/repeated migration head 0023 and real
restore regressions passed. Final read-only catalog 0 guarded DBs/0 generated
roles and unchanged control privileges; no business schema/storage/cluster change.
[Hosted evidence](evidence/phase9-ci-39656369586.json): all five jobs passed for
exact ece779758db1660c2a3314331cea97f63974c2e6. Job steps/artifact metadata inspected;
archives not downloaded. P09-T10 is technically verified; actual custody, private
production ACL/key provisioning, device usability and operating procedure adoption
remain unaccepted. Other Phase 9 operations/recovery/release gates remain open.

### Provisional operating roles — user decision, 2026-10-21

For a future production deployment, operational alerts and recovery are proposed
for Municipal IT Operations / System Administration. Sensitive identity recovery
and MFA-key custody are proposed for authorized identity/access or IT Security
Administration, with dual authorization. These are provisional roles pending
municipal agreement; no named people or existing dedicated IAM team is assumed.

These proposals introduce no municipal approval requirement for development,
testing, ordinary login, routine use or isolated development-account recovery.
The existing local operator recovery command remains testable using a nonsecret
local case reference (for example `DEVELOPMENT-RECOVERY-001`) and the documented
identity-verification assertion. This is a local privileged action, not an
external approval workflow. Authenticated password change remains self-service;
lost-factor administrator recovery is a separate sensitive operation. The final
production distinction between self-service recovery and sensitive recovery
still requires an agreed operating procedure.

No external notifications, approval workflow or production MFA-key escrow has
been activated. TOTP seeds remain encrypted in the database; encryption keys
are external protected files. Do not put plaintext MFA secrets or recovery
credentials in application records, reports, logs, backups of application
configuration, or this documentation. Test-only keys are disposable.

### U020 — encrypted database/document backup and verified restore bundle

Implemented `app/backup.py`, `backup_crypto.py`, `backup_restore.py`, operator CLI
commands, disposable regression tests and a disabled Windows backup-task draft.
No new migration; head remains `0023_human_mfa`. No real production key, backup,
escrow, task registration, notification or deployment has been created.

`backup-create` requires the exact named application database, direct
non-superuser/non-BYPASSRLS schema ownership and current migration head. Default
`postgres`/template databases, wrong database names, unrelated owners and unsafe
paths are rejected. A PostgreSQL advisory lock prevents overlapping backups.
The existing identity/writer guard is held across a REPEATABLE READ exported
snapshot, native matching-major `pg_dump`, private storage inventory and encrypted
file capture. Use a reviewed maintenance window: authenticated login and domain
mutations can wait or receive busy errors while that guard is held. Reads may
continue; this is not a zero-impact online backup certificate. Out-of-band DBA
or filesystem mutations must be excluded during capture.

The inventory checks every referenced stored object/hash and includes valid
unreferenced private objects without deleting them. Missing/mismatched files or
unclassified objects fail the backup. Metadata-only DMS links do not copy external
content. Native age 1.3.2 streams the manifest, custom-format database dump and
private files into an encrypted tar archive; only native public recipients are
accepted, with no SSH/plugin/passphrase or interactive fallback. Encryption does
not require the recovery private identity. An independently trusted Ed25519 key
signs a receipt binding timestamps, migration head, ciphertext name/hash/size and
file count. The receipt is written last; incomplete directories are not healthy
backups. Secrets, authenticated URLs and tool stderr are never printed.

The temporary plaintext dump is deleted only after successful encryption and
positive verification of this operation's UUID directory, marker and dump hash.
There is no recursive source cleanup, retention deletion, database drop or
cluster/service operation. On failure a private partial may remain for local
inspection and is never advertised as successful. Limits: 100,000 physical files,
25 MiB/file, 20 GiB dump and 50 GiB encrypted archive; capacity includes 256 MiB
reserve. Tool stages have explicit deadlines (default 30 minutes each), not a
promise that the whole recovery completes within that duration.

`backup-prepare-restore` is DB-independent. It verifies an independently supplied
Ed25519 public key and the entire ciphertext before decrypting. The exact bytes
sent to age are hashed against the signed digest as well. Complete age success
is required before parsing any plaintext. Extraction uses an exact manifest
allowlist, member/count/size bounds, exclusive file creation and per-file hashes;
traversal, links, duplicates, missing/extra members and corrupt files are denied.
It writes a new UUID child only, then `ready.json` last. It never imports into an
existing database. A separately reviewed import must use a NEW empty target,
matching-major native clients, the source migration head and reviewed restricted
role grants. Retain the old instance for rollback; never point a test harness at
a real backup or business database. Private prepared plaintext remains sensitive.

Signing keys, decryption identities and MFA encryption keys are separate from
the backup and web process. Keep an independently trusted verifier public key;
accepting a verifier supplied alongside an untrusted backup proves no origin.
The application database contains encrypted MFA seeds only; this bundle does not
escrow the external MFA key. Production custody/dual-authorization proposals
above remain inactive. Local development tests generate disposable keys without
municipal approval. No retention policy is silently enabled.

Review-only Windows command shapes (all paths/identity below are examples, no
credential values). Existing environment must select the appropriate owner
connection/passfile; production connections still require verified database TLS:

```powershell
& $Python -m app.cli backup-create --database APP_DATABASE `
  --directory C:\ohvr-private\backups --age C:\ohvr-tools\age.exe `
  --age-sha256 REVIEWED_EXE_SHA256 --recipients C:\ohvr-private\recipients.txt `
  --signing-key C:\ohvr-signing\signer.pem `
  --pg-dump 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe'

& $Python -m app.cli backup-prepare-restore `
  --receipt C:\ohvr-private\backups\BACKUP_JOB\receipt.json `
  --verifier C:\ohvr-trusted\verifier.pem --identity C:\ohvr-recovery\identity.txt `
  --directory C:\ohvr-private\recovery --age C:\ohvr-tools\age.exe `
  --age-sha256 REVIEWED_EXE_SHA256 --production
```

`render_windows_tasks.py --role backup` renders a **disabled** 12-hour repeating
task with no overlap, least privilege and a bounded execution limit. The launcher
accepts only backup public configuration paths plus the protected signing-key
path; no decryption identity is configured in the scheduled encryptor. It uses
`MIGRATION_DATABASE_URL`, not web/limited maintenance credentials. The owner
account has broad database privileges and must remain separate from the web
identity. No task registration has run. A successful schedule, off-host copy,
backup-age alerts, capacity/retention policy, recovery custody and a representative
restore drill still need operating acceptance. RPO 24h/RTO 4h remain targets;
the 12h schedule alone cannot prove either.

Verification:

```powershell
$env:TEST_POSTGRES_ADMIN_URL='postgresql+psycopg://ohvr_verify@127.0.0.1:55432/postgres'
$env:PGPASSFILE=Join-Path $PWD '.local-postgres\test.pgpass'
# TEST_AGE_BIN and TEST_AGE_SHA256 can select an already verified native tool.
# This workspace also recognizes its ignored, hash-verified verification tool.
$env:REQUIRE_BACKUP_ENCRYPTION='1'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest tests/test_backup_crypto.py tests/test_phase9_backup.py tests/test_windows_operations.py -q -ra --database postgresql
```

Actual targeted runs: initial collection failed because a new test used the
wrong model name `ContractHistory`; corrected to existing `Revision`. No schema
or production behavior was changed to accommodate it. Corrected run 16 passed;
restricted-login restored-access and Windows checks then 28 passed; CLI regression
made 29 passed. Latest reviewed-source/full/CI results must be appended below.
The real encrypted restore compares contract/document/revision IDs, file hashes,
encrypted MFA seed/replay state, forced RLS and restricted-login department access
and downloads. Tampered signatures/ciphertext/archives, missing blobs, overlap
and unsafe targets are negative tests. Each database is generated and identified
by the existing UUID/OID/owner/comment harness; only those databases are removed.

CI provisions two native tools in an ignored test directory from the official
Linux release with a pinned archive SHA-256, and sets
`REQUIRE_BACKUP_ENCRYPTION=1` for **both PostgreSQL jobs**. Missing tools fail those
jobs; SQLite without the tools has explicit encryption skips. No production or
global tool installation. Official Windows asset and exact executable digests
are recorded separately; Sigsum proof was not verified. References:
[age 1.3.2 manual](https://github.com/FiloSottile/age/blob/v1.3.2/doc/age.1.html),
[standard Ed25519 signatures](https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/).


### U020 final technical verification - source 92329b6

- 262 collected. Native PostgreSQL: 260 passed, 2 explicit local skips, 15 passing subtests, 578.16s. SQLite: 236 passed, 26 explicit skips, 15 passing subtests, 160.25s. Zero failures/errors/xfails.
- Explicit PostgreSQL: 24 passed/238 deselected/zero skips, 128.22s. Reviewed backup/Windows selection: 29 passed/zero skips, 17.69s. All 17 backup cases executed in full PostgreSQL; SQLite skips only the real PostgreSQL backup among those cases.
- Actual clean/populated/repeated migrations remain at 0023_human_mfa. Encrypted snapshot/native restore, restricted restored department access/downloads, IDs/hashes, revisions and encrypted MFA replay state passed. Tiny synthetic timings: backup 1.199s and preparation/import/verification 3.030s. Two contracts, one PDF and one staged orphan: this is not representative production recovery or RPO/RTO acceptance.
- All FIVE exact-source hosted jobs passed: [run 39660619585](https://github.com/mignoncharly/kaemmerei/actions/runs/39660619585), source 92329b6f181f174f0212c429e3368383bcc027dc. Both PostgreSQL jobs required native encryption tools and actual backup tests. Run/jobs/steps and five artifact metadata entries inspected; archives not downloaded.
- Final read-only catalog: zero guarded disposable databases, zero generated roles; dedicated control privileges unchanged. No business data/schema/cluster/service modification or production deployment. pip check clean. Warnings: existing Starlette/httpx TestClient deprecation and Windows pytest-cache ACL/path warning; no warning suppressed.
- Evidence: [local JSON](evidence/phase9-u020-local.json), [hosted JSON](evidence/phase9-ci-39660619585.json), [native tool provenance](evidence/phase9-age-provenance.json). JUnit hashes bind the recorded local results.
- Phase 9 remains open. Remaining work includes monitoring/backup-age alerts, representative mixed workload/recovery, remaining scheduled jobs, native TLS/service/ACL/capacity acceptance and reproducible release checks. Production ownership and custody are provisional, not development blockers. A static follow-up is explicit production TLS validation in the standalone DBA role-configuration script, which currently constructs development Settings; the application/operator CLI backup path already revalidates production TLS. Do not deploy via that script before resolving the follow-up. No production rollout is authorized.

### U021 — DBA TLS policy and reproducible release inputs

Phase 10 has required Phase 9 entry gates. The user's request to continue is
being applied to the remaining engineering work; no optional-scope waiver or
production acceptance is inferred. Municipal organizational decisions do not
block local development, login, testing or secure local operator recovery.

The standalone DBA grants script now validates `APP_ENV`, sanitizes malformed
URL failures and applies the shared production database TLS policy **before
engine creation**. Production requires PostgreSQL/psycopg, `verify-full` and a
single absolute local CA path. Application web/integration and CLI-selected
operator connections use this same policy. Development can use the dedicated
native loopback cluster without TLS. DBA tools do not require unrelated web/MFA
startup settings. The existing exact database identity, migration-head check,
transactional grants and credential redaction remain. This closes the U020
static script gap; actual production CA/hostname/TLS handshake tests remain open.
[PostgreSQL 18 certificate policy](https://www.postgresql.org/docs/18/libpq-ssl.html).

`requirements.lock` pins the actual 30-package runtime closure, including
transitive dependencies and Psycopg binary extras, with 706 SHA-256 wheel hashes
from official version-specific PyPI metadata. Yanked artifacts and source builds
are excluded. `.gitattributes` fixes lock line endings across checkouts. The
version inventory is unchanged from U019's runtime advisory review; this is no
new claim about OS, PostgreSQL/libpq, Python, age, ClamAV or proxy security.
[Lock provenance](evidence/phase9-runtime-lock-provenance.json) records metadata
URLs/digests and the lock digest. Dev/browser tooling remains separately scoped.
Required installation flags follow [pip's hash policy](https://pip.pypa.io/en/stable/topics/secure-installs/).

`scripts/build_release.py` reads committed Git blobs from HEAD and a fixed source
allowlist. Working-tree changes, environments, caches, test clusters, real config,
logs, private keys, data and documents are excluded. Unclassified tracked objects
inside runtime trees, links/submodules, missing inputs, oversized inputs or an
incomplete/branched migration graph fail the build. ZIP entries have fixed order,
timestamp, permissions and no platform-dependent compression. The manifest binds
source commit, migration head, dependency lock and every member's hash/size. It
does not contain a timestamp or machine-specific path. Build destinations are
new local files only; existing files are never overwritten or cleaned up.

Verification requires an independently trusted expected artifact digest, checks
all regular members against the exact manifest and parses the migration chain.
A checksum is integrity evidence, not a signature or release authorization.
`scripts/verify_release_runtime.py` explicitly executes a reviewed own artifact
after verification: it extracts only verified members into a fresh ignored UUID
bundle and starts an isolated child with no database/recovery credentials. The
child imports the packaged application, applies its migrations to in-memory
SQLite, confirms no implicit users and exercises application startup/shutdown.
This checks packaging/runtime completeness, not production RLS, TLS or pilot use.

Review/build commands from a committed checkout (no deployment):

```powershell
$Python='C:\kämmerei\.venv\Scripts\python.exe'
# Select a NEW empty venv path; use the existing interpreter to manage it.
& $Python -m venv --without-pip .verification\release-runtime
& $Python -m pip --python .verification\release-runtime\Scripts\python.exe install `
  --require-hashes --only-binary=:all: -r requirements.lock
& $Python -m pip --python .verification\release-runtime\Scripts\python.exe check

New-Item -ItemType Directory -Force .verification\releases | Out-Null
$Archive=Join-Path $PWD '.verification\releases\NEW-RELEASE.zip'
& $Python -m scripts.build_release --output $Archive
# Use the reviewed build's digest, not a digest supplied by an untrusted sender.
& $Python -m scripts.build_release --verify $Archive --sha256 REVIEWED_SHA256
& .verification\release-runtime\Scripts\python.exe -m scripts.verify_release_runtime `
  --archive $Archive --sha256 REVIEWED_SHA256
```

CI adds clean hash-verified installation and source-artifact smoke/regression
checks on Windows and Ubuntu, then a dependent job compares both artifacts byte
for byte. This adds three jobs to the five existing application/security jobs.
Source packages are CI verification artifacts only; nothing is deployed or
registered. Full/current-source hosted results must be recorded after completion.

Actual preliminary verification: TLS/application SQLite selection 47 passed,
2 explicit PG-only skips. Reviewed release/TLS selection 29 passed. A genuine
fresh Windows venv installed all 30 locked packages offline from independently
hash-checked official wheels; all versions and pip check passed. Shared `.venv`
unchanged. Real artifact build/smoke and frozen-source full tests are pending.

Investigation retained: the first metadata generator used the Windows default
encoding and failed; explicit UTF-8 fixed it. Six initial fixture teardown errors
were Git's read-only object attributes; a fixture-local attribute change fixes
new test cleanup without changing ACLs or the real repository. Automatic approval
review rejected the command to remove earlier failed synthetic fixture directories;
they were retained in ignored verification storage, not deleted by another route.
The first clean `pip --target` attempt failed on a private temporary-directory
ACL. Supported `pip --python` into a new normal venv succeeded. Pip temporary
cleanup warnings were retained; no external temp directory or ACL was changed.
Two wheel downloads timed out; existing local wheel copies were accepted only
after matching the same official SHA-256. No hash/policy was bypassed.

Remaining Phase 9 engineering/acceptance: mixed workload/recovery measurements,
remaining maintenance jobs, actionable monitoring and backup-age checks, native
proxy/service/TLS/ACL/capacity acceptance, wider tool advisory/update operations
and production custody/retention adoption. P09-T11 is partial until those wider
update/inventory gates are resolved. Phase 10 release/owner gates remain open.


U021 investigation follow-up: the first real source artifact at 569b30e was
built twice identically (103 files, 910,919 bytes; SHA-256
`b58cc5025d5bd32e09aae9f5a4f62ccd56d197b698c6072d2c9ea61e4e40f9c7`).
Initial packaged smoke failed because its caller began a transaction before
SQLite migration. The existing migration guard correctly denied this. The
verification caller now uses a plain connection, matching existing migration
fixtures; no migration or application guard changed. The same artifact then
passed fresh-runtime migrations/startup/shutdown in isolated in-memory SQLite.
Final frozen-source local/hosted results and final artifact identity follow.
