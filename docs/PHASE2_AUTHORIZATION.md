# Phase 2 — Application authorization and identity administration

Date: 2026-10-21. Scope: P02-T01–P02-T08 in the remediation plan.
Technical defaults are implemented; municipal policy/production approval is not inferred.
Phase 1 evidence remains in PHASE1_BASELINE.md. Current phase state is maintained in HANDOFF.md.

## Adopted capability matrix (P02-T01/T06)

| Principal | Contract read | Contract/task/document write | Review decision | Identity administration |
|---|---|---|---|---|
| Guest, inactive account, department account without active department | Denied | Denied | Denied | Denied |
| Active department user | Own department, including its archived records | Own active contracts, existing CSRF/version rules | Only with explicit capability, active team membership and concrete assignment; existing own-department read authority still required | Denied |
| Existing reviewer | All departments | Denied | Denied by default | Denied |
| Reviewer with `can_approve` | All departments through existing reviewer role | Denied | Only explicitly assigned reviews in an active team containing that user | Denied |
| Active administrator | All departments | Existing administrative authority | Existing administrative authority, audited; archive still denies changes | Allowed, CSRF protected and audited |
| Department-scoped API token | Own active department only | Denied | Denied | Denied |
| Unscoped API token | Existing global read scope | Denied | Denied | Denied |

Capability, membership and assignment are independent conditions. Contact labels, deputy labels,
recipient labels, optional linked contact accounts and team membership never grant contract read authority.
No cross-department read grant or delegation system is introduced. A department approver cannot
be assigned another department's contract. A globally authorized reviewer can be explicitly enabled
and assigned by an administrator. Legacy recipient text remains display/history data; structured
team/user assignment is the decision authority. Existing reviewers are not automatically enabled.

Users required to change a temporary password can access only the password-change/logout flows.
Review decisions serialize with identity changes and archival, so application-driven membership or
capability revocation cannot race a decision using stale authority.
Login verification and session creation hold the same identity lock through one commit. A login
already in flight cannot recreate an authenticated session after a password change revokes sessions.
Form bodies are read before identity/parent locks are acquired.

## Implementation and task mapping

| Task | Implementation |
|---|---|
| P02-T01 | `User.can_approve`, fail-closed role checks, `can_decide_review`, per-review UI controls; no automatic approver migration |
| P02-T02 | `app/authorization.py`: shared `contract_scope`, `contract_query`, `load_contract`, `load_child`; used by lists, metadata, exports, reports, import duplicate detection, history parents, child routes, API and review inbox |
| P02-T03 | Private stored types/people retain authorized department scope. Metadata includes authorized archived records for historical filtering; archival never broadens access. Fixed shared reference options remain deliberately shared. |
| P02-T04 | Audited admin create/rename/suspend/reactivate for departments; stable IDs and no delete route. Suspension deletes department-user sessions. Scoped tokens are dynamically suspended; reactivation restores only still-active/unexpired tokens, never deleted user sessions. |
| P02-T05 | Maintained, scoped contact catalog with stable IDs, active flag and optional user FK; active entries populate forms. Contract names remain display snapshots. Inactive known contacts cannot be newly selected; unchanged historical labels can survive unrelated edits. |
| P02-T06 | Recipient teams, memberships, admin review assign/reassign/clear, and `/reviews` decision inbox. Parent authorization and membership/capability checks remain server-side. |
| P02-T07 | `/account/password`: old-password challenge, CSRF, shared 12–256 character policy, confirmation, different new password, rate limiting, all-session revocation, fresh session/CSRF rotation and safe audit. Admin/CLI temporary passwords force change on first use. |
| P02-T08 | Shared `identity_service` validation and mutation service used by CLI/web. Stable user IDs and immutable usernames, active department consistency, serialized last-admin protection, session revocation on permission/membership/reset changes. CLI engine disposal now runs even on errors. |

