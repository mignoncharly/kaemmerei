# U025: synthetic acceptance package and remaining technical gates

U026 hosted CI execution and local artifact preservation are both **VERIFIED** for exact commit `3d4a180297db801293e4b86e42e9f60a55fbca86`, [run 39791514267](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267). All ten jobs passed; all nine saved ZIPs match published SHA-256/CRC/member hashes; required Windows/Linux native-link cases and identical nested releases are validated. [Original report/integrity receipt](evidence/u026-artifacts-verified.json), [verified execution scope](U026_HOSTED_CI_EXECUTION.md), [next operator steps](U026_NEXT_ACTIONS.md). Intended-host R43/TLS, approved host scanner/configuration, twelve NOT_RUN participant scenarios and municipal authorizations remain open. No rerun, artifact recreation, merge or deployment.

Engineering revision: `da60deaf6cd89a16b2711a5bad9a0fd377b00215`.
[Machine-readable evidence](evidence/u025-engineering.json). Subsequent documentation
commits do not change the source recorded in executed tests or artifacts.

## Delivered and verified

- Local Microsoft Edge U024 is **VERIFIED**: 32 successful checks, exact source
  `d3f5ad2752feb565b5ae74ecbf90fde82ad84e4d`, result SHA-256
  `2de4e1f138efe1e53f9c73ee902c866840876da6809836fca9cf9b566d69f179`.
  Validated all three local artifacts in `u023-browser-d3daac21079b428eb2ee63c77e6ed744`.
  No browser rerun was made. The package builder independently checked ancestry
  and that application/browser/dependency inputs did not change in U025.
- **76 passed, 2 explicit skips, zero failures/errors** in the exact-source targeted
  run: package integrity/provenance, release and CI structure, native-link behavior,
  native gate/scanner adapter, synthetic document lifecycle and permissions.
  The skips are actual ClamAV and native symbolic-link creation; neither is a pass.
- Actual Windows junction and junction-parent storage rejection **passed**.
- Added required native-storage-links CI matrix on Linux and Windows. The strict
  local gate produced **1 passed, 1 failed, 0 skipped**, correctly failing because
  this identity cannot create an actual symbolic link. The separate injected-error
  regression verifies that required link coverage cannot silently skip. This gate
  remains unfulfilled; junction coverage does not substitute for symbolic links.
- An executable builder verifies browser source/hash/provenance and creates the
  participant packet. It refuses altered evidence, browser-affecting source changes,
  incomplete browser results and overwriting existing output. Archive CRC and all
  manifest checksums were checked in regression tests.

The workflow now requires **ten final-source hosted job executions**: locked runtime
release on Linux/Windows, release reproducibility, frontend browser, actual scanner,
native PostgreSQL, SQLite, PostgreSQL service and native storage links on Linux/Windows.
Local YAML/structure checks passed. None of these is a current hosted success claim.

## Acceptance package ready for participant use

Local archive: `.verification/u025-acceptance-da60dea/acceptance.zip`.
SHA-256: `ffab0034f7b7d0e924501b625a0e318b830402aec8917ac20024796327acc57f`.
Candidate source: `da60deaf6cd89a16b2711a5bad9a0fd377b00215`.

Contents:

- `SESSION.md`: participant roles, synthetic fixture setup, manual-input and scope
  boundaries, how to record evidence and validate results.
- `SCENARIOS.md` / `scenarios.json`: the 12 browser/operational participant scenarios:
  MFA, department permissions, Fachbereich creation, own-scope search/report/export,
  edit conflict/history, document quarantine/retry/download, actual scanner detection,
  independently assigned review, archive/read-only history, recovery/monitoring,
  keyboard/manual assistive technology and the final acceptance boundary review.
- `results.json`: exact candidate source, all **12 NOT_RUN**. No participant row was
  marked passed from browser automation. Edit the extracted results during the session.
- `browser-evidence.json`: original U024 source/hash/count, retained without rewriting.
- `authorization.json`: formal pilot acceptance, real-data use and production approval
  **NOT_GRANTED**; independent review incomplete; automatic disposal disabled.
