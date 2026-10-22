# U026 review preparation and remaining gates

U026 hosted CI execution and local artifact preservation are both **VERIFIED** for exact commit `3d4a180297db801293e4b86e42e9f60a55fbca86`, [run 39791514267](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267). All ten jobs passed; all nine saved ZIPs match published SHA-256/CRC/member hashes; required Windows/Linux native-link cases and identical nested releases are validated. [Original report/integrity receipt](evidence/u026-artifacts-verified.json), [verified execution scope](U026_HOSTED_CI_EXECUTION.md), [next operator steps](U026_NEXT_ACTIONS.md). Intended-host R43/TLS, approved host scanner/configuration, twelve NOT_RUN participant scenarios and municipal authorizations remain open. No rerun, artifact recreation, merge or deployment.

Verified engineering source: `adca68bfb9f56ae20d39e51b6c54873b758b1de4`.
[Machine evidence](evidence/u026-engineering.json), [operator handoff](U026_OPERATOR_HANDOFF.md),
[PostgreSQL maintenance proposal](U026_POSTGRESQL_PATCH_PROCEDURE.md).
Later documentation changes retain these executed-test identities. The approved review
source in `.verification/u026-review.json` is 3d4a180; hosted success and preserved
artifacts are now verified for that exact commit. Working-tree documentation updates
do not imply CI verification of a new code revision.

## Verified engineering and preserved evidence

- **87 passed, 2 skipped, zero failures/errors**, SQLite targeted regressions at the
  engineering source above: CI/release preparation, maintained-scanner policy,
  document protections, native gate, package provenance/integrity and native links.
  Explicit skips: actual ClamAV unavailable; OS denies actual symbolic-link creation.
  Actual Windows junction rejection passes. U025's strict symbolic-link failure remains
  a historical managed-identity limitation; Windows/Linux hosted native-link gates
  subsequently passed. No local privilege changes were needed.
- Local branch `review/u026-synthetic-pilot` prepared against configured remote `origin`,
  repository `https://github.com/mignoncharly/kaemmerei`. `main` remains at U025
  `223eec99bcfaafdece2d2501c4866c0cfdbdfc56`. The authorized normal-session publication
  of 3d4a180 and run 39791514267 are now independently confirmed. No main merge,
  additional publication, rerun or deployment occurred in this documentation update.
- All ten final-source hosted executions are enumerated by the executable local review
  manifest tool and now independently confirmed successful at 3d4a180.
  YAML/matrix/required-gate regressions pass. The manifest records the
  committed workflow SHA-256 separately from local working-tree bytes/line endings.
- Original U025 archive revalidated: SHA-256
  `ffab0034f7b7d0e924501b625a0e318b830402aec8917ac20024796327acc57f`, source
  `da60deaf6cd89a16b2711a5bad9a0fd377b00215`, CRC/member/payload hashes correct,
  all 12 participant rows still NOT_RUN. No participant acceptance was performed.
- U024 Edge source `d3f5ad2752feb565b5ae74ecbf90fde82ad84e4d`, 32 checks,
  SHA-256 `2de4e1f138efe1e53f9c73ee902c866840876da6809836fca9cf9b566d69f179`
  preserved and revalidated. Browser-relevant input equivalence checked; no browser rerun.

## Read-only environment observations

The latest native gate exited 2 as expected: pg_dump, pg_restore and psql are **18.3**;
separately installed postgres.exe reports **18.3**, while loaded binary libpq is **18.4**.
The dedicated loopback port is unreachable from this environment and the read-only
server query could not complete: **actual runtime server version NOT_OBSERVED**.
Do not infer stopped/running state or runtime version solely from this failed probe.
No installation, cluster start/stop, config, service, data or ACL action was performed.

Official PostgreSQL sources reviewed on 2026-10-22 list **18.6** as current for major 18.
The proposed same-major update includes vendor provenance, scoped approval, coherent
encrypted backups, verified cold rollback state, release-note applicability review,
session recycle and repeated native/RLS/MFA/recovery/mixed/host tests. No exact installer
hash is invented, no update or rollback is executed, and R43 stays open.

The scanner preflight exited 2 with EXTERNALLY_BLOCKED: no approved engine/definition
configuration. New versioned technical policy requires reviewed maintained upstream
branches (1.4.6+ or 1.5.4+ within those branches), with review expiry 2026-11-22.
Distribution backports need explicit technical review; signature-download availability
alone is insufficient. New CI preflight inventories real executable/definition hashes
before actual-engine tests. Successful inventory would still not establish signature
authenticity, freshness or detection until actual scans execute. Real integration test
changes are **VERIFIED in hosted CI with ClamAV 1.5.4**: clean/EICAR, exact
clean HTTP bytes and rejected infected/ranged access. Intended-host execution remains
**IMPLEMENTED BUT UNVERIFIED** until approved provisioning and actual checks there.
Mocked regressions and hosted results do not close the intended-host gate.

## Remaining owner actions by category

| Category / status | Exact remaining action | Owner |
|---|---|---|
| Technical implementation: VERIFIED locally | Review manifest, maintained-engine gate and acceptance checks implemented/tested; package/upgrade instructions delivered. This is not an approval to operate. | Engineering preparation complete |
| Hosted CI: VERIFIED | VERIFIED for exact commit 3d4a180: all ten jobs passed in run 39791514267. Job URLs and all nine original ZIPs are preserved and independently integrity-verified; no rerun or new collection required. | Product owner, then engineering |
| Environment verification: EXTERNALLY BLOCKED | Approve identified patched synthetic host or scoped native maintenance, trusted installer/provenance, backup/rollback window; execute operator-reviewed 18.6 update and post-upgrade tests. No update without separate approval. | Product owner and authorized PostgreSQL/host operator |
| Environment verification: EXTERNALLY BLOCKED | Provision approved maintained ClamAV and official current signatures; run preflight then actual clean/EICAR/HTTP tests, intended-host heuristics/throughput and lifecycle acceptance. | Authorized scanner/host operator, then engineering |
| Native-link CI: VERIFIED | Both required Windows/Linux native-link steps succeeded at 3d4a180; required missing-privilege paths fail rather than silently skip. Required symlink/junction JUnit cases have been inspected and passed; preserve the receipts without rerunning CI. | Engineering artifact validation |
| Intended-host verification: EXTERNALLY BLOCKED | Verify intended host service/TLS/VPN/storage/monitoring/recovery. STRATO suitability still needs non-secret product/OS/capability evidence. | Authorized host operator and engineering |
| Participant acceptance: PREPARED, NOT COMPLETE | Responsible Kämmerei representative, selected Kämmerei/Fachbereich users and product owner/operator execute twelve scenarios on an agreed recorded synthetic candidate; collect observations/issues and separate formal signoff. | Named participant roles; no fabricated results |
| Municipal authorization: EXTERNALLY BLOCKED | Written finance/deadline/records decisions, independent security review, and distinct real-data/production approval. Keep manual foundations, unvalidated-calculation notices, preservation and disposal off. | Municipality and independent reviewers |

Development, synthetic technical readiness, real-data pilot authorization and broader
production approval remain separate. Synthetic automation is verified within its scope;
environment gates and formal participant acceptance remain open. No real municipal
records, disposal, external notifications, key escrow or deployment is activated.
The user's uncommitted Start-TestDatabase.ps1 edit, PostgreSQL data, Windows ACLs and
STRATO website remain unchanged. Raw logs/credentials are not included in shared evidence.
