# game-gamer extraction readiness

The freeze candidate gives extraction a reproducible source baseline. The
[current mechanics and graph inventory](14-mechanics-freeze.md) define the
behaviour to carry across a package boundary.

| Target responsibility | Current seams | Extraction status |
| --- | --- | --- |
| Core transactions and replay | `commons_engine.WorldEngine`, mutation records, `from_log`, `world_at` | Most portable layer. It has table/mutation hooks and no terminal dependencies. Preserve ordering, exact idempotency and historical replay. The default schema and legacy handling are Hube-shaped and need explicit compatibility fixtures at the new boundary. |
| Persistence | `commons_engine.store.SQLiteStore`, `commons_engine.persistence` | Portable with an injected engine class. Preserve compare-and-submit semantics, atomic append and existing log readability. Private paths belong to the host application. |
| Commons domains | `model.py`, `engine.py`, `invitations.py`, `player.py`, `identity.py` | Domain rules already run independently of rendering. Explicitly separate the Commons command registry and fixture clock from generic transaction machinery. `ActorSession` supplies command discovery, actor binding and inbox queries. Current providers are simulated and require a host identity policy for deployment with real users. |
| Graph and trajectory projections | `projections.py`, `network_view.py`, `trajectory.py` | Reconstruct on demand from state/history. Preserve structural, stored and inferred edge identities and provenance. The trajectory adapter depends on a pinned optional package and keeps Commons events in its versioned metadata. Reuse its native serialization without introducing a second write path. |
| Matrix and inbox projections | `expertise.py`, `heatmap.py`, inbox queries in `player.py` | Inbox queries work over Commons records. The matrix consumes the questionnaire-specific expertise payload and completeness rules. Keep these interpretation rules with the matching projection or its world adapter. |
| Terminal interaction | `terminal_input.py`, `fullscreen.py` routes/screens and `CursesViewport`, `play.py`, renderer modules | Key decoding, viewport, raster and stack behaviour can be reused. Forms, screen builders and labels still refer to Commons commands and Montréal matrix/scenario navigation. Pull them through presentation interfaces when a second host needs them. |
| World definitions and external data | `scenarios/`, `scenario_catalogue.py`, `montreal_capture.py`, `ecosystem_import.py`, `catalogue.py`, `gathering.py` | Keep participant data, Notion vocabulary, source provenance, scenarios, policies, objectives and gathering configuration with the host world. Use fictional fixtures for shared tests and respect existing import privacy boundaries. |

A suitable first extraction boundary is the transaction and replay layer plus
its persistence adapter. Keep the Commons domain package as the initial host.
Its inputs remain versioned commands from an actor-bound session, and its outputs
remain event logs and detached world snapshots. Projections consume those outputs
and the terminal submits through the same session as other clients.

Before publishing a reusable package, establish a public event and world schema
compatibility policy, fixture-based parity for both Commons and Hube, and a
second host fixture exercising different content. The existing graph projection
dispatches to expertise matching based on world configuration, and the Commons
engine has a gathering-specific activation condition. These are seams to
isolate when extracting those domains. Terminal forms and copy also need host
interfaces before reuse with a different world. Production authentication,
migration guarantees and public API stability remain separate acceptance gates.
