# Production readiness: blockers and product-owner inputs

U022 final local verification: implementation `05648ed`, PostgreSQL 343 passed/2 skips, SQLite 309 passed/36 skips, 15 subtests each; full representative mixed workload and encrypted restore passed. [Exact evidence, scope and remaining release gates](U022_ENGINEERING_VERIFICATION.md). Synthetic scope approval is separate from actual-host/participant acceptance and real-data/production authorization.

## U022 decision update — 21 October 2026

Pilot scope, provisional permissions, empty-register/synthetic-only data and
acceptance participant roles are now decided. See [PILOT_DECISIONS](PILOT_DECISIONS.md)
for the controlling record, four release statuses and remaining written
finance/deadline/records and actual-host dependencies. Sections 2 and 6 below are
historical pre-decision context; do not request settled decisions again. Current
implementation/test evidence belongs to HANDOFF U022. Earlier U021 results apply
only to their recorded source revision. No Judith/infrastructure grant, municipal
authorization, notification, escrow, website change or deployment is implied.

Status summary: 21 October 2026. This document summarizes the current handoff and distinguishes product decisions from remaining engineering work. It does not replace the remediation plan or its acceptance records.

## 1. Where we stand 

The remediation plan has **not yet reached full production acceptance**:

- **Phases 1–8:** technically verified.
- **Phase 9:** substantial implementation completed; operational verification and some engineering work remain.
- **Phase 10:** acceptance preparation exists; business validation, independent review and rollout acceptance remain open.

Current local evidence: implementation `05648eda3ce6ddb9fe7e33082593e294522fbf24` passed 343 PostgreSQL tests with 2 explicit skips and 15 subtests; the representative mixed workload and encrypted restore passed. Eight hosted CI jobs belong only to prior `3442ad8`; no current-source hosted CI was dispatched. See the U022 report above.

The original PostgreSQL startup problem and security defects R01, R04 and R10 are resolved. The remaining blockers concern production readiness and acceptance.

**Crucial** means required before the indicated release stage. **Can wait** means it can be deferred if the product owner explicitly accepts the resulting release scope.

## 2. What the product owner needs to provide

| Input or confirmation | Exactly what is needed | Priority |
|---|---|---|
| **First release scope** | Which departments participate first; whether access is internal/network/VPN or publicly reachable; which user roles and workflows the first release must support. | **Crucial before configuring the real-user pilot.** |
| **Business permission and approval rules** | Confirm the implemented department restrictions, reviewer assignments, approval requirements and transfer rules, or specify necessary changes. A short role-to-permission matrix is sufficient. | **Crucial before users access real departmental data.** Engineering can demonstrate the existing rules first. |
| **Financial and deadline interpretation** | A responsible business role must validate representative reporting totals, income/expense treatment, unknown amounts, renewal and notice-date examples. | **Crucial before users rely on those features.** A feature can be withheld from the first release if explicitly agreed. |
| **Initial data approach** | Decide between an empty register and migration of existing records. For migration: sanitized examples, field mappings, document sources and treatment of incomplete legacy records. | **Migration can wait for an empty pilot. Crucial if existing records must be available at launch.** |
| **Actual hosting arrangement** | Coordinate a staging/production Windows host, intended domain, network access, storage and backup destination, plus an approved secure way to configure them. The platform choice is already settled. | **Crucial before a hosted real-user pilot.** Engineering handles application configuration and verification once the environment is available. |
| **Production operating responsibilities** | Confirm which existing roles will monitor failures, manage accounts, patch systems, restore backups and authorize sensitive administrator recovery. Confirm secure custody arrangements for production encryption/recovery keys. | **Crucial before live operation.** The provisional role assignments remain valid for preparation; named individuals or a dedicated IAM team are unnecessary. |
| **Records and data-handling rules** | Confirm permitted data, export/access restrictions, retention, legal holds and treatment of documents, audit records and backups. An agreed temporary preservation/manual procedure may support a limited pilot. | **Crucial before real-data use.** Automated deletion can remain disabled. |
| **Business acceptance participants** | Identify representative departmental roles who will exercise realistic workflows and validate results. Engineering prepares the environment, scenarios and evidence. | **Crucial for pilot acceptance and wider rollout.** Their evaluation happens during the controlled pilot. |
| **Independent review and release acceptance** | Arrange the independent security/permission review required by the plan and identify the role accountable for accepting the final release and documented residual limitations. | **Crucial before broader production rollout.** Preparation and engineering can continue now. |

