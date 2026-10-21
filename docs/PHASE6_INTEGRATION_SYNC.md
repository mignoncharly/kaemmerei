# Phase 6 — Reliable integration synchronization

Date: 2026-10-21. P06-T01–T08; R05/R36/R41. Forward migration
`0019_integration_sync`. Existing application, v1 API and Phase 1–5 protections
are retained. Synthetic test databases only; no business deployment. D07 scope,
ownership and retention policy require municipal integration/security acceptance.

## Compatibility and transition

API v1 stays available with its existing fields, offset pagination, filters,
document routes and legacy token profile. Child-only updates now advance the
parent timestamp. v1 remains an approximate inventory API: offset/timestamp
pagination does not guarantee a complete change stream or scope removals.
No sunset date or existing client conversion is invented. Inventory consumers,
assign owners, agree a transition window under D07 and verify each consumer before
any future v1 retirement. Responses link to the successor snapshot endpoint.

Existing tokens migrate to `legacy_v1`, with unknown service/account owner left
NULL. Their historical creator is retained and is not silently declared their
accountable owner. Creator deactivation alone preserves the old ownerless-token
behavior; department deactivation, expiry and revocation still deny access.
Legacy tokens gain no v2 capability. Newly issued tokens bind an active accountable
account and named service; account deactivation/inactive department membership
suspends them. Owner/department changes increment the grant version.

New v2 tokens cannot use v1 to bypass their narrower capabilities. Existing v1
creation requests omitting new fields retain their v1 profile, with the creating
administrator as accountable owner and the submitted application name as service
label. The new admin form defaults to explicit v2 rights and finite expiry.

## API v2 contract

All API requests require `Authorization: Bearer <token>` over the approved TLS
ingress. Tokens are never query parameters. All API responses are private/no-store.
UTC timestamps end in `Z`; monetary values are recorded decimal strings or NULL,
not actual payments, inferred tax basis or historical finance calculations.
IDs are stable database identifiers. Fields absent for missing capabilities are
not NULL placeholders. The machine-readable response contract is
[`app/static/api-v2.schema.json`](../app/static/api-v2.schema.json), served as
`/static/api-v2.schema.json`. Existing interactive OpenAPI exposure stays disabled.

| Endpoint | Required capability | Response |
|---|---|---|
| GET `/api/v2/snapshot?limit=100` | metadata + accountable owner/finite expiry | Materialized authorized inventory, next_cursor or final changes_cursor, snapshot expiry |
| GET `/api/v2/snapshot?cursor=...&limit=100` | Same grant and token as initial request | Next fixed snapshot page; current authorization rechecked |
| GET `/api/v2/changes?cursor=...&limit=100` | metadata | At-least-once upsert/remove notifications, next_cursor and has_more |
| GET `/api/v2/contracts/{id}` | metadata | Current authorized aggregate with granted sections |
| GET `/api/v2/contracts/{id}/history?after_id=0&limit=100` | history | Authorized revisions, seek pagination by revision ID |
| GET `/api/v2/contracts/{id}/documents/{document_id}` | document_content | Phase 5 verified, scoped attachment/range response |

Limits are 1–500; invalid numeric limits return 400, malformed typed query values
or missing required query parameters use FastAPI 422. Invalid/tampered/wrong-token
or wrong-endpoint cursors return 400. Expired cursors, changed grant fingerprints
or retired replay positions return **410 `resnapshot_required`**. Missing/expired/
revoked/suspended credentials return 401; missing capabilities or unadopted v2
ownership return 403; unauthorized or missing contracts/parent-child references
return 404. Unavailable/corrupt document bytes remain 409. Explicit capacity bounds
return 413, never a successful truncated snapshot.

### Capabilities

| Capability | Included fields/authority |
|---|---|
| metadata | ID/number/designation/type/partner/status, department ID, contact/deputy labels, relevant/end/notice/renewal dates, version/content revision, updated/archive times |
| finance | Recorded annual/contract value, financial direction, payment interval and budget assignment |
| documents | Authorized document metadata/state/hash/size, predecessor/hold, validated DMS URL; no bytes automatically |
| document_content | Verified byte downloads; requires documents when granting rights |
| tax | Current tax status/result/reviewer/time/provenance |
| tasks | Task ID/title/kind/status/due date/assignee/version |
| history | Review state/assignment/result, immutable decision provenance and paginated revision before/after contents; explicitly sensitive historical finance/tax/personal content can be included |

