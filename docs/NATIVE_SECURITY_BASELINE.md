# Native component security review — U022, 22 October 2026

U023: exact R43 remediation/attestation and source-bound verification commands are
in [the synthetic acceptance package](SYNTHETIC_PILOT_ACCEPTANCE.md). Native tools
are observed separately from psycopg's loaded libpq; the read-only attestor records
both. Strict full client-output parsing and official-signature scanner enforcement
are code-side controls, not native patching or gate closure. All three original
official advisories were rechecked on 22 October 2026; no exploit attempted.

The local [inventory](evidence/phase9-u022-platform.json) observes PostgreSQL
server/client tooling 18.3. It is the dedicated loopback synthetic test platform,
not a STRATO or municipal production host. No installed binaries, cluster data,
ACLs or services were changed. Current functional test passage is not native
component security clearance or independent review.

Official evidence reviewed read-only:

| Advisory | Relevant official condition/fix | Local conclusion |
|---|---|---|
| [CVE-2026-6479](https://www.postgresql.org/support/security/CVE-2026-6479/) | A negotiation-recursion availability issue affects releases before 18.4; TCP applicability depends on SSL/GSS settings, with another socket condition documented. Fix published 14 May 2026. | 18.3 is in the affected range; complete exploit preconditions were not established or exercised. |
| [CVE-2026-14666](https://www.postgresql.org/support/security/CVE-2026-14666/) | Cached RLS plans can remain stale after specified database-role/ownership changes. Fixes include 18.6, 17.11 and 16.15, published 13 August 2026. Applicability depends on role-change and policy patterns. | Relevant to the platform review; application User-role changes are not automatically the same condition. No application exploit confirmed. |
| [CVE-2026-19385](https://www.postgresql.org/support/security/CVE-2026-19385/) | Crafted function transform metadata can compromise a pg_dump client when an attacker can create the required DB objects. Fixes include 18.6, 17.11 and 16.15, published 13 August 2026. | Observed 18.3 backup client is in the affected range. Test fixtures contain only trusted synthetic objects; no exploit attempted. |

This is a targeted review, not an exhaustive native/OS advisory clearance. It is
based on official affected ranges and conditions, not solely a version-string
vulnerability assertion. Broader Python/Windows/proxy/scanner/age patch review
and the actual host inventory remain operating acceptance work.

`app.server_security` defines a reviewed **minimum** production floor for majors
16/17/18: 16.15, 17.11 and 18.6. Older patches, unreviewed majors and malformed
versions fail closed. This floor does not certify that a version is the latest,
fully supported or free from every advisory; review current official updates and
the actual host before deployment. No environment flag disables the production
floor. Changes to this technical baseline require source review and tests.

Production web/integration startup and operator commands check the server.
Operational health reports a redacted failing security-baseline check rather
than losing its JSON failure channel. Production backup creation checks both the
server and parsed pg_dump version before snapshot export/output, including direct
library callers; production TLS remains verify-full with an explicit local CA.
Development diagnostics retain access to the isolated test platform so unrelated
engineering is not blocked. Do not run real municipal records there.

Before a hosted synthetic/user pilot: authorized system administration must
provision reviewed patched native server **and matching client tools**, capture
non-secret version/hash/patch evidence, and repeat the actual-role, backup/restore,
TLS and workload checks on that environment. The minimum gate is a control, not
the completion of that task. Do not update the existing STRATO website or native
test cluster under this document. Real-data and production authorization remain
separate, ungranted gates. R43 remains open pending patch/host verification.
