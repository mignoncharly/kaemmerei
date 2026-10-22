# U026 operator handoff — prepared, unpublished

Repository: `https://github.com/mignoncharly/kaemmerei`, remote `origin`.
Local review branch: `review/u026-synthetic-pilot`.
Workflow: `.github/workflows/phase1-verification.yml` (`Phase 1 verification foundation`).
The final local review manifest records the exact commit and committed workflow SHA-256.
No push, PR, workflow dispatch or hosted execution has been performed or authorized.

## Publication and ten final-source checks

Before publication, review `.verification/u026-review.json` and the source-bound
evidence linked from the U026 remaining-gates record. It identifies these ten runs:

| Job | Execution platforms |
|---|---|
| locked-release | ubuntu-24.04 and windows-latest |
| release-reproducibility | ubuntu-24.04 |
| native-storage-links | ubuntu-24.04 and windows-latest |
| frontend-browser | ubuntu-24.04 |
| document-scanner | ubuntu-24.04 |
| native-postgresql | ubuntu-24.04 |
| sqlite | ubuntu-latest |
| postgresql | ubuntu-24.04 |

All hosted outcomes are NOT_RUN. Local YAML checks are not hosted results. Publishing
this branch triggers the workflow's existing push event automatically; publication
approval must account for the hosted jobs, dependency downloads and disposable CI
services. Do not push merely to find out whether CI works. After explicit approval,
publish the **exact manifest commit**, without force, to the named remote branch:

```text
git push origin <approved-exact-commit>:refs/heads/review/u026-synthetic-pilot
```

This is a reviewable future command, not executed. Do not substitute a later HEAD.
Record run IDs, head_sha, per-job conclusions, workflow blob hash and artifact hashes.
Require every listed execution on the final source; old hosted successes do not count.
A new code/workflow change requires a new final-source run. No deployment follows CI.

## R43 maintenance handoff

Use [the reviewed PostgreSQL proposal](U026_POSTGRESQL_PATCH_PROCEDURE.md). It separates
read-only version evidence, installer/host approval, encrypted backup/rollback go-no-go,
authorized minor update and post-upgrade tests. No existing PostgreSQL installation or
data is changed by the review manifest or scanner inventory tools.

## Maintained ClamAV and real integration handoff

An approved host operator selects a maintained **clamscan**, not clamdscan, from
[official installers/portable packages](https://docs.clamav.net/manual/Installing.html#windows)
or a reviewed signed distribution. Verify the downloaded package and detached signature
using the vendor's documented GPG procedure and a verified Talos key; record signer,
package hash, architecture and provenance privately. No download or install was done here.
Signature access alone does not establish patch support: review the
[support matrix](https://docs.clamav.net/faq/faq-eol.html#version-support-matrix).
As observed 2026-10-22, supported policy floors are 1.4.6 LTS or 1.5.4, within those
reviewed branches. Distribution backports or new branches require explicit technical
review. `docs/pilot/scanner-engine-baseline-v1.json` is configurable, versioned and
expires on 2026-11-22 so stale review cannot silently become a pass.

The host operator provisions an approved isolated definitions directory and valid
freshclam.conf. [FreshClam](https://docs.clamav.net/manual/Usage/SignatureManagement.html)
downloads/updates official CVD/CLD signatures. Do not use unverified custom signatures,
disable TLS, add security exclusions, expose clamd, run recursive system scans or use
remove/move options. Provisioning/network/update actions are separate from the read-only
preflight. Preserve existing Windows ACLs; no permissions bypass is prescribed.

With approved existing absolute paths set locally as CLAMAV_EXECUTABLE and
CLAMAV_DATABASE_DIR, run preflight, then integration only if preflight succeeds:

```powershell
python -m scripts.scanner_readiness --expected-source ((git rev-parse HEAD).Trim()) --output .verification/scanner-preflight-UNIQUE.json
if ($LASTEXITCODE -eq 0) {
    python -m scripts.run_pilot_verification --expected-source ((git rev-parse HEAD).Trim()) --selection scanner --output .verification/scanner-integration-UNIQUE
}
```

Preflight reads engine version/binary and main/daily definition hashes; status
READY_FOR_REAL_ENGINE_TESTS is **not** detection, freshness or signature-authenticity
verification. The integration test uses the actual adapter with official-db-only,
freshness, heuristic encrypted/macro/limit alerts and existing upload constraints.
It scans synthetic clean bytes and in-memory EICAR, checks exact clean HTTP download
bytes, rejected infected state and denied ranged download. Missing engine fails the
required gate. No mocked engine or fixture result closes this gate. Raw scanner output
and EICAR bytes are not shared; reports contain sanitized source/outcomes and hashes.
Current local preparation does not assert any real-engine pass.

The required CI scanner job performs maintained-engine preflight before real HTTP
checks under restricted PostgreSQL roles. Review inert encrypted/macro/oversize fixture
outcomes, queued outage/retry and representative throughput on the intended host as
separate follow-ups; one EICAR case does not establish all scanner acceptance.

## Kämmerei participant instructions and evidence

Original U025 packet: `.verification/u025-acceptance-da60dea/acceptance.zip`.
Exact source: `da60deaf6cd89a16b2711a5bad9a0fd377b00215`.
Archive SHA-256: `ffab0034f7b7d0e924501b625a0e318b830402aec8917ac20024796327acc57f`.
Preserve it unchanged. The read-only review-manifest tool verifies archive SHA-256,
CRC, member set, every manifest payload hash, 12 NOT_RUN rows and the original Edge
source/hash. Extract a **working copy** for participant records, retaining the original.

1. Responsible Kämmerei representative and operator agree the actual synthetic session
   revision/environment, selected Fachbereich and allowed accounts. If using a later
   candidate, build a fresh candidate packet with the tracked builder; do not silently
   rewrite the original packet's source. Record actual browser/environment separately.
2. Selected Kämmerei/Fachbereich users use separate personal browser profiles and
   disposable accounts with TOTP and provisional configurable business permissions.
   Keep the register empty initially; create only the fictional SYN-PILOT cases in
   SESSION.md. No legacy or real municipal records, extra Judith grants or shared TOTP.
3. Follow SCENARIOS.md for all twelve cases. The operator prepares synthetic accounts,
   independent eligible reviewer and disposable recovery targets. If actual scanner or
   host dependencies are unavailable, record BLOCKED rather than bypassing controls.
   Manual dates/amounts supply no approved accounting/deadline interpretation.
4. For each executed case record participant **role**, actual observations, timezone-
   bearing timestamp, outcome and local evidence reference in results.json. Keep
   NOT_RUN for untouched cases. A PASSED row needs all evidence fields. Record issues
   and remediation before retest; never copy the 32 automated browser checks into
   participant acceptance. Record actual assistive technology for the manual case.
5. Use the source-bound validator command in SESSION.md from the **recorded candidate
   checkout**; a mismatched HEAD must not be relabeled. A fresh candidate packet may be
   prepared for the review branch after its technical gates are satisfied. Keep raw
   logs/screenshots local; no credentials, TOTP seeds/codes, personal identities,
   municipal documents or authenticated URLs in shared evidence. Hash approved sanitized
   evidence and retain the immutable original packet plus the separate session results.

No participant case was executed in this preparation. Formal synthetic acceptance
needs the responsible representative, selected users and product owner/operator to
review actual outcomes and record the acceptance decision. Financial/deadline/records
decisions, independent security review, real-data authorization and production approval
remain separate. Automatic disposal, external notifications and key escrow stay inactive.
