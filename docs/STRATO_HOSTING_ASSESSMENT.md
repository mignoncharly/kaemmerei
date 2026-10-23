# STRATO read-only hosting assessment

2026-10-22: **SSH/SFTP access and existing-pin verification VERIFIED; hosting
suitability UNVERIFIED.** The owner will establish the exact product/tariff through
the authenticated customer account. No further remote discovery, changes or deployment
is requested or performed in this update. Native Windows/PostgreSQL/TLS remains the
approved architecture.

## Completed local evidence

The owner completed the local inspector. Engineering located and inspected the actual
sanitized report, confirmed its success/unchanged-state fields and computed its SHA-256
without rerunning SSH or downloading website files:

- Report: `.verification/strato-readonly-052a35280f3549a79b3f4a876a2af27f/sanitized-report.json`.
- Observation: `2026-10-22T16:33:27.441698+00:00`.
- Status: `COMPLETED_READ_ONLY_DISCOVERY`; error code/stage: null.
- SHA-256: `6a0e0011352f47e762c4de04cab1cab9a879952be940419c75e069ea46702562`.
- [Curated completed-run receipt](evidence/strato-completed-assessment.json).

Original report and prior failure/preflight receipts remain unchanged. Earlier local
JSON/dependency restrictions do not negate this completed normal-session execution.
Repository base at review is `3d4a180297db801293e4b86e42e9f60a55fbca86`; the inspector
is a working-tree addition and its report does not attest an executed Git commit.
Do not equate this assessment with the separately source-bound U026 hosted CI evidence.

| Verified fact | Evidence source | Scope / limit |
|---|---|---|
| SSH authentication succeeded | Completed report `connection_authenticated: true` | No administrative entitlement follows. |
| SFTP subsystem available | `sftp_supported: true` | No website transfer, directory inventory or application-file read was performed. |
| SSH shell/exec channel available | `shell_supported: true` | Channel acceptance does not prove unrestricted commands, an interactive shell or persistent service hosting. |
| Existing Ed25519 pin used successfully | Prior exact-endpoint cache inspection plus completed report `host_key_verified_before_authentication: true`, `cached_endpoint_pin_usable: true` | **Previously established TOFU trust**; independently provider-verified identity is not claimed. Unknown/changed keys are not accepted or saved. |
| No remote modifications/application-file reads | `remote_changes_performed: false`, `application_files_read: false`; owner confirmation | No service/config/database/ACL/website changes. These fields are execution evidence, not an independent availability audit of existing projects. |
| No credential material recorded | `credential_material_recorded: false` | No endpoints, usernames, passwords, private keys, authenticated URLs or unrelated host details are included here. |

OS probes returned `UNAVAILABLE_OR_RESTRICTED` for both `os_family` and `windows_os`.
This establishes **neither Linux nor Windows** and does not identify why the commands
were unavailable. No additional probes are authorized by this document.

## Provider-documented characteristics and inference

