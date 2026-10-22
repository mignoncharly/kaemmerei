# Synthetic pilot acceptance package — U023

U025: [built acceptance package, exact-source tests and remaining owner actions](U025_SYNTHETIC_ACCEPTANCE_PACKAGE.md). Windows junction rejection verified; required Windows/Linux native-link CI added. Formal acceptance remains incomplete.

U024 local Microsoft Edge: **VERIFIED**, 32 checks, exit 0, synthetic only, exact
source `d3f5ad2752feb565b5ae74ecbf90fde82ad84e4d`; result SHA-256
`2de4e1f138efe1e53f9c73ee902c866840876da6809836fca9cf9b566d69f179`.
[Validated evidence](evidence/u024-edge-verified.json), [diagnosis and scope](U024_BROWSER_FAILURE_DIAGNOSIS.md).
This closes the local Edge engineering check, with no new browser run. Formal
12-scenario participant acceptance is **NOT COMPLETE**; R43, actual scanner,
native symlink, current hosted CI and actual-host gates remain open. Real-data
use and production deployment remain blocked pending separate approvals.

Baseline: verified code `05648eda3ce6ddb9fe7e33082593e294522fbf24` and preserved
documentation `8ca205c`. New exact-source execution evidence is recorded in
HANDOFF U023 after the code freeze. This package does not claim participant
acceptance, hosted CI success or deployment.

## Scope and participants

Kämmerei plus one selected Fachbereich; empty register, synthetic records only,
internal/VPN access, personal local accounts with TOTP and the configurable
provisional permission matrix. No Judith privilege grant. Application/business
authority is distinct from Windows/database administration and key custody.
Keep the provisional operational roles. Notifications, production key escrow,
external workflows and automated disposal remain inactive.

Participants: responsible Kämmerei representative, selected Kämmerei test users,
and product owner/software engineer/project IT operator. Select the Fachbereich
and record actual testers locally. Do not include real names, contracts, addresses,
secrets or TOTP screens in shareable technical evidence.

The [12 browser/operating scenarios](pilot/scenarios-v1.json) specify role, steps
and expected observations. Copy [the results template](pilot/results.template.json)
to a new `.verification` location; set `source` to the exact tested Git revision.
Each case starts NOT_RUN. Record actual result, role, timezone-aware observation
time and authorized evidence reference. A case cannot pass merely because its
automated regression passes. Have the responsible representative and product
owner review the complete record, unresolved issues and scope before recording
formal synthetic pilot acceptance. Independent security review and municipal
real-data/production authorizations remain separate.

Validate a completed or partially completed record:

```powershell
$source = (git rev-parse HEAD).Trim()
python -m scripts.pilot_verification --expected-source $source --output .verification/acceptance-review.json acceptance --results .verification/pilot-results.json
```

Exit 2 means incomplete/failed scenarios; the sanitized result never grants
formal authorization. Use a new destination for every execution. Full Git checkout
and development dependencies are required for browser/test procedures; the
curated runtime source bundle deliberately excludes test tooling and fixtures.

## R43: exact requirement and verification

Observed local server and native tools: 18.3; they are NOT the intended STRATO
host inventory. The native production floors are **18.6, 17.11 or 16.15**, with
current maintained minor updates and component review required before adoption.
The application rejects unreviewed majors, old patches and malformed versions.
Do not use an RC major release to evade that gate.