- Inert synthetic PDF/text scanner fixtures; manifest with every payload checksum.
  The PDF is explicitly an inert upload fixture, not a rendered business document.

Participants: responsible Kämmerei representative, selected Kämmerei test users,
selected Fachbereich user, and product owner/software engineer/project IT operator.
Use personal disposable accounts with approved configurable business permissions;
no broader Judith permission or infrastructure privilege is assigned. Empty register,
synthetic cases, internal/VPN scope, local TOTP. No legacy migration or real data.

The actual acceptance validator was run against the prepared results: exit **2**,
**0 PASSED / 12 NOT_RUN**, `all_scenarios_passed=false`, formal authorization false.
That refusal is expected and confirms that preparation does not complete acceptance.
Use the command in `SESSION.md` after recording real participant observations. It
requires the recorded candidate revision; it does not relabel results at a later HEAD.

## Exact remaining actions

| Status | Gate and action | Responsible role |
|---|---|---|
| VERIFIED | Local Edge 32-check execution and artifact validation. No rerun for U025 changes; repeat only if relevant inputs change. | Engineering complete |
| VERIFIED | Windows junction and junction-parent rejection. | Engineering complete |
| EXTERNALLY BLOCKED | R43: approve a separately patched synthetic host or authorized maintenance of the existing installation; reviewed 18 family requires 18.6+ and matching native clients. Verify trusted installer, restart executing server, run native attestation and repeat restricted-role/revocation, TLS, mixed workload and encrypted recovery tests. Do not treat client installation alone as server remediation. | Product owner authorizes environment/maintenance; authorized system administrator; engineering verifies |
| EXTERNALLY BLOCKED | Native clients observed read-only as 18.3; loaded binary libpq separately 18.4. Current read-only server probe unavailable and loopback test port unreachable from this environment; historical server 18.3 is not asserted as a current observation. No server restart or ACL/configuration change attempted. | Authorized host operator supplies patched, reachable synthetic environment |
| EXTERNALLY BLOCKED | Actual ClamAV executable and official current definitions must be approved/provisioned. Then run required clean/EICAR/HTTP gates, reviewed inert encrypted/macro/limit fixtures and intended-host throughput. Existing adapter/quarantine tests and Edge's synthetic scanner do not close this. | Authorized scanner/host operator, then engineering |
| EXTERNALLY BLOCKED | Run required native-storage-links on an already permitted Windows/Linux CI identity; actual symbolic-link creation must succeed. Do not change Windows privileges to manufacture local success. | Engineering after approved runner/publication access |
| EXTERNALLY BLOCKED | Authorize review-branch publication and CI execution, or provide approved equivalent runner evidence, then run all ten jobs against the final candidate. Current read-only GitHub lookup was unreachable; no push/dispatch or hosted success. | Product owner authorization, then engineering |
| EXTERNALLY BLOCKED | Provide non-secret exact STRATO product/OS/capability evidence and authorized read-only host inventory. SFTP alone establishes neither Windows administration nor persistent app hosting. Verify VPN/TLS, service identity/storage and operating recovery separately. | Product owner and authorized host operator |
| PREPARED, NOT ACCEPTED | Execute and record all 12 participant scenarios with required dependencies; resolve failures/blocked cases and obtain formal synthetic acceptance separately. | Responsible Kämmerei representative, selected users and product owner/operator |
| EXTERNALLY BLOCKED | Written financial/deadline and records/retention decisions; independent review and separate real-data/production authorization. Keep manual entry, unvalidated calculation warnings, disposal off and external workflows/escrow inactive. | Municipality and designated independent reviewers |

Development engineering evidence, synthetic technical readiness, real-data pilot
permission and broader production approval remain four distinct statuses. The first
has verified evidence; the second still has the gates above; the latter two are not
granted. Nothing was deployed or pushed. The existing PostgreSQL installation,
configuration and Windows ACLs were unchanged, and the user's Start-TestDatabase.ps1
edit is preserved unstaged.
