# U026 hosted CI execution and local artifact preservation - VERIFIED

Both gates are **VERIFIED** for exact tested commit `3d4a180297db801293e4b86e42e9f60a55fbca86`, branch `review/u026-synthetic-pilot`.
[GitHub Actions run 39791514267](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267): **10/10 jobs successful**, duration **14m 42s**, **9 artifacts**.
Workflow `.github/workflows/phase1-verification.yml`; committed SHA-256 `e535b4fc846684965fbd883b38a856f0df0216cdff024c042d69769bc630c6ae`.

[Hosted execution evidence](evidence/u026-hosted-ci-success.json) and [independently validated local artifact receipt](evidence/u026-artifacts-verified.json). No CI/browser rerun, new download, artifact recreation, push, merge or deployment was performed for this validation.

## Exact local report and original artifacts

Inspected the exact user-specified report, relative to the repository:

`.verification/u026-confirmed-run/preserved-8ca121aa85ff4b1b8e8c4b7ea9278dd8/sanitized-report.json`

Report SHA-256: `98cce9fd325d240cb138ab62e30880ba244f22aa1031c01f01545fb0fd1c582e`.

Its status is VERIFIED, source/run identity agrees with GitHub evidence, read_only=true and push_or_dispatch_performed=false. All nine original ZIPs remain unchanged under the same run directory in `private/`. Independently recomputed each published ZIP SHA-256, ZIP CRC and every outer member hash. Both nested source releases were also checked against their manifest/path/size/hash inventory without extracting or executing code.

**No further collection or rerun is required.** Preserve the original report, ZIPs and integrity records. Earlier partial/failed attempts remain historical evidence; they do not override the completed receipt. Raw artifacts/logs stay local; share curated sanitized records.

## Final job results

