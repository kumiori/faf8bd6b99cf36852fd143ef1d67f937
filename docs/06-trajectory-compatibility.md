# Trajectory compatibility contract — subtle-trajectory/v1

Assessment written before integration. See `05-trajectory-audit.md` for source
evidence. The target is committed `trajectory-engine 0.2.0`, repository
`https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18`, commit
`757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`. The standalone local checkout has
unrelated uncommitted extensions; they are not this integration's dependency.

## Smallest compatible boundary

Use the package's real `build_trajectory_document`, `normalise_trajectory_document`,
`trajectory_yaml` and `load_trajectory_yaml` public APIs. Place a versioned Commons
projection envelope at **`plan.commons_trajectory`**. Its normaliser preserves
unknown nested plan fields, but drops unknown top-level fields and forces the
outer plan's `source_kind` to `plan`. Consequently epistemic status belongs inside
the envelope, not in the package's outer plan label.

Native primitive geometry requires normalised time plus energy/influence defaults.
There is no source-supported generic arbitrary-state/event representation. Leave
`primitives` and `uncertainty` empty. Do not invent numbers, use geometry to encode
agreement statuses, manufacture uncertainty strengths, or call `realize_primitive`
to equate an accepted contract or a verified outcome with native `Done`.

This is a native package document with a documented extension, not a claim that
the package natively understands Commons contracts. Geometry/physical analysis is
explicitly unavailable until meaningful quantities are independently authored.
No trajectory-package algorithm or serializer is copied into Commons.

## Mapping

| Commons concept | Representation |
|---|---|
| World at transaction n | Detached projection reconstructed from the event prefix by `CommonsGame.from_log`; state hash and summary are derived |
| Atomic transition | Complete original event including all mutations, initiating command, actor, commit and authorisation |
| Ordered trajectory | Original ordered `events`; sequence and identities preserved, not normalised into coordinates |
| Contract lifecycle | Agreement/version/approval/evidence mutations retained exactly; terminal labels are derived from those records |
| Provenance | Original record provenance plus explicit envelope `world_kind` and history-kind labels |
| Simulation | Fictional fixture remains labelled synthetic; verified-in-simulation never means empirically verified |
| External inputs | Recorded commands such as `advance_time`, plus any future explicitly recorded external-input fields, remain intact |
| Alternative branch | Named hypothetical suffix from an explicit parent sequence, commit and state hash; source prefix is shared by reference |
| Rejected branch action | Rejection reason and attempted command retained in branch diagnostics; it creates no canonical event |
| Serialisation | Native `trajectory-plan/v2` YAML containing `subtle-trajectory/v1` envelope; package version and source commit recorded |

Keep K's meaning explicit: the accepted model uses K for commitments. Commits are
transaction/audit records. The new task's use of K for commits does not silently
redefine the frozen conceptual tuple. Both remain representable and distinct.

## Authority and reconstruction

```
Commons commands → authoritative engine → append-only event history
                                           ├─ Commons replay/state query
                                           └─ read-only trajectory adapter
                                                └─ trajectory-engine document/YAML
                                                     └─ terminal inspection/export
```

Only Commons validates actions and state reconstruction. Loading a trajectory is
inspection, not permission to replace a saved world. The adapter has no save or
commit method and never calls the authoritative store's submit operation.

Projection validity is checked with Commons replay, sequence/before-image checks
and existing commit hashes. Package normalization alone is insufficient to certify
a game history. Derived frame summaries are recomputed, not trusted on import.

## Branches

A branch begins from `events[:parent_sequence]` reconstructed in a detached engine.
The same Commons validation resolves explicitly supplied hypothetical commands.
Accepted suffix events are retained; rejected attempts are labelled diagnostics.
No branch changes the original game, its SQLite file or its historical prefix.
Branch-local event IDs may repeat IDs on another path; identity is qualified by
the branch ID. A branch never claims historical authority merely by being viable.

The package has native authored two-way branch labels, not a generic arbitrary
game-event tree. The envelope preserves arbitrary branch lineage without lossy
conversion to that geometric construct. Independent actors' authored plans are
not merged or mislabelled as this system-generated collective history projection.

## Compatibility acceptance

Test exact nested equality after native YAML round-trip, complete Commons replay,
contract creation/acceptance/execution/verification distinction, source ordering
and provenance, detached alternative branches and rejected attempts, fixed actor
sessions, and original Hube regressions. Optional trajectory dependency imports
must not prevent Hube's standard-library engine from loading.
