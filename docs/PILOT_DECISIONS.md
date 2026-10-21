# Pilot decision record — U022, 21 October 2026

Authority: product-owner instructions in the current work session. These replace
the corresponding unanswered product questions in earlier handoffs. They do not
constitute municipal real-data or production authorization.

| Status | Current meaning |
|---|---|
| Development | Authorized; implementation and isolated synthetic verification continue. Current-source evidence is recorded in HANDOFF U022. |
| Synthetic technical pilot readiness | Scope approved; engineering verification in progress. Empty register, synthetic contracts only. No observed departmental acceptance or hosted environment acceptance yet. |
| Real-data pilot authorization | Not granted. Requires confirmed hosting/internal access, business/data-handling acceptance and municipal authorization appropriate to the pilot. |
| Broader production approval | Not granted. Independent security review and formal municipal production authorization are separate release gates. |

Approved scope: Kämmerei plus **one Fachbereich, still to be selected**; internal
network/VPN access; individual local accounts and TOTP MFA. Begin empty, without
legacy migration. Fixtures are created only in positively identified disposable
test databases; they are never a seed for the real register.

The [existing permission matrix](PHASE2_AUTHORIZATION.md) is the approved
**provisional technical baseline**. Configure active department membership,
account role, explicit `can_approve`, recipient teams/memberships, individual
review assignment, mandatory review recipients and scoped/expiring API profiles
through the existing audited controls and settings. Assignment never expands read
scope. The three base roles and their PostgreSQL policies are a versioned security
boundary: a future matrix change requires coordinated application/RLS changes and
permission regressions, not a bypass switch. Do not turn the provisional matrix
into an irreversible business policy.

Judith receives **no new permissions** under this decision. Possible later
business authority is separate from application account administration, database
schema ownership, Windows administrator access and encryption/recovery-key custody.
No account or infrastructure grant was made during this work.

Written Kämmerei clarification is pending for finance and deadlines. Records/data
handling also requires relevant municipal confirmation. Preserve manual fields
and manually dated tasks; no tax, accounting, statutory calendar or retention
interpretation is inferred. See [versioned requirements](DOMAIN_RULE_REQUIREMENTS.md).
Automatic disposal stays disabled for records/documents/history/backups. Existing
expired authentication housekeeping is an operational security control, not a
business-retention policy. No event/snapshot retention deletion is enabled.

Keep provisional Municipal IT Operations/System Administration responsibility;
sensitive identity/recovery custody remains provisionally with authorized
identity/access or IT Security Administration, including the earlier proposed
dual authorization. No external notifications, production recovery escrow or
external approval workflow is activated. Ordinary development/login/recovery
remains available under the existing local procedures.

Acceptance participants: a responsible Kämmerei representative, selected Kämmerei
test users, and the product owner/software engineer/project IT operator. Record
their actual results in [Phase 10 acceptance](PHASE10_ACCEPTANCE.md). Their
participation does not replace an independent security review or municipal release
authorization. No participant sign-off is recorded by this decision document.

Hosting: the existing STRATO account serves a separate website. Its exact product
is unverified; the agreed Windows/PostgreSQL architecture remains. The
[read-only hosting investigation](HOSTING_ASSESSMENT.md) makes no account entitlement,
deployment, DNS or website change. No credentials are requested.