Identity events contain stable actor/target IDs, principal type, timestamp, action and safe changes.
Password values/hashes and session tokens are never included. Identity audit is application-managed;
database-enforced append-only privileges belong to Phase 3.

### Administration workflow

1. Open **Benutzerverwaltung**, create/edit a user, and explicitly enable **Freigabefähigkeit** only when intended.
2. Under **Fachbereiche & Identitäten**, create an active recipient team and add that account.
3. The account must sign in again after permission/membership changes. A new/reset password must first be replaced.
4. Open the authorized contract, create its review, then use **Prüfung zuweisen** to select the team and account.
5. The assigned user finds eligible reviews under **Prüfungen**. Archived contracts, inactive teams/accounts/departments and missing capability/membership deny decisions.
6. An administrator can reassign or clear both assignment fields. Membership removal and suspension immediately invalidate the decision conditions.

Only administrators maintain catalogs or identities. Global contacts must be deliberately created
as shared entries; a private contact's scope cannot be changed to global. Contact rename/deactivation
does not rewrite historical contract display values. No emails, password notifications, delegation
or new external identity provider is implied.

## Migration and compatibility

New forward migration: `0014_identity_authorization`, following unchanged `0013_integration_tokens`.

- Adds `users.can_approve = false` and `must_change_password = false` for existing users. Only subsequent provisioning/reset forces a password change.
- Adds identity audit/serialization tables, contact identities, recipient teams/memberships and nullable review team/assignee foreign keys.
- Backfills each distinct nonblank `(department_id, responsible/deputy display name)` into a **department-private** contact identity. It does not publish private historical names as global reference data.
- Preserves contract/user IDs, display strings, reviews, history, documents and existing passwords. Legacy reviews remain unassigned. No approvals or memberships are fabricated.
- New user writes require an active department for an active department account; admin/reviewer writes require no department membership. Legacy optional organizational associations are preserved by migration and must be explicitly cleared during subsequent administration; no silent rewrite is performed. Broader legacy constraint inventory remains Phase 3.
- No existing business database was migrated in this session. `init-db` must be run for an explicitly selected application database only after the established backup/maintenance procedure. Deployment remains separate from test verification.

Recovery is forward repair or a verified compatible backup. The migration deliberately refuses
automatic downgrade before deleting any identity/assignment/audit data. Do not roll back to the old
broad reviewer-decision behavior. If remediation is needed, keep decisions disabled/read-only until
the corrected application/schema pair is restored. Production backup/restore is not verified here.

## Verification

The existing CI workflow runs
the complete test collection on SQLite, PostgreSQL 18 and native Linux PostgreSQL. The explicit
PostgreSQL-only lifecycle check still cannot fall back to SQLite.

Implementation source: `9fde6c09546f93df75195b9096a19a4173900eee` on `main`.

| Verification | Collected | Passed | Failures/errors | Skips | Xfails | Additional subtests |
|---|---:|---:|---:|---:|---:|---:|
| Full SQLite | 66 | 65 | 0 | 1 PostgreSQL-only | 0 | 15 passed |
| Full native Windows PostgreSQL 18.3 | 66 | 66 | 0 | 0 | 0 | 15 passed |
| Final targeted `tests/test_phase2.py --database postgresql` | 21 | 21 | 0 | 0 | 0 | 0 |
| Explicit PostgreSQL clean lifecycle/migration/cleanup | 1 | 1 | 0 | 0 | 0 | 0 |

The full PostgreSQL run took 125.97s, SQLite 62.69s, final targeted run 60.71s and
explicit lifecycle check 2.64s. Full runs cover the original application/security regressions
as well as Phase 2. The final targeted run additionally verifies malformed file submissions are
rejected by the non-upload identity forms. JUnit's full-suite `tests=81` includes the 15 subtests.
Clean/populated upgrades and repeated head migration passed on both databases; the new populated
0013→0014 fixture verifies private contact backfill, unchanged labels, false approval flags and
unassigned legacy reviews. Concurrent last-admin writers leave exactly one active administrator.

