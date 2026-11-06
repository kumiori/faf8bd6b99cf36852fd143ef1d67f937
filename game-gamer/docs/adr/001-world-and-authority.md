# 001 · One authoritative world with scoped actions

**Decision.** The package owns the world and accepted state transitions.
Ecosystem, Gathering and Scenarios consume neutral projections of the same
history and submit to the same store. The store compares the world revision
and commits the entire accepted action atomically. The engine also compares
the exact agreement version. Simulation and counterfactual authority are explicit.

Separate mode runtimes would require reconciling competing histories and
duplicate authority checks. A local-save-at-finalisation design would let
different actors accept incompatible terms or reserve the same resource.
Embedding the existing terminal, Notion importer or trajectory transport
would tie the semantic model to one host's interface and dependencies.

**Compatibility.** Retain legacy host records in the host adapter.
Expose a scoped public envelope and versioned portable schemas for new
consumers. The host adds application-specific matching and labels to the
shared graph. Verify the migration against frozen history and projection
fingerprints.