`metadata` is mandatory for a v2 profile. Additional rights require explicit
administrator selection. `legacy_v1` is a separate broad compatibility profile,
not a wildcard for v2. No H&H, LDAP, product-specific DMS, external notification or
remote-write connector is implied. D07 must approve the exact consumer profile,
especially history and document contents, before distributing production tokens.

### Consumer algorithm and example shapes

1. Request a new snapshot, store its pages in a separate local staging inventory.
2. Follow `next_cursor` until NULL. Pages contain captured payloads at the initial
   boundary; a row no longer authorized at delivery is omitted. Do not finish from
   an empty page alone. Only the last page returns `changes_cursor`.
3. Atomically install the staged inventory and persist `changes_cursor`. This is
   a replacement of the old scoped cache, not an append-only import.
4. Poll changes. Process all events before atomically persisting `next_cursor`.
   Upserts mean fetch the current `resource_url`; overwrite by contract ID. A 404
   during that fetch means purge the cached contract and its children.
5. A remove means purge that ID and its locally owned child copies. It contains
   only event_id, contract_id, operation and reason. It never contains the new
   department, private payload, document name or destination URL.
6. Continue while `has_more`; poll again later otherwise. A notification can repeat
   or refer to state already included in an earlier fetch. Deduplicate by event_id
   when useful; ID-based upsert/removal must remain idempotent. Persist cursors
   across process restarts, never reconstruct them from time/sequence/offset.
7. On 410 discard the old cursor and scoped cache and perform an explicit new
   snapshot. On 401/403 stop and remove/quarantine the previously authorized cache
   according to the consumer's approved privacy policy; an unusable token cannot
   receive removal events. Do not continue polling with revoked credentials.
   A saved cursor unknown after restore (400) requires operator-confirmed fresh
   synchronization; never silently resume at the current head.

```json
{"api_version":2,"data":[],"next_cursor":null,"changes_cursor":"OPAQUE","snapshot_expires_at":"2026-10-22T12:00:00Z"}
```

```json
{"api_version":2,"data":[{"event_id":"EVENT","contract_id":42,"operation":"upsert","resource_url":"/api/v2/contracts/42","category":"document"}],"next_cursor":"OPAQUE","has_more":false}
```

```json
{"event_id":"EVENT","contract_id":42,"operation":"remove","reason":"no_longer_authorized"}
```

Relative resource URLs use the same configured application origin. Never follow
an event to an unrelated host. Event order is publication order; this is a state
synchronization feed, not a claim of exact commit timestamps or a historical
business-event payload for every intermediate state. Replays recheck current
authority and can conservatively become removals. Equal timestamps are harmless.

## Publication, snapshot and security design

Database triggers capture changes in the source transaction into `sync_outbox`,
including old/new department scope. Contract, document lifecycle/link/hold,
task, review, decision and revision changes are covered. Child changes touch the
mutable parent updated_at and emit their category. Archived parents are not
rewritten for archival revision inserts; existing archive barriers remain intact.

PostgreSQL aggregate writer triggers acquire a common `sync_state` row lock.
The v2 publication function takes the same lock, sees committed unpublished
entries, assigns external sequence positions and marks each outbox row in the
same transaction. Source outbox IDs are never used as a high-water mark. A late
commit with a lower allocated ID still gets a fresh published position. A rolled
back publication leaves both position and published marker unchanged. Concurrent
publishers serialize, preserving unique event IDs and idempotent publication.

Under this barrier the initial snapshot captures authorized payloads and the
published boundary, then commits stored rows and initial cursor together. Writers
resume after that short transaction. Pagination uses immutable stored rows rather
than offset reads of changing contracts. Permissions are refreshed after waiting
for the barrier; grant/owner/department writers also meet the barrier so a changed
GUC scope cannot create a successful incomplete snapshot. Ordinary v2 detail reads
retain the existing per-request/transaction authorization boundary.

PostgreSQL functions that perform publication remain VOLATILE (the default), so
their internal queries take fresh snapshots after lock waits. Application
connections use READ COMMITTED. SQLite serializes its writes instead and claims
no database RLS. The single barrier deliberately trades throughput for a clear
pilot consistency boundary; production load/lock-duration measurements remain
Phase 9. Direct writes outside the documented aggregate protocol can encounter
database deadlock rejection; retry the complete transaction, never disable locks.

