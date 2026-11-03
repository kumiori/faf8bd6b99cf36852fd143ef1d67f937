# Upgrade plan and migration boundary

This is the original implementation sequence. The later [M0–M5 roadmap](MILESTONES.md)
now governs milestone order and acceptance; work described here is not necessarily
complete merely because its scaffold exists.

1. Establish Hube's 58-test baseline and source hashes; retain the supplied frozen
   specification verbatim in `COMMONS_SPEC_V0.1.txt`.
2. Extract Hube's mutation, history, replay and append-only storage into
   `commons_engine`. Keep Hube's domain methods and public API. Add a source-checkout
   bridge plus a declared installation dependency; no saved-world migration.
3. Add typed Commons records, strict command validation, immutable agreement
   versions, actor/version/content-bound approvals and inspectable governance.
4. Add commitments, execution, evidence, independent verification, reservations,
   expiry, lifecycle transitions and explicit commit metadata.
5. Add a SQLite command transaction for concurrency guarantees at the authoritative
   storage boundary; preserve legacy `save_log` compatibility.
6. Define synthetic bilateral, mentoring and gathering worlds. Add CLI demonstration,
   projections, complementarity/missingness analysis and a loopback web adapter.
7. Add the declaration splash, psychedelic procedural visual, generated MIDI score,
   browser synthesiser and a real engine-backed play surface.
8. Validate all required domain failures, real competing SQLite submissions,
   deterministic replay, HTTP interaction, browser behaviour and Hube compatibility.

The only Hube edits are the extraction seams, shared-record/storage imports,
checkout bridge and package dependency. Legacy domain state is deliberately not
converted into Commons agreements: its semantics and ending remain unchanged.
