# Game-Gamer extraction map

The source is the Saddle Pathways mechanics freeze in `game_commons` at
`a849cdb`, with an earlier transaction lineage in `game_hube`. Game-Gamer
represents a collective as one evolving, authoritative world. Ecosystem,
Gathering and Scenarios are contexts for reading that world and submitting
actions to it. The retained boundaries come from the Probe Engine brief.
Questionnaire and Markdown instrument semantics belong to that engine.

| Class | Source | Responsibility and target | Evidence |
| --- | --- | --- | --- |
| CORE | `commons_engine/engine.py`, `records.py` | Ordered atomic mutations, exact retries, history and deterministic replay. Preserve Hube's inherited defaults through a compatibility boundary. | `test_engine`, `test_m0_freeze`, Hube suite |
| ADAPTER | `commons_engine/store.py`, `persistence.py` | SQLite serialisation and legacy log I/O. Separate the storage contract from this standard-library implementation. | Competing-process reservation, restart and stale-position tests |
| CORE | `commons_game/model.py`, `engine.py`, `invitations.py` | Actors and resources, declarations, contact, attendance, versioned agreements, approval, reservations, fulfilment, verification and objectives. Retain exact existing rules and event serialisation. | `test_engine`, `test_collective_action`, `test_mechanics_freeze` |
| CORE | `commons_game/projections.py` | Structural network, declared-domain matching, contract registry and neighbourhood. Read models use a single world snapshot. | Engine and graph regression tests |
| ADAPTER | `commons_game/projections.py`, `expertise.py`, `heatmap.py`, `presentation.py` | Questionnaire matching, bounded matrix arithmetic, first-name presentation and rendering. Host layers add labels and substitute expertise edges. | `test_matrix_navigation`, `test_relational_navigation` |
| ADAPTER | `commons_game/player.py`, `identity.py`, `server.py` | Actor binding, available commands, presentation-specific inbox grouping, pending identity requests and transport. A host establishes actor identity before submission. | `test_player`, `test_collective_play`, `test_http` |
| ADAPTER | `commons_game/ecosystem_import.py`, `montreal_capture.py`, `catalogue.py`, `config/` | Notion capture, privacy and source mapping. Host imports emit events through the same authoritative engine. | `test_collective_play` and matrix tests |
| ADAPTER | `commons_game/trajectory.py`, `trajectory-lock.json` | Optional external trajectory document interchange. Native history replay remains in the engine. | `test_trajectory` |
| APPLICATION | `scenario.py`, `scenario_catalogue.py`, `scenarios/`, `gathering.py` | Montréal and fictional scenario content, configured policies and objectives, and gathering display text. The package defines the reusable world schema and mechanics. | Demo, gathering, mechanics and standalone-install tests |
| APPLICATION | `__main__.py`, `commands.py`, `play.py`, `fullscreen.py`, `tui.py`, `web/` | Application workflows, terminal and web views and controls. | Playability, HTTP and terminal tests |
| DO_NOT_EXTRACT | `terminal_input.py`, `network_view.py`, `renderers/` | Key decoding, graph layouts and the current renderer stay with Saddle Pathways. | PTY, matrix and renderer regressions |
| PROTOTYPE | Optional 3D camera and experimental alternative strategy views | Presentation experiments stay with the host. Core branching produces a separate hypothetical world. | Relational navigation and trajectory tests |
| DO_NOT_EXTRACT | Private saves, captures and local configuration | Preserve only fictional fixtures and public schemas in package artifacts. | Wheel and sdist inspection |

The [golden baseline](../tests/fixtures/game-gamer-baseline.json) fixes the
source commit, canonical definition fingerprints, schema, submitted commands,
rejections and world, graph, history and inbox fingerprints after every step.
Initial fixtures are the checked-in scenario JSON files. Montréal's entry
uses the fictional seed only. The detailed freeze report covers the earlier
read-only audit of the private world and its limits. The baseline also covers
contact acceptance, rejection of the wrong recipient, rejection of stale terms,
institutional authorisation, verification and gathering attendance.

## Local acceptance

| Gate | Result |
| --- | --- |
| Source freeze and behavioural equivalence | Four fictional worlds reproduce every recorded world, graph, inbox and history fingerprint, including rejected attempts. |
| Standalone package and migrated host | 180 tests passed, including HTTP integration over loopback. The compatibility test also ran the original 58-test Hube suite. |
| Terminal preservation | The matrix and collective-action PTY playthroughs passed through restart and trajectory replay. |
| Independent consumer | The rehearsal example starts with an inferred match and reaches a verified objective in 13 events. Its restored world and projections match the original. |
| Distribution | The wheel and sdist were built, inspected and installed in clean environments. The wheel contains only Game-Gamer modules and distribution metadata. The sdist also contains the fictional example, package tests and documentation. |
| Second repository | A clean consumer repository installed `v0.1.0` from a temporary bare Git repository over `git+file` and ran the rehearsal example. |
| External release | Pending a configured external package remote. |

The Montréal host consumes the shared model and transition engine through
its compatibility adapter. Existing save files keep their event format.
The scoped public API is for new worlds created with `game-gamer/world/v1`.