| Job | Actual result and job URL |
|---|---|
| document-scanner | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868511637) |
| sqlite | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868511886) |
| locked-release (windows-latest) | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868511935) |
| native-postgresql | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868512038) |
| native-storage-links (windows-latest) | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868512044) |
| locked-release (ubuntu-24.04) | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868512127) |
| frontend-browser | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868512144) |
| native-storage-links (ubuntu-24.04) | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868512158) |
| postgresql | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119868512251) |
| release-reproducibility | [SUCCESS](https://github.com/mignoncharly/kaemmerei/actions/runs/39791514267/job/119869164432) |

## Nine preserved artifacts

| Artifact | Verified ZIP SHA-256 |
|---|---|
| document-scanner-verification | `739bd19e598cea1af30146176095636bb7643bf1bff19ccc364b6b74f7865f79` |
| native-postgresql-verification | `ce07822162f9996544a85c30a2b30c6b7f5fed3ecc9eb37ef959310e4d72095e` |
| native-storage-links-ubuntu-24.04 | `0ee91f9f37811cb5a902fe3a273715625acc592404915f4e9dba187238ea34c3` |
| native-storage-links-windows-latest | `b703a3fa1018d469036f02413f38c3635cefb00c7de6c10b6dc326acbf1cacbf` |
| phase8-browser-verification | `6cbaeac63b6f80a4c36870ac5370e6821ddc55b0bba6baccc20f9e08e6dd1713` |
| postgresql-verification | `30c2d2a2a39ca6296f0c1adab766dd6e7a27701bb2ed4815a6d5bdd9dd692c51` |
| runtime-release-ubuntu-24.04 | `9f893e8e1a334d5f9d8066098dc12812ee71c5c495cd2ed14c40802d77db67a1` |
| runtime-release-windows-latest | `518ea2ce4715798935d16ebf6649b597d839092290098f38e7ebdfcd8a63fe70` |
| sqlite-verification | `5871e48ca4eb21143d44876532e0e76e016d135245b18da9346de23ece05bce9` |

GitHub retention expiry is 2027-01-20; downloaded originals are now preserved locally. The two platform wrapper ZIPs differ because they contain platform-specific test evidence; their nested source releases are identical:

- Source-release SHA-256: `528b00f3d609a1313d749ae32ae697dc89b24b045a8292d54347cf5238837c6a`.
- Exact source: `3d4a180297db801293e4b86e42e9f60a55fbca86`; 128 payload files; migration head `0027_child_read_admission`.
- Windows native-link JUnit: **2 passed, 0 skipped** (actual symlink and junction rejection).
- Linux native-link JUnit: actual symlink **passed**; one non-applicable Windows-junction case skipped. No required native-link case silently skipped.

## Contents verified and limits of the evidence

| Selection | Recorded evidence | Scope boundary |
|---|---|
| Native PostgreSQL | Server and pg_dump/pg_restore/psql 16.15; baseline passed; 403 passed/8 skips/15 subtests in full suite | Disposable Linux CI, not intended host |
| Service PostgreSQL | Server and matching native clients 18.6; baseline passed; 403 passed/8 skips/15 subtests in full suite | Disposable loopback CI; SSL disabled, not production TLS |
| SQLite | 361 passed/50 skips/15 subtests | Development/backend selection |
| Hosted real scanner | ClamAV 1.5.4; one actual clean/EICAR/HTTP test passed, zero skips; exact clean download and denied infected download | Linux CI engine, not intended-host scanner |
| Hosted browser | Synthetic result passed at exact CI source, browser 156.0.8078.4 | Distinct from local U024 Edge; no participant acceptance |
| Backup/recovery and workload | Both CI backup selections 19 passed/zero skips; representative mixed runner VERIFIED | Synthetic isolated CI; not intended-host RPO/RTO/TLS acceptance |
| Source release | Both platform release selections 30 passed; identical nested source manifests/hashes | Packaging/integrity only; no deployment |

Full-suite skips were reviewed directly in the preserved JUnit. All 42 additional SQLite skips have passing counterparts in the PostgreSQL suite, including two native-age fixtures not provisioned in the SQLite job. Eight skips are shared by both Linux full suites: the real scanner is covered by its separate real-engine job, the Windows junction by its Windows job, and six Windows-only PowerShell parser/wrapper cases remain Linux OS skips. Those six retain their earlier local Windows evidence; the hosted Windows release job is not falsely described as having run them. Targeted suites overlap the full suites and are not added into a fabricated grand total.

Both native attestation JSONs explicitly keep r43_closed=false. The service test verified PostgreSQL 18.6 and the native job 16.15; loaded CI libpq was 18.6. Both CI servers report SSL disabled on disposable loopback. None changes the last-observed local 18.3 binaries or proves intended-host TLS.

## Remaining acceptance and authorization boundaries

- **VERIFIED:** hosted CI execution, nine original artifacts/integrity receipts, required Windows/Linux native-link execution and identical nested source release for the exact tested commit.
- **EXTERNALLY BLOCKED:** intended operating host selection/suitability, authorized R43 patch/TLS verification, approved maintained scanner installation and tests under actual host identities, service/network/storage/monitoring/recovery configuration.
- **PREPARED, NOT ACCEPTED:** original U025 packet remains unchanged; all **12 participant scenarios NOT_RUN**. Written financial/deadline/records decisions, independent security review, real-data authorization and production approval remain separate.
- No merge into main, PostgreSQL installation/data/ACL change, STRATO website modification, real-data processing, external notification/escrow activation or deployment occurred.

[Prioritized next operator and engineering actions](U026_NEXT_ACTIONS.md).

## Historical pre-success execution record (superseded)

The following is retained for chronology only. Do not repeat its old push/collection commands for this successful candidate.



# U026 hosted CI GO: authorized attempt and execution-environment block

The product owner explicitly authorized publication and hosted CI of:

- Repository `https://github.com/mignoncharly/kaemmerei`
- Branch `review/u026-synthetic-pilot`
- Exact commit `3d4a180297db801293e4b86e42e9f60a55fbca86`
- Workflow `.github/workflows/phase1-verification.yml`
- Committed workflow SHA-256 `e535b4fc846684965fbd883b38a856f0df0216cdff024c042d69769bc630c6ae`

This supersedes the earlier **authorization pending** statements for this exact
publication/CI action. It grants no deployment, main merge, local PostgreSQL upgrade,
ACL modification or real-data permission. Corrections and reruns on the isolated
review branch are authorized after actual check failures; none has been observed yet.

## Actual executed work

The pre-push static review verified that the candidate has one workflow, contents:read
token permissions, no deployment steps or production endpoint, and no repository-secret
references. It uses synthetic loopback PostgreSQL credentials and disposable hosted
runners. The explicit artifact lists exclude passfiles, connection JSON and key files;
browser screenshots occur before disposable MFA secret entry. Release-building creates
source/configuration artifacts without deployment. No other push-triggered workflow
exists in the candidate. This is a source review, not hosted runtime proof.

Executed the exact authorized push, without force and without updating main:

```text
git push origin 3d4a180297db801293e4b86e42e9f60a55fbca86:refs/heads/review/u026-synthetic-pilot
```

**Git exited 1 before reaching GitHub.** The managed execution environment sets
HTTP/HTTPS/ALL proxy transport to unavailable loopback port 9. No Git-specific proxy
override exists. The attempted push published no branch. A separate API observation
also failed before any hosted result could be retrieved. No browser/connected GitHub
session is available. No proxy override, network-security bypass or credential request
was attempted. The global remote-ref/run state is **NOT_OBSERVED**, not asserted absent.

[Machine-readable attempt and all ten check rows](evidence/u026-hosted-ci-attempt.json)
records the authorized source, failed transport, null tested commits/run URLs, helper
hashes and preservation checks. No job is marked passed, failed, skipped or executed
based on this transport failure. There is no actual GitHub run URL to report yet.

## Concrete local execution handoff

The complete local helper is outside the approved commit under
`.verification/u026-hosted-ci/`; it does not change the branch's commit or pushed source.
The wrapper pins the helper SHA-256 and uses the existing workspace Python environment.
From the repository in the normal authorized Windows PowerShell session, execute:

```powershell
.\.verification\u026-hosted-ci\Invoke-U026.ps1
```

The helper:

1. Verifies exact HEAD/branch/remote, the pinned workflow, absence of additional
   workflows, unchanged application/test inputs and no unreviewed pre-push hook. It
   deliberately preserves the existing Start-TestDatabase.ps1 modification.
2. Pushes **only** the approved commit to the review branch, with no force or merge.
   Uses existing Git credentials without soliciting new credentials. It does not
   change proxy settings, TLS trust, ACLs, installations or the current website.
3. Verifies the remote ref points at the exact commit, observes the automatic push run,
   and dispatches the same workflow only if no matching run appears after 90 seconds.
4. Polls up to one hour and records each job's result, tested commit, job/run URL and
   failed step names. Missing/incomplete checks cannot become success. It does not
   automatically rerun a failure without engineering diagnosis/correction.
5. Downloads Windows/Linux native-link artifacts privately and parses JUnit in memory,
   without extracting files. Requires actual symbolic-link rejection to execute/pass on
   both platforms and actual junction rejection to execute/pass on Windows. A Linux-only
   non-applicable Windows-junction skip is allowed and explicitly distinguished. Ten
   green jobs without these required artifact cases are insufficient for verification.
6. Keeps raw logs, signed artifact URLs, credentials and downloaded archives private.
   GitHub authorization headers are never forwarded to artifact-storage redirects.
   On a failed run it saves raw GitHub logs locally for engineering diagnosis.
7. Writes `sanitized-report.json` under a new UUID run directory and verifies the local
   launcher and main ref remain unchanged. Only this sanitized report is shareable.

**Executed helper regressions: 7 passed, 0 failed**, including the actual PowerShell
parser, exact-candidate preflight, required skip rejection, missing artifact handling,
ten-green-but-unverified cases, authenticated-URL filtering and no token forwarding.
These tests use simulated GitHub responses; they are not hosted/native-link CI passes.
Actual helper API smoke test here correctly returned NOT_VERIFIED with a fixed network
error and preservation booleans true. No PostgreSQL/browser tests were rerun here.

## Ten required checks: actual outcomes pending

| Required job | Platform | Actual result / run URL |
|---|---|---|
| locked-release | ubuntu-24.04 | NOT_OBSERVED / none |
| locked-release | windows-latest | NOT_OBSERVED / none |
| release-reproducibility | ubuntu-24.04 | NOT_OBSERVED / none |
| native-storage-links | ubuntu-24.04 | NOT_OBSERVED / none |
| native-storage-links | windows-latest | NOT_OBSERVED / none |
| frontend-browser | ubuntu-24.04 | NOT_OBSERVED / none |
| document-scanner | ubuntu-24.04 | NOT_OBSERVED / none |
| native-postgresql | ubuntu-24.04 | NOT_OBSERVED / none |
| sqlite | ubuntu-latest | NOT_OBSERVED / none |
| postgresql | ubuntu-24.04 | NOT_OBSERVED / none |

**VERIFIED:** pre-push source/permission/artifact audit; seven collector regressions;
approved candidate/main/launcher preservation. Prior U024/U025 evidence remains intact.

**IMPLEMENTED BUT UNVERIFIED against GitHub:** exact publication/polling/artifact
collection helper. Actual hosted test outcomes and executed native-link coverage are
pending; no underlying hosted test failure can be diagnosed before results exist.

**EXTERNALLY BLOCKED:** managed execution network transport. Existing GO permission
remains valid; no new authorization is needed to run the normal-session helper.
Patched actual host, maintained real scanner, independent review, twelve participant
outcomes and municipal real-data/production approvals remain their separate gates.
Formal pilot acceptance is not complete. No deployment, main merge, ACL or PostgreSQL
data/installation change was performed.


