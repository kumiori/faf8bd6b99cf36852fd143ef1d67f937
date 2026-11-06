# Persistence and replay

The store exposes a detached committed snapshot and atomic submission. The
in-memory reference serialises submissions under a lock. The SQLite adapter
reloads the latest log under `BEGIN IMMEDIATE`, evaluates the command, appends
the accepted event and commits once. Exact retries resolve against the stored
command. A failed transaction rolls back and may be retried with the same ID.

Navigation, inspection, filtering, drafting outside shared state and replay can
operate on detached snapshots. Publishing invitations, proposals, acceptances,
approvals or evidence goes through authoritative submission.

## Portable history

`game-gamer/history/v1` carries `schema`, `scope_id`, ordered `events`,
`history_digest` and nullable `fork`. Restore verifies the digest, genesis
scope and schema, mutation schema, and each transition and its authorisation
against the preceding state. SHA-256 digests check consistency. A host
establishes the trustworthiness of its imported history independently.

A fork carries its `id`, parent `revision` and parent `prefix_digest`.
`Collective.fork` creates an in-memory counterfactual with distinct scope and
recorded counterfactual authority for new actions. Replaying an authoritative
prefix simply reconstructs its accepted history. No operation promotes a fork
to the parent. Nested forks and future schemas fail explicitly.

Existing hosts retain their native SQLite event encodings and replay paths. Their compatibility entry points remain with the host. A legacy save
opens in its original application without a portable history conversion.
