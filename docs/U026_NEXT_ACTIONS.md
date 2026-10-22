# U026: prioritized actions after verified hosted CI

Hosted CI is **VERIFIED** only for `3d4a180297db801293e4b86e42e9f60a55fbca86`:
[run 39791514267](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267),
10/10 jobs successful, 14m 42s, nine artifacts. [Evidence](evidence/u026-hosted-ci-success.json).
The final status was independently read from fresh GitHub run/jobs/artifact APIs.
No unnecessary test rerun, new publication, main merge or deployment follows this record.

## Completed - hosted CI and local preservation

**VERIFIED:** all ten hosted jobs and all nine downloaded ZIPs at the exact tested
commit. The exact completed report is
`.verification/u026-confirmed-run/preserved-8ca121aa85ff4b1b8e8c4b7ea9278dd8/sanitized-report.json`,
SHA-256 `98cce9fd325d240cb138ab62e30880ba244f22aa1031c01f01545fb0fd1c582e`.
ZIP CRC/published hashes/member hashes, required Windows/Linux native-link cases and
both identical nested source releases were independently validated locally. Preserve
originals; **do not repeat collection or CI**. [Integrity evidence](evidence/u026-artifacts-verified.json).

CI records PostgreSQL 18.6 service and 16.15 native tests, with loopback SSL disabled,
and actual ClamAV 1.5.4. These verify disposable CI, not the intended operating host.
Six Windows-specific PowerShell cases are Linux full-suite skips with earlier local
Windows evidence; do not imply all tests ran on every hosted OS. Node action-runtime
and moving ubuntu-latest annotations are later maintenance, not a reason to rerun now.

Completed STRATO access assessment: SSH/SFTP/shell and existing TOFU pin verified; no changes/application-file reads. Await owner tariff evidence; do not repeat discovery. [Findings](STRATO_HOSTING_ASSESSMENT.md), [prepared Windows/R43/scanner requirements](WINDOWS_SYNTHETIC_PILOT_REQUIREMENTS.md).

## Priority 1 — approve the intended technical host and R43 maintenance

**You / authorized host operator:** provide non-secret STRATO product/tariff category,
OS and capability evidence, using the existing host-evidence template. No account
numbers, credentials or website modification are needed. Confirm whether the product
supports an isolated persistent Windows Python service, PostgreSQL, private storage,
VPN/firewall/TLS and recovery administration. SFTP access proves none of these.
If the product is unsuitable, agree the host explicitly; do not silently change platforms.

Select the actual synthetic host and maintenance owner. Approve a separately patched
synthetic host or a scoped update of the identified PostgreSQL installation. Latest
local read-only observation: native pg_dump/pg_restore/psql and installed postgres.exe
18.3, loaded libpq separately 18.4; actual runtime server was unobservable. These are
historical observations, not new post-CI measurements. No installation was updated.

**Engineering directly:** maintain the [reviewed R43 procedure](U026_POSTGRESQL_PATCH_PROCEDURE.md),
installer/provenance review and non-destructive preflight. After explicit maintenance
authorization and provisioned access, verify executing server and matching clients at
the approved 18-series patch (reviewed target 18.6), required backups/isolated restore,
rollback readiness, session recycle and release-note follow-ups. Repeat only the
post-maintenance native/RLS/MFA/TLS/recovery/workload tests that establish the new host.
CI native gates are verified for ephemeral runners; they do not close intended-host R43.
Do not install, stop/start, re-ACL or overwrite an existing cluster without scope approval.

## Priority 2 — provision intended-host real ClamAV and secure operations

**You / authorized host operator:** approve/provision a maintained ClamAV package and
official current signatures on the intended host; retain verified package provenance,
existing service identity and protected storage. Provisioning is separate from the
successful Linux CI scanner. No security exclusions or weakened upload controls.

**Engineering after provisioning:** use scanner_readiness preflight then required
clean/EICAR/HTTP tests, quarantine/no-range bypass and retry behavior; verify reviewed
encrypted/macro/limit fixtures and representative throughput under the actual scan
identity. Inspect the versioned engine policy before its 2026-11-22 review expiry;
new branches/backported packages need explicit technical review. No engine pass is
inferred merely from signature-download access or mocked results.

