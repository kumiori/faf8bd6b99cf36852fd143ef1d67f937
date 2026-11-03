# Commons conceptual architecture — frozen framework V0.1

The authoritative engine enforces distributed decision rules. Central storage
does not confer sole decision authority on its operator.

`commons_engine` owns detached state, mutations, atomic commits, ordered history,
idempotency, deterministic reconstruction, and persistence adapters. Hube retains
its rules as a domain subclass. `commons_game` is another domain subclass, not a
second implementation of history, mutation or SQLite append machinery.

## Domain

Actors are fictional people or organisations with stable identities and declared
roles. Relationships, reported capacities and needs preserve epistemic status and
provenance. Derived matches remain disposable projections. Agreements are
multilateral objects, not weighted actor edges. Each version contains parties,
terms, responsibilities, resources, validity, governance and verification criteria.
Local approval receipts bind actor, version and exact content digest. They are
simulated actor approvals, not cryptographic signatures or production identity.

Acceptances and governance approvals are separate collections. Every party must
accept the same version. Its authorisation policy additionally requires an
explicit eligible electorate, approval threshold, named approvers and/or stakeholder
categories. No approval can transfer to an amendment. Old versions and their
receipts remain inspectable.

A commitment records an accepted responsibility. A commit records a validated
state transformation: ID, initiating action/actor, authorisation decision,
previous/resulting version and state hashes, logical timestamp, and mutations.
Acceptance can produce a commit without establishing fulfilment.

## Invariants

1. Rejected commands change neither state nor history. Multi-record writes are atomic.
2. Exact accepted retries return the original result; changed payloads conflict.
3. Acceptance, institutional authorisation, activation, execution, fulfilment and
   independent verification are separate transitions.
4. Amendments supersede versions and reset current approvals. Active agreements
   require termination before renegotiation in this milestone.
5. Managed reservations summed across agreements never exceed resource capacity.
   Externally reported capacity must be reconciled before engine reservation.
6. Fulfilment requires recorded execution and evidence against every criterion.
   The independent designated verifier alone can establish verified outcomes.
7. Reservations remain held until verification or an explicit releasing transition.
8. Expiry follows recorded world time. Wall-clock timing and animations do not
   alter deterministic simulation. The facilitator may record advancing time.
9. Replay validates mutation chains and Commons state hashes. Hashes detect
   inconsistency; they are not external signatures or tamper-proof notarisation.
10. SQLite command submission reloads, validates, reserves and appends under one
    `BEGIN IMMEDIATE` transaction. A second process cannot reserve stale capacity.
11. Empirical declarations, mathematical inferences and fictional demonstrations
    remain separately labelled. No real Montréal agreement is fabricated.
12. Graphics, music and mechanical metaphors never determine game outcomes.

## Application and modes

Python CLI and a loopback HTTP adapter submit the same structured commands. The
browser holds no authoritative game state. ECOSYSTEM reads actors, reports and
derived possibilities; SCENARIOS operates negotiated agreements; GATHERING has a
separate fictional convening objective, invitations and operational constraints.
All use the same engine and record schema. Mode projection is separate from the
choice of scenario/world.

The first worlds use fictional actors and synthetic resources: a bilateral
research-log access exercise; Montréal → Geneva mentoring; and a commons gathering.
Empirical importing, production authentication, legal enforcement, financial
custody, blockchain, AI delegation and calibrated social mechanics are deferred.
