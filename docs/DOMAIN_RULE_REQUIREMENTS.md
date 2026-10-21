# Written domain decisions → versioned, testable rules

State: pending clarification, U022. No accounting, statutory deadline or records
rule has been adopted. The existing recorded-value inventory and calendar
arithmetic are technical aids. The UI, HTTP header and API v2 payload mark the
pending status. Saved manual values and task dates remain available. No new
derived authoritative field, automated disposal or statutory assumption is added.

Decision packets:

- [Finance v1](rules/finance-v1.json): amount meanings, population/status/as-of
  treatment, direction, zero/unknown, net/gross, rounding and corrections.
- [Deadlines v1](rules/deadlines-v1.json): contractual sources, receipt/dispatch,
  renewal anchors, leap/month-end cases, timezone/calendars and manual confirmation.
- [Records v1](rules/records-v1.json): permitted data, classification, access/export,
  separate lifecycle rules for documents, predecessors, history, logs, events,
  snapshots and backups, preservation/holds and disposal authority.

Each has a stable domain/version, explicit supersession, decision state, written
approval provenance, questions and stable case IDs. Synthetic case inputs are
provided; **expected results and evidence remain null**. They are prompts for the
responsible roles, not proposed legal/accounting answers. `app.rule_requirements`
validates the contract; tests reject invented pending answers, duplicate case IDs,
invalid supersession and adoption without written expected results/evidence.
Validation never makes a packet executable or grants a release approval.

When the written answers arrive:

1. Preserve v1; create the next immutable version, linking its predecessor.
2. Record responsible role, date and source reference. Store the actual source in
   the authorized records location; put only its non-secret reference here.
3. Convert each answer into named input/output examples, including null/zero,
   mixed bases, transfers/archives, leap/month-end boundaries and conflicting
   contractual clauses. Record rationale/evidence for each expected result.
4. Resolve contradictions explicitly; an incomplete packet stays pending.
5. Implement a separately reviewed deterministic rule for that version. Use
   decimal monetary units, explicit dates/timezones and named source fields.
   Do not execute arbitrary expressions supplied in configuration.
6. Persist provenance for any future confirmed/derived result: rule domain/version,
   input snapshot/digest, evaluation time, source reference, reviewer and manual
   override reason. Material edits invalidate confirmation. Preserve earlier
   outputs and re-evaluate explicitly; do not rewrite history silently.
7. Replay approved examples as regression tests and compare the recorded-value
   baseline. Verify HTML, XLSX, API, dashboard and history agree on version/status.
   Obtain domain acceptance separately from technical test passage.

Until then: no approved-rule engine or authority switch exists. Do not infer
payment flow from annual_value, convert net/gross, extrapolate fiscal commitments,
roll a missed notice into a lawful next date, apply holiday rules or dispose of
preserved data. A manual task date records a user's instruction; it is not a
machine-confirmed legal deadline. Finance/deadline clarification is not permission
to enable disposal; that requires its own policy, confirmation and verified path.