On the approved synthetic host, verify service/TLS certificate and negative-hostname
checks, network boundaries, trusted proxy, database TLS, existing ACL/quota isolation,
monitoring/failure visibility, reboot/restart and encrypted recovery access. Provisional
responsibilities remain valid; no external notification workflow or recovery-key escrow
is activated. Existing STRATO website must remain isolated and unchanged.

## Priority 3 — execute the twelve synthetic participant scenarios

**You / acceptance participants:** arrange the responsible Kämmerei representative,
selected Kämmerei users, selected Fachbereich user and product owner/operator. The
approved pilot scope/permissions/empty register/local TOTP decisions are already settled;
do not request them again. Use synthetic contracts only and an agreed recorded candidate.
Keep the original U025 archive unchanged, with source
`da60deaf6cd89a16b2711a5bad9a0fd377b00215`, SHA-256
`ffab0034f7b7d0e924501b625a0e318b830402aec8917ac20024796327acc57f`.
If exercising a later candidate, engineering builds a fresh source-bound packet rather
than rewriting the original. Follow SESSION.md/SCENARIOS.md and record actual outcomes,
role, timezone timestamp, issues and sanitized evidence reference. Leave unavailable
cases BLOCKED and untouched cases NOT_RUN; the 32 automated checks are not twelve
participant passes. Include manual assistive-technology observations and independent
assigned review; no self-approval or extra Judith/infrastructure privileges.

**Engineering directly:** prepare/review the source-bound packet, synthetic fixture
instructions, account and provisional role configuration, validate the submitted results,
and fix actual technical findings. Account changes on the intended host still require
approved operating access. Formal acceptance requires actual participant outcomes and
the separate recorded decision; it remains incomplete today.

## Priority 4 — obtain municipal business and release decisions

Request written business/records clarification now in parallel with host preparation;
this numbering does not defer that work until after participant testing. Real-data and
production release decisions remain later separate gates.

**Municipality / responsible Kämmerei and records roles:** provide written financial
interpretation, deadline examples/authority and records/export/retention/legal-hold rules.
Engineering translates approved answers into versioned rule packets and test cases;
it does not invent accounting, statutory or contractual calculations. Manual entry and
unvalidated-calculation notices remain, and automated disposal remains off.

**Municipality / independent reviewers:** conduct the independent security/permissions
review and separately authorize any real-data pilot and wider production use. A technical
CI pass or synthetic participant decision grants neither approval. No main merge,
production deployment, municipal records, external notifications or key escrow is
authorized by this action list. Existing operating responsibilities remain provisional.

| Status | Current meaning |
|---|---|
| Development engineering | VERIFIED within recorded local/hosted test scope at its exact source |
| Synthetic technical readiness | CI verified; intended-host/scanner/patch/secure-operations gates remain open |
| Formal synthetic pilot acceptance | PREPARED, NOT COMPLETE; twelve participant outcomes pending |
| Real-data pilot authorization | NOT_GRANTED |
| Broader production approval | NOT_GRANTED |


## Ready-to-fill operator request

A concrete local request packet is prepared in `.verification/u026-next-operator-steps/`:
`host-evidence.json` (non-secret STRATO/OS/capability fields) and
`maintenance-request.json` (identified target/provenance/backup/rollback references).
All maintenance/deployment approvals start NOT_AUTHORIZED. Use local receipt references,
not credentials, customer/account numbers or personal records. Existing provisional
Municipal IT Operations/System Administration responsibility is retained.

First return the actual product/OS/capability evidence and identify the synthetic host.
On an already authorized Windows host, the operator can run the existing read-only
`./scripts/Get-PilotHostInventory.ps1` and retain its JSON. No elevation, service change,
installation, ACL edit or website modification is requested. Run it on the intended
host; a workstation inventory is not STRATO entitlement or hosting proof. The inventory
alone deliberately leaves hosting/VPN/TLS capability unverified until evidence is reviewed.
Engineering then reviews that evidence and prepares the exact scoped maintenance and
verification commands. Installation/restart/configuration still needs separate approval.