[Hosted run 39594698525](https://github.com/mignoncharly/kaemmerei/actions/runs/39594698525)
completed successfully for the exact implementation SHA: **sqlite**, **postgresql** and
**native-postgresql** all passed. GitHub API run/job/step and artifact metadata was inspected;
the existing full-suite commands collected Phase 2 tests and migrated to 0014. The PostgreSQL
jobs also ran the explicitly selected PostgreSQL lifecycle check. Artifact contents were not downloaded,
so hosted warning counts are not inferred from the local XML files.

Evidence: [local results and JUnit hashes](evidence/phase2-local.json),
[hosted run/job/step metadata](evidence/phase2-ci-39594698525.json). The local ignored XML files are
`.verification/phase2-sqlite-full.xml`, `phase2-postgresql-full.xml`,
`phase2-postgresql-targeted.xml` and `phase2-postgresql-explicit.xml` in that directory.
The final catalog check found zero harness databases remaining. Native cluster directories,
private passfiles, default postgres schemas and unrelated services were not deleted or reconfigured.

Remaining local warnings are unchanged: Starlette's deprecated AnyIO alias and the managed Windows
pytest cache ACL warning. Neither was suppressed. Native startup's prior operator-confirmed success
and the agent ACL limitation remain as documented in Phase 1; this phase did not attempt reinitialization.

**Technical Phase 2 gate: verified.** Municipal acceptance of D01/D02 and production release remain open.

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
$python = 'C:\kämmerei\.venv\Scripts\python.exe'
& .\scripts\Start-TestDatabase.ps1 -Python $python
& $python -m pytest -q -ra
& $python -m pytest -q -ra --database postgresql
& $python -m pytest -q -ra --database postgresql tests/test_phase2.py
& $python -m pytest -vv -ra --database postgresql tests/test_postgresql_integration.py
```

### Investigation history

- An initial targeted PostgreSQL run passed 16 checks and failed one UI assertion: PowerShell pipeline insertion had replaced new German characters with `?`. The template/CLI strings were corrected using UTF-8-preserving edits; the assertion was retained.
- A subsequent SQLite full run passed all 61 test bodies but failed CLI-fixture cleanup: the CLI's engine was not disposed on `SystemExit`. A `finally` now disposes it on every exit, and the CLI regression passes.
- A PostgreSQL run passed 62 test bodies but failed one DROP cleanup because WITH FORCE lacked permission to terminate a connected process. Its exact transient backend was not observed afterward; a background connection is a possibility, not an established diagnosis. The harness now performs guarded ordinary DROP after owners close engines, without granting signal privileges or terminating sessions. The exact failed-test database was positively checked against its owner/comment and synthetic fixture, then removed normally.

PostgreSQL documents the permission limits of FORCE and its connection termination behavior in
[PostgreSQL 18 DROP DATABASE](https://www.postgresql.org/docs/18/sql-dropdatabase.html).
The dedicated test role retains its existing restricted attributes; OID/owner/comment cleanup guards remain intact.
The initial implementation (3b2c2e6) also passed [run 39593686567](https://github.com/mignoncharly/kaemmerei/actions/runs/39593686567).
Final transaction review added the login/password-change race regression and removed lock acquisition
before review form parsing; the final 9fde6c0 run above verifies those additional corrections.

## Boundaries and next phase

Phase 3 database RLS, constrained schemas, restricted production roles and database-protected audit
remain unimplemented. Phase 4 still owns content/version-bound approvals, separation-of-duty policy,
complete aggregate mutation/version semantics and tax workflow. This phase does not claim those guarantees.
MFA/SSO and host recovery remain Phase 9. D01/D02 defaults are technical choices, pending municipal
owner acceptance; no delegation policy is approved or implemented. Production approval remains open.
