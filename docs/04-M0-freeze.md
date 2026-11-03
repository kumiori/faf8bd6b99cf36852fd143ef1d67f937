# M0 — Engine baseline and compatibility freeze

Date: 3 November 2026. Scope: audit, checkpoint and regression verification; no
additional gameplay. See `M0_BASELINE.json` for exact checkpoint refs and hashes,
and `MILESTONES.md` for the ordered acceptance gates.

## What is frozen

Hube was already extracted onto `commons_engine.WorldEngine` before the latest
commit-first instruction. Its current checkpoint is the functioning reference.
Relative to the original inspection manifest, only `game/engine.py`,
`game/model.py`, `game/persistence.py` and `pyproject.toml` changed, plus the new
`game/_shared.py` checkout bridge. Scenario and test sources were preserved.

The six original acceptance artefacts are hashed separately: seed fixture,
packaged scenario, expected final world, full CLI input, acceptance scenario and
Funding/two-bed traversal input. Any later intentional migration must name the
changed semantics and refresh the baseline explicitly, rather than changing the
golden result to make a regression pass.

## Source inventory

| Concern | Current implementation | Baseline invariant |
|---|---|---|
| State and graph | `../game_hube/game/model.py`, `Game.get_world()` in `commons_engine/engine.py` | Stable node/relation IDs; detached read projections; schema 0.1 |
| Commands | `../game_hube/game/engine.py::Game.validate`, `_prepare` | `{key, kind, actor, ...}`; strict field/ref checks; no partial writes |
| Transition commits | `commons_engine/engine.py::WorldEngine.submit`, `_commit` | Validate and commit under an in-process lock; full before/after mutation set |
| Commitments | Hube `_prepare`: `act`, `confirm`, `verify` | Proposed allocation → provider-confirmed commitment → independent verification |
| Player authority | `../game_hube/game/player.py::PlayerSession` | Session cannot submit as another actor; switching needs explicit hot-seat |
| Verification | Hube `_prepare` verification branch | Another player, sufficient evidence kind and nonempty reference; organizer mode requires seeded organizer |
| Feasibility | Hube `Game._evaluate`, `project('now')` | Six fixed conditions; Marco/books seeded; verified quantity only; ending at 6/6 |
| Capacity | Hube `_compatible`, `_possibilities`, `project_need` | Exact resource/unit/location/date; pending allocations reserve; no double allocation |
| Persistence | `commons_engine/persistence.py`, Hube compatibility exports | Append-only SQLite; stale writer prefix fails; no independent authoritative snapshot |
| Replay | `WorldEngine.from_log`, `world_at` | Sequence and before-image validation; atomic historical transaction boundaries |
| Interactive play | `../game_hube/game/play.py::PlayTerminal` | Actor-bound, goal-directed commands; reversible forms; no hidden scenario script |
| Simulation | `../game_hube/game/replay.py::simulate` | Precomputed reference run; pacing changes display only |
| Configuration | `../game_hube/game/fixtures/`, `game/scenarios/` | One fictional stop; canonical expected final world remains unchanged |
| Presentation | Hube terminal/gettext; isolated `ui-tests/arcade` | English/Italian canonical equivalence; rendering owns no game rules |

There are no `GameRunner` or `ActionSubmission` classes in this implementation.
Local identity selection is not production authentication. The raw engine API is
a trusted simulation boundary, not an authenticated network endpoint.

## Existing regression coverage

The original suite covers initial state; pure validation; observations;
idempotency; new resource categories; consent and independent verification;
feasibility; atomic invalid actions; compatibility; partial capacity; withdrawals;
SQLite save/reload and stale-writer rejection; corruption detection; concrete
venues; pending-versus-verified progress; historical/detached reads; actor-bound
requests and responses; discovered identities; corrections; full entered play;
causal recap; local dialogue recovery; canonical resource reuse; CLI round trips;
replay controls and TTY restoration; and locale equivalence.

Fresh Hube baseline: **58 passed**. The Commons suite independently invokes the
same Hube tests and checks both applications inherit the same shared engine.
Full checkpoint-suite results are recorded in `VALIDATION.md`.

## Limits that must remain explicit

* Hube has simple allocation commitments, not first-class contracts. Sharing the
  transaction engine alone does not complete M4.
* Hube's feasibility rules and fixture loader deliberately refer to one event.
* Commons governance currently lives in its domain dispatcher; extraction into
  a reusable governance module and scoped delegation are still M2 work.
* The existing gathering and mentoring fixtures are synthetic scaffolds. They do
  not establish empirical import, operational Montréal agreements, alternative
  strategies, or full multi-mode gameplay.
* Preconditions are currently registered code paths and declarative data; no
  player-supplied executable contract code is evaluated.
* `game_hube`'s older installation instructions predate the new local shared
  dependency. For a fresh source installation, install `../game_commons` alongside
  `game_hube`; record this packaging documentation correction before release.

No Hube scenario, saved world, private participant material, UI experiment or zine
was modified by this M0 checkpoint. The unrelated files remain outside its Git
commit. The freeze is a compatibility contract, not a claim of production readiness.
