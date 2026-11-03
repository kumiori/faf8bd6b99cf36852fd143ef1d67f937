# Existing engine audit — 2 November 2026

Baseline: sibling `../game_hube`; inspected before implementation. Its project
root is not a Git checkout. The nested arcade experiment has its own repository.
`hube-baseline.json` records source/test/fixture hashes before the upgrade.

## Actual architecture

* `game/model.py`: schema 0.1 dataclasses, typed relation signatures, stable IDs.
* `game/engine.py:13`: `Game` owns detached dictionary state and an ordered log.
  `validate` checks a structured `{key, kind, actor, ...}` command against a
  private candidate world. `submit` commits the complete mutation set.
* `game/engine.py:25`: `_commit` records before/after images, provenance and a
  deterministic logical timestamp. One transaction can affect several records.
* `game/engine.py:422`: exact resource/unit/location/availability matching;
  proposed allocations reserve capacity; verified allocations satisfy needs.
* `game/persistence.py`: append-only SQLite transactions; stale prefixes fail.
* `game/player.py`: local actor-bound sessions; explicit hot-seat switching.
  Identity selection is not authentication; there is no network multiplayer.
* `game/fixtures/hube-stop-01.json`: fictional seed; six fixed conditions.
  `game/scenarios/hube_stop_01.json`: reference command trajectory.
* `game/play.py`, `terminal.py`, `dialogue.py`: clients and reversible forms.
* `game/journey.py`: provenance-based support trace; excludes incidental activity.
* `game/replay.py`, `replay_input.py`: semantic presentation and terminal controls.
* `tests/`: 58 tests covering rules, consent, replay, SQLite and real CLI paths.
* `ui-tests/arcade/dist/index.html`: isolated browser counter, no engine binding.

There is no `GameRunner` or `ActionSubmission` class. The corresponding actual
interfaces are `Game.submit(dict)`, `PlayerSession`, and the terminal adapters.
Runtime dependencies are Python's standard library; pytest is a development tool.

## Inventory

| Class | Components | Decision |
|---|---|---|
| A — reusable unchanged in semantics | `Mutation`, detached state, transaction diff, prefix-safe SQLite append, replay before-images, idempotency | Extract into `commons_engine`; preserve legacy record format. |
| B — reusable after refactoring | Table registry and epoch in `engine.py`; submission transaction and history reconstruction | Parameterise table registries and add an event-decoration hook. Serialize in-process writes. |
| C — Hube-specific | `_prepare`, `_evaluate`, exact matching, `event_001`, ending lock, fixture loader, terminal vocabulary, journey | Keep in Hube, including six-condition semantics and all IDs. |
| D — missing | First-class versioned agreements, approvals, governance policies, commitments, named commits, simulated escrow, independent outcome verification | Add Commons domain modules and fixtures above shared machinery. |
| E — limited guarantees | `save_log` detects stale writers only after local planning; no lock around in-memory validate/commit | Keep legacy save semantics; add a SQLite command transaction that reloads and validates while holding `BEGIN IMMEDIATE`. |

## Coupling and compatibility

`Game._prepare` marks the hard-coded `event_001` feasible; `load_fixture` accepts
one fixture; `_evaluate` supports the pilot's two rule families. These are explicit
pilot constraints, not invented defects. The schema vocabulary describes more
than the command implementation supports. Evidence references are attestations,
not independently authenticated external proof. Neither absence of production
identity nor deferred visibility is presented as a newly discovered regression.

The extraction must retain the `game.Game` API, canonical final JSON, logical
timestamps, idempotency results, saved event payloads, locales and CLI behaviours.
No Hube scenario, participant data, saved world or authored conceptual document
may be rewritten. A checkout bridge will locate the shared sibling package;
installed use will declare the same package as a dependency.
