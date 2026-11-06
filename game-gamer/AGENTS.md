# Game-Gamer development

The earlier transaction runtime and the Saddle Pathways application provided
the mechanics for this package. The goal is portable collective
decision-making across hosts.

- Keep one authoritative event history per world. Ecosystem, Gathering and
  Scenarios read and act on that history.
- Preserve actor authority, scope and expected world and agreement revisions.
  Exact retries must resolve idempotently inside the commit boundary.
- Keep declarations, inferred matches, proposed contact, acknowledged
  relationships, party acceptance, policy approval and verified outcomes
  distinct. Preserve the originating event and applicable agreement version.
- Produce detached, deterministic read models. Keep reusable terminal presentation in the optional TUI. Host web surfaces,
  identity providers, questionnaire semantics and Montréal data belong to the host.
- Treat historical replay and counterfactual branches as distinct. All
  authority in the current public schema is simulated.
- Validate portable data and reject unsupported schema versions explicitly.
  Preserve legacy event ordering and shape for compatibility consumers.

Run `python -m pytest` in this directory with the test and tui extras installed. Run the
host's golden trajectories when editing legacy-compatible semantics.
