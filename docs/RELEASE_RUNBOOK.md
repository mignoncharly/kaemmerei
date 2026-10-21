# Reviewable pilot rollout and recovery procedure — U022

This is a preparation artifact, not an execution authorization. Four separate
statuses are maintained in [PILOT_DECISIONS](PILOT_DECISIONS.md). Current technical
test evidence belongs to its exact Git revision; earlier CI does not cover new
source. No external push/deploy or workflow dispatch is authorized this session.

## Prepare the synthetic technical pilot

1. Freeze source, record commit/artifact SHA-256, runtime lock, schema head and
   configuration references. Build twice and verify the source manifest. Run
   packaged startup/migrations using only the locked runtime before dev tools.
2. Confirm the actual host/product and internal/VPN boundary without affecting the
   separate website. Verify Windows process supervision, restart behavior, proxy
   HTTPS/redirects, trusted forwarding, secure cookies, DB verify-full TLS, restricted
   roles/RLS, private ACLs, scanner definitions, quotas and available space.
3. Provision an **empty** isolated register and two departments (Kämmerei plus the
   selected Fachbereich). No legacy import is needed. Provision personal test
   accounts with the provisional matrix and require TOTP via the existing owner
   procedure. Verify revocation/recovery with disposable test factors. Do not put
   fixture accounts, test keys or business permission assumptions into production.
4. Review the disabled Windows task definitions and separate service identities/
   passfiles for web, scan, authentication purge, reconciliation, event publication,
   integration-status, backup and monitoring. Registration needs later explicit
   authorization. Confirm local monitoring actually has a responsible reviewer.
5. Run the Phase 10 synthetic journeys with the recorded acceptance participants.
   Record actual outcomes per step. Finance/calendar examples remain unvalidated;
   preserve disagreements for written clarification. Disposal/external delivery
   remain disabled. Do not represent this as real-data acceptance.

## Checkpoints and stop criteria

Before any future authorized upgrade of business data: verified encrypted database
and document backup, independently trusted receipt/digest, key availability via
the approved local procedure, timed new-target restore and restricted-role checks.
Keep the prior application artifact/configuration and original database/storage
untouched during rehearsal. Empty first pilot removes legacy migration mapping;
it does not remove schema/backup/reconciliation checks for future upgrades.

Stop if source/schema identity differs, migration/reconciliation fails, unauthorized
scope appears, documents lack valid scan/hash, monitoring is stale, backup age
exceeds 24h or ordinary-page/export targets fail. Record evidence and reopen the
affected phase. A failed run is not replaced by an undocumented smaller workload.

## Rollback rehearsal

The automated encrypted restore exercises create a **new positively identified
empty disposable PostgreSQL target**, verify signature/authentication/member hashes,
restore database and file storage together, reapply explicit restricted-role grants,
and verify IDs, file bytes, revision history, MFA replay state and department access.
The representative selection adds 10k contracts/50k document metadata/20k history
and 500 inert PDFs. Its measured snapshot age and restore time are local observations;
off-host/custody/schedule and actual-host 24h RPO/4h RTO acceptance are separate.

After an authorized production incident, choose compatible application rollback
only when schema compatibility has been tested. Otherwise use the rehearsed
consistent DB/document restore to a new approved target, validate and deliberately
switch routing. Do not downgrade/drop schema or bypass RLS/scanning/MFA. Keep the
failed instance preserved for controlled investigation under the records policy.
Actual proxy switching, service restart and site-level rollback remain unperformed.

## Operating review and release

Provisional system administration reviews local failed/stale job checks and backup
age; identity/security roles handle sensitive recovery. Record triage, action and
resolution references without secrets. Confirm patch cadence and native tool
versions on the actual host; local inventory is not host acceptance. Re-review
these preparations at the next test/host/domain evidence change and before any
authorization request. Wider production additionally requires independent security
review, records/business approvals and formal municipal release authorization.