Official STRATO [SSH/SFTP instructions](https://www.strato.de/faq/hosting/so-nutzen-sie-ihren-ssh-sftp-zugang/)
describe webspace-scoped accounts, separate SFTP versus SFTP+SSH access and personalized
SFTP server names. The [SFTP connection guide](https://www.strato.de/faq/hosting/so-verbinden-sie-sich-mit-dem-strato-sftp-server/)
documents the hosting hostname pattern and customer-account location for access details.
These are public product-family characteristics, not this account's tariff inventory.

**Inference only:** the reported hostname format is consistent with managed webhosting
as documented there. It does not confirm the purchased package, OS, virtual-machine
ownership, administrator access or an entitlement to native Windows services. SFTP and
shell availability are compatible with restricted webspace access. No personalized
hostname or account information was sent to documentation/search services or copied here.

## Unresolved capabilities and OPEN.HERZ compatibility

| Capability | Current assessment | Evidence still needed |
|---|---|---|
| Exact product/tariff and OS | UNVERIFIED | Owner's non-secret product/category evidence; explicit Windows OS/service entitlement. Hostname alone is insufficient. |
| Administration | UNVERIFIED | Delegated Windows service/task, PostgreSQL and network administration rights; successful SSH login supplies none of these automatically. |
| Python/FastAPI persistent hosting | UNVERIFIED | Supported runtime, permitted persistent service, restart/reboot supervision and resource allocation. |
| PostgreSQL hosting/access | UNVERIFIED | Approved database allocation/installation rights, executing server/client/libpq versions, roles/RLS, verify-full TLS; no database contents inspected. |
| TLS web server/reverse proxy | UNVERIFIED | Approved hostname/certificate, proxy binding/configuration authority and forwarding/security behavior. |
| Internal/VPN-only access | UNVERIFIED | Provider capabilities and reviewed network isolation, including denial outside the approved boundary. |
| Storage/resources | UNVERIFIED | Private storage, quotas, capacity and least-privilege isolation from existing projects. |
| ClamAV/background workers | UNVERIFIED | Maintained native binaries, official definitions, service identity/scheduling rights, actual detection/retry/throughput evidence. |
| Encrypted backup/recovery | UNVERIFIED | Isolated protected destination, local key custody and coherent DB/document restore evidence; no backups triggered. |
| Isolated Windows synthetic pilot | NOT DEMONSTRATED | All required Windows/runtime/network/database/storage/operations capabilities and scoped provisioning authorization. |

A separate Windows VM/server is **conditionally required** if the actual product lacks
native Windows administration and the needed persistent services. It is not yet proven
necessary because product/OS entitlement is unresolved. Do not substitute Linux,
containers or another hosting model, purchase resources or deploy to test suitability.

The environment already hosts active projects. Any future co-location proposal must
address resource contention, shared binaries/services, port/routing collisions, storage
exhaustion and cross-project access. These are review risks, not observed incidents.
The completed read-only access test does not approve co-location or establish capacity.

## Next engineering and operator steps

1. **Owner:** establish the exact product/tariff in the authenticated customer account.
   Return only non-secret category, OS and service/network/storage entitlement evidence;
   omit account numbers, credentials and unrelated project information. No support
   fingerprint ticket or repeat SSH assessment is required.
2. **Engineering:** reconcile that evidence with [isolated Windows pilot requirements](WINDOWS_SYNTHETIC_PILOT_REQUIREMENTS.md).
   Preparation is concrete: required capabilities, evidence/owner assignments, source
   guard, isolation plan, native/TLS distinction and scanner exercise instructions.
3. **Operator/engineering after separate scope approval:** provision the selected isolated
   Windows target, complete [R43 maintenance and evidence worksheet](U026_POSTGRESQL_PATCH_PROCEDURE.md),
   real native scanner checks, service/TLS/network/storage checks and encrypted recovery.
   No installation, restart, signature update, workload or recovery exercise now.
4. **Participants/municipality:** all twelve synthetic scenarios remain NOT_RUN.
   Finance/deadline/records decisions, independent security review, formal synthetic
   acceptance, real-data authorization and production approval remain separate gates.

R43 stays open on the intended host; hosted PostgreSQL success does not close its
patch/TLS requirements. Hosted scanner success does not replace the intended-host
engine exercise. Start empty, use synthetic contracts only, retain provisional
configurable roles/local TOTP and internal/VPN scope. Disposal, external notifications
and production recovery-key escrow remain disabled.

## Preservation and verification scope

This update only inspected the saved sanitized report, validated its schema fields/hash
and prepared local documentation. It did not reread credentials, connect to STRATO,
rerun discovery/CI, read application files, alter infrastructure, merge or deploy.
Existing PostgreSQL data, Windows ACLs, the owner's Start-TestDatabase.ps1 edit and
all unrelated local changes are retained. Prior 41 inspector regressions are historical
test evidence; no application/browser/scanner/host tests were rerun for this document update.