| Component/advisory | Preconditions and impact | Required remediation/evidence |
|---|---|---|
| Server: [CVE-2026-14666](https://www.postgresql.org/support/security/CVE-2026-14666/) | Cached RLS plans can survive relevant SQL-role membership/attribute/database-ownership changes, permitting recently revoked reads/writes. Application User rows are not automatically the same condition. | Patched server at the floor above; authorized role/ownership lifecycle review; terminate/recycle old sessions after the authorized maintenance; repeat restricted-role and revocation regressions. |
| Server: [CVE-2026-6479](https://www.postgresql.org/support/security/CVE-2026-6479/) | Negotiation recursion can deny service via reachable Unix socket; TCP condition applies when both SSL and GSS are disabled. Windows loopback is not the Unix-socket case. Fixed in 18.4/17.10/16.14, covered by the stricter floor. | Patched server, actual network/SSL/GSS configuration review. VPN/SSL restrictions reduce exposure but do not replace patching. No exploit attempted. |
| `pg_dump`: [CVE-2026-19385](https://www.postgresql.org/support/security/CVE-2026-19385/) | An object creator can craft function transform metadata that executes code as the OS backup user through vulnerable pg_dump. Trusted synthetic fixtures do not demonstrate that attack. | Patched backup client at 18.6/17.11/16.15 or later within the reviewed family; match server major; trusted distribution/hash evidence. Patching the server alone does not patch pg_dump. |
| `pg_restore`, `psql`, runtime libpq and remaining native stack | Component identity/version review is required; an old version string alone does not prove every exploit precondition. Local psycopg/libpq may differ from the installed native client. | Inventory independently. The attestor records loaded libpq, tool versions/hashes and server version; baseline success is not exhaustive advisory clearance. See [native baseline](NATIVE_SECURITY_BASELINE.md). |

Engineering implemented fail-closed production server/backup checks; U023 tightens
full client-output parsing and adds `pg_restore`/`psql` attestation. Development
synthetic diagnostics remain possible. No application change repairs native code.

**Action requiring authorization:** an authorized system administrator must choose
either a separately provisioned patched synthetic host or a reviewed maintenance
upgrade of the existing installation. Confirm verified backup/recovery and trusted
installer provenance, schedule downtime/restart and preserve compatible config.
No upgrade/installer/service/ACL action is performed by these verification tools.

After that authorized action, run on the intended host with its existing local
control URL/passfile in the operator's session (never put them in chat):

```powershell
$source = (git rev-parse HEAD).Trim()
python -m scripts.pilot_verification --expected-source $source --output .verification/native-gate.json native --bin 'C:\Program Files\PostgreSQL\18\bin' --server
```

It executes `--version` and read-only SHOW queries only; captures fixed version
numbers, hashes, SSL-enabled boolean and loaded libpq implementation/version;
omits URLs, credentials, service paths/account names and SQL contents. Exit 2
means the baseline is not met or not observed. `r43_closed` remains false because
actual-host review and repeated tests are independent evidence requirements.
Repeat full PostgreSQL, MFA/RLS/revocation, encrypted DB/document restore, actual
TLS/negative-hostname checks and representative mixed workload afterward. Do not
test an exploit on the existing cluster. Installing patched binaries without a
server restart and checking the executing versions does not close R43.

## Browser procedure and safe local fallback

`scripts/verify_phase8_browser.py` retains CSP, keyboard, responsive/recovery and
archive-confirmation checks and adds disposable department/create/edit/document/
review-request/archive/history/MFA journeys. Its backend is explicitly SQLite and
its scanner synthetic; actual RLS and real scanner coverage come from separate
checks. Browser automation does not supply participant/assistive-technology
acceptance or actual VPN/TLS validation. No fixed external target URL is accepted.

The tracked wrapper replaces the ignored U022 helper. Run in an ordinary
authorized PowerShell terminal if this runner cannot start the browser driver:

```powershell
cd C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase
.\scripts\Invoke-PilotBrowserVerification.ps1 -ExpectedSource ((git rev-parse HEAD).Trim()) -Channel msedge
```

No elevation, ExecutionPolicy bypass, ACL edit, download or browser-sandbox flag
is requested. The existing Python/development/browser dependencies and installed
chosen browser must already be available. An explicit `-Python` may select the
existing development interpreter. Dependencies: `requirements-browser.txt`;
approved CI installs these separately on a disposable runner. Do not install or
change the user's normal browser merely to manufacture a result.

Each run gets a new `.verification/u023-browser-<UUID>` directory. Only share
`sanitized-report.json`; keep logs/screenshots local. Expected format:

```json
{"format":"ohvr-local-browser-verification-v2","source":"<actual 40-char Git SHA>","status":"passed or failed_or_environment_blocked","exit_code":0,"synthetic_only":true,"check_count":32,"result_sha256":"<actual SHA-256 or null>","error_code":null}
```

Check count is illustrative, never a prefilled pass. Success requires a fresh v2
result from the same source, at least 30 checks, exit 0 and unchanged verification
source before/after. Secret/code fields are never screenshotted or returned.
Failure exits 2 and must remain unverified. The wrapper verifies current HEAD;
if documentation was committed after a tested code freeze, record the wrapper's
actual HEAD and confirm the code diff rather than rewriting an older result.

## Scanner checks and dependencies

| Check | Engineering mechanism | Actual-engine/host dependency |
|---|---|---|
| Exit 0/1/error/timeout/missing binary, stale/future/malformed definitions | Adapter regressions, explicit limits, official signatures only, heuristic encrypted/macro/limit alerts | Mock results verify the adapter, not malware detection effectiveness |
| Quarantine/no range bypass, retry exhaustion/overlap/crash, replacement/hash/scope | Synthetic HTTP and actual PostgreSQL lifecycle regressions | Actual host identity/storage/scan scheduling acceptance still required |
| Actual clean/EICAR and definition freshness | Required real-engine test now also verifies actual HTTP clean download and denied infected download | Maintained ClamAV `clamscan` and official current CVD/CLD from approved `freshclam` update, executable/definition access under scan identity |
| Encrypted/macro/container-limit heuristics, representative throughput | Flags enforced and regression-checked | Operator-reviewed inert encrypted/macro/oversize fixture set, actual engine/host measurements; not claimed from mocked flags or one EICAR test |

Official ClamAV [scanning documentation](https://docs.clamav.net/manual/Usage/Scanning.html)
distinguishes standalone clamscan from clamdscan (which can ignore scanner flags).
Use the supported clamscan binary, no substitution with clamdscan. No recursive
system scan, removal, security exclusion or scanner daemon exposure is needed.
Signature freshness limit remains the configured `scanner_max_age_hours`.

With **already approved and provisioned** binary/signature paths, set
`CLAMAV_EXECUTABLE` and `CLAMAV_DATABASE_DIR` in the local operator session, then:

```powershell
python -m scripts.run_pilot_verification --expected-source ((git rev-parse HEAD).Trim()) --selection scanner --output .verification/required-scanner-run
```

This does not install/update anything and forces REQUIRE_REAL_CLAMAV=1. Missing
configuration reports EXTERNALLY_BLOCKED, not a skip/pass. To repeat the actual
scanner test with restricted PostgreSQL roles use the already configured guarded
test cluster and `REQUIRE_REAL_CLAMAV=1; python -m pytest tests/test_phase5.py -k
real_clamav --database postgresql` (set the environment in PowerShell correctly:
`$env:REQUIRE_REAL_CLAMAV='1'`). Keep EICAR bytes out of shareable files; test
assembles them in memory and uses only disposable records. Do not disable
endpoint protection if it intercepts the synthetic test; record that dependency.

## Existing STRATO account: non-destructive assessment

The [hosting assessment](HOSTING_ASSESSMENT.md) remains conditional. The official
[Windows product page](https://www.strato.de/server/windows-dedicated-server/)
advertises administrator access, scheduler and VPN capabilities for that product
category; it does not establish this account's entitlement. SFTP means file
transfer capability only, not Windows administration, native PostgreSQL install,
persistent Python process, task registration, TLS proxy or private port access.
No account-specific STRATO connector or authorized host endpoint is available here.
Repository samples are placeholders; no secret configuration is evidence.

1. Product owner: fill only tariff/category/OS and a non-secret order/product
   overview reference in [host evidence template](pilot/host-evidence.template.json).
   Do not provide credentials, customer numbers or website contents.
2. Authorized host operator: on the intended Windows host, run
   `powershell -NoProfile -File .\scripts\Get-PilotHostInventory.ps1` and keep the
   sanitized JSON. It reads OS, administrator-token boolean, PATH-discovered tools
   and fixed service counts, makes no changes, and fails to establish hosting
   capability by itself. A local developer-machine run is not STRATO evidence.
3. Engineering/operator review existing service/ACL/quota/network/TLS and backup
   configuration read-only. Record capability references separately. No probing
   or modifying the separate website; no DNS, upload, purchase or platform change.
4. Actual internal/external reachability, restart, certificate/DB TLS, storage and
   restore rehearsals require the intended isolated synthetic environment and
   authorization for any configuration changes. Unknown template fields stay null.

## Exact-source release evidence required

Run on a clean committed verification tree, preserving the unrelated launcher
edit. `scripts.run_pilot_verification` pins source before/after, uses only existing
dependencies/guarded synthetic fixtures, captures private logs and emits sanitized
JSON and JUnit hashes. Use unique output destinations:

```powershell
$source = (git rev-parse HEAD).Trim()
python -m scripts.run_pilot_verification --expected-source $source --selection mixed --output .verification/rc-mixed
python -m scripts.run_pilot_verification --expected-source $source --selection postgresql --output .verification/rc-postgresql
python -m scripts.run_pilot_verification --expected-source $source --selection sqlite --output .verification/rc-sqlite
```

Run the mixed benchmark without competing suites. The PostgreSQL selection forces
encrypted backup tests to execute. Also require browser, real scanner, actual
patched native attestation, hash-locked runtime install/pip check, twice-identical
source build/manifest and isolated packaged migration/startup. Review every skip;
expected backend skips need a passing actual-backend counterpart. A missing
scanner/symlink privilege is missing local environment coverage, not a backend pass.

Current workflow `.github/workflows/phase1-verification.yml` expands to ten hosted job executions:
locked-release Windows and Linux; cross-OS release reproducibility; real frontend
browser; real scanner; native PostgreSQL; SQLite; PostgreSQL service; required native
storage links on Windows and Linux. **All ten
must run against the final candidate commit** after explicit external authorization.
Retain job/run IDs, source SHA, artifacts, test/skips and failure classifications.
Current workflow additionally repeats selected phases/backup tests, verifies
native-manager safety, enforces matching native patch floors on both PostgreSQL
jobs, runs the real scanner HTTP check with restricted PostgreSQL logins, and
runs the representative mixed workload separately within the service job. No old hosted success is inherited. No hosted run is
dispatched by this work.

Candidate evidence inventory must bind exact code source, source artifact SHA-256,
schema head, dependency lock hash, test report hashes, benchmark, native/scanner/
browser outcomes, outstanding gates and all exclusions. Keep tests and evidence
separate from a deployable package. A checksum proves integrity, not approval.
Do not mark candidate fully accepted while R43, actual host/scanner,
participant acceptance or independent review remains open.

## Pending municipal decisions remain separate

Finance, contractual deadline interpretation and records/retention packets remain
pending with expected results null. Manual data/task dates remain available;
estimates are unconfirmed and disposal disabled. Written responsible Kämmerei
answers and relevant municipal confirmation are required before adopting versioned
rules or authorizing real-data use. These decisions do not block local technical
regressions and do not authorize wider production.