Opaque 256-bit cursor values are stored only as hashes, bound to token ID, API v2,
endpoint mode, scope/capabilities, accountable owner, grant version, boundary and
expiry. No per-process signing key is required. Cursors survive application
restarts, but never transfer across overlapping replacement tokens. PostgreSQL
has forced RLS on all five new tables (14 protected aggregate/audit/sync tables in
startup checks). Web/integration roles cannot select or write raw outbox/state/
event rows. A narrow definer function returns redacted visible events; integration
can insert/read only its own cursor/snapshot rows. Definer paths are fixed and
PUBLIC execute revoked. Existing shared-role/GUC SQL-compromise boundaries from
Phase 3 remain: API capabilities are not a defense against arbitrary execution
with the application's database credentials.

## Tokens, usage and retention

Admin creation, scope/owner changes, rotation and revocation are audited without
secret/hash/URL values. Mutation authority is revalidated under the existing
identity guard. Revocation stores time and classified reason. Rotation creates a
new separately hashed secret once, preserves profile/department/owner and records
the predecessor. It does not revoke the old token automatically: move the consumer
to a fresh snapshot with the new token, verify synchronization, then explicitly
revoke the predecessor. New rotated token lifetime is 90 days. Adoption of an old
ownerless token during rotation is explicitly shown in the admin UI.

Usage timestamps no longer commit before business reads. Successful responses
schedule a separate best-effort update after response handling, throttled to once
per five minutes/token/process plus a database age predicate. Failures increment
`app.state.integration_usage_failures` without changing the completed business
response or logging credentials. This is approximate telemetry, not immutable
evidence that a client processed a transfer. Phase 9 owns metric export/alerts.

Cursor access expires after 24 hours; active change consumers renew the cursor
expiry on each successful page. Snapshot expiry remains fixed at creation.
Feed/outbox/cursor/snapshot rows are **not automatically deleted** while D06/D07
retention decisions remain pending. Expiry prevents API use, not physical erasure.
Stored snapshots contain scoped business payloads and must be included in the
privacy/backup inventory. Any future operator retirement must hold the barrier,
advance the persisted replay floor monotonically, retire matching feed rows and
respect snapshot boundaries/holds. Requests below that floor return 410; the
regression tests simulate this with synthetic owner-authorized state only.

Pilot bounds: 5000 contracts per snapshot; 1000 rows per expanded child collection.
Exceeding either fails with 413 rather than omitting records. Use department tokens
or fewer expansions; large-scale paginated expansion is Phase 9 capacity work.
Initial materialization/publication can hold the writer barrier while creating
these rows. Monitor pending outbox, published/state counts, snapshot growth, cursor
expiry, lock waits and usage-update failure count before enabling production.

## Migration, recovery and operator verification

0019 adds token ownership/capabilities/grant version/revocation/rotation fields,
five synchronization tables and capture/security functions/triggers. No existing
token gains new API rights; unknown owners remain unknown. No existing applied
migration is edited. Clean/populated/repeated migration tests cover forward
upgrade; a destructive downgrade is refused. Reapply reviewed role provisioning
for new grants and startup checks. No business database or production roles have
been changed here.

Back up database, feed/cursors/snapshots and private document storage consistently
as described in Phase 5. Never reset sequence state or source publication markers
to repair a consumer. Restore into an identified isolated database first; verify
hashes, scope, feed replay and full snapshot replacement. A point-in-time restore
may invalidate external saved cursors or rewind already consumed events: stop
consumers and require fresh snapshots after a restore/cutover. Do not merge an old
database's feed positions into a newer consumer cache.

```powershell
Set-Location 'C:\kämmerei\OPEN_HERZ_Vertragsregister_Phase'
& .\scripts\Start-TestDatabase.ps1 -Python 'C:\kämmerei\.venv\Scripts\python.exe'
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database sqlite
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -ra tests/test_phase6.py --database postgresql
& 'C:\kämmerei\.venv\Scripts\python.exe' -m pytest -q -m postgresql --database postgresql
# Separate, explicitly configured privileged operator process only:
& 'C:\kämmerei\.venv\Scripts\python.exe' -m app.cli integration-status
```

The read-only status command reports counts, current boundary/floor and unknown
legacy-owner count, never credentials or business values. Native cluster/passfiles/
identity guards remain untouched; Docker is not introduced as a local dependency.
Final actual verification and CI evidence will be appended after execution.

### Primary design references

- [PostgreSQL 18 transaction visibility and nontransactional sequences](https://www.postgresql.org/docs/18/transaction-iso.html)
- [PostgreSQL 18 explicit transaction-held locking](https://www.postgresql.org/docs/18/explicit-locking.html)
- [PostgreSQL 18 VOLATILE function snapshots](https://www.postgresql.org/docs/18/xfunc-volatility.html)

The barrier/outbox/snapshot design above is this application's implementation;
the cited database behavior supports its assumptions, not a vendor certification.