Do not provide passwords, tokens, recovery keys or `.env` contents in chat. Infrastructure and secret provisioning should use the agreed secure mechanism.

## 3. Engineering work that can continue without further product decisions

These are remaining implementation and verification responsibilities. They should not be presented as work waiting entirely on the product owner.

| Remaining work | Priority and dependency |
|---|---|
| Complete outstanding maintenance jobs, scheduling, cleanup and event processing; verify retries, locking and failure visibility. | **Crucial before live operation.** Can continue now. |
| Finish operational health information: failed jobs, database problems, disk capacity, backup age and relevant security events. | **Crucial before live operation.** Local implementation can continue; external delivery needs an agreed destination later. |
| Run representative mixed workload tests covering dated contracts, history, reviews, login, uploads, scanning and exports. Existing performance evidence covers a narrower dataset. | **Crucial.** Workload targets are already approved; no further target decision is needed. |
| Exercise representative encrypted database-and-document recovery and measure recovery time and recoverable data age. Existing successful restores use small fixtures. | **Crucial.** Local rehearsals can continue; final acceptance needs the actual operating environment. |
| Verify the deployed Windows service, TLS proxy, database TLS, trusted forwarding, filesystem permissions, quotas and failure recovery. Configuration templates alone do not establish this. | **Crucial before hosted real-user access.** Needs the actual host. |
| Complete the wider infrastructure dependency/update inventory, release documentation, rollout procedure, rollback rehearsal and remaining acceptance checks. | **Crucial before production release.** Much of this can continue now. |

## 4. What can wait

| Item | Can it wait? |
|---|---|
| **SSO / LDAP** | **Yes.** Local accounts with TOTP MFA have already been selected. |
| **Specific accounting, procurement or DMS adapters** | **Yes, if excluded from release one and the manual/API workflow is accepted.** If mandatory, engineering needs product/API specifications, mappings and a test environment to implement them. |
| **Email reminders and automatic escalation** | **Yes, if dashboard/manual follow-up is accepted.** Operational failure monitoring still needs an effective process. External notifications remain inactive under the product owner's instruction. |
| **Automated disposal/deletion** | **Yes; keep it disabled.** Retention, preservation and storage responsibilities still need agreement. |
| **Automatic spreadsheet updates and broader import automation** | **Yes, if the existing bounded, create-only import is accepted.** |
| **Additional visual polish** | **Usually yes.** Usability or accessibility problems preventing intended users from completing essential tasks require correction before acceptance. |

## 5. Decisions already provided

These decisions do not need to be requested again:

- Native Windows, PostgreSQL and a TLS reverse proxy.
- Local accounts with TOTP MFA and audited administrator recovery.
- Initial workload: 10 concurrent users, 10,000 contracts and 50,000 document metadata records.
- Initial performance targets: ordinary pages p95 under two seconds and bounded exports under 15 seconds.
- Recovery point objective (RPO) of **24 hours** and recovery time objective (RTO) of **four hours**.
- Provisional operations ownership: Municipal IT Operations / System Administration.
- Provisional sensitive identity-recovery ownership: authorized identity/access or IT Security Administration, with proposed dual authorization for sensitive administrator recovery.
- Continued isolated development, testing, login and development-account recovery without municipal approval gates.

Operational ownership remains provisional pending municipal confirmation. No named individuals are assigned, and a dedicated IAM team is not assumed. External notifications, approval workflows and production MFA-key escrow must not be activated before the production operating model is agreed. Ordinary login and routine application use do not require external approval.

The workload and recovery figures are adopted targets; they do not by themselves establish production acceptance. The hosting decision authorizes preparation, not deployment.

## 6. Most useful next product-owner input

Prepare a short release-one brief containing:

1. Pilot departments, roles and access network.
2. Required workflows and explicitly deferred integrations.
3. Empty register versus legacy-data migration.
4. Roles responsible for validating business rules and participating in acceptance.
5. The proposed hosting arrangement and confirmed operating responsibilities.

Engineering can continue immediately. These decisions are needed to configure and accept the first real-user rollout.

## Source documents

- [Current handoff](../HANDOFF.md)
- [Remediation plan](../REMEDIATION%20PLAN%20PHASES.md)
- [Phase 9 operations](PHASE9_OPERATIONS.md)
- [Phase 10 acceptance](PHASE10_ACCEPTANCE.md)
