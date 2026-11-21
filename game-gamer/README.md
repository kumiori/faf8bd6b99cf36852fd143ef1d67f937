# Game-Gamer

Game-Gamer is a UI-independent engine for collective decision-making. It
represents actors, relationships, capacities, resources, governance and
commitments in a shared world. It validates authorised actions, applies
reproducible transitions, preserves provenance and returns neutral read models.

Ecosystem, Gathering and Scenarios work with the same world. For example, a
reported capacity and need can produce an inferred match in Ecosystem. The
actors can then record attendance in Gathering, negotiate a versioned agreement
and produce independently verified evidence. Each accepted action advances the
same history.

## Install and run

Python 3.11 or later. The package uses the Python standard library. Install from
the directory containing this README.

```sh
python -m pip install .
python examples/minimal_collective/main.py
```

The fictional example uses three actors, two independently recorded party
acceptances, steward approval, a room reservation and independent review. It
serialises the history, restores it and checks the complete projection.

## Optional terminal

```sh
python -m pip install 'game-gamer[tui]'
game-gamer play examples/minimal_collective/world.json --db rehearsal.sqlite
```

Use the example from a source checkout or unpacked source distribution.
See the [terminal guide](docs/TUI.md) for controls, the independent playthrough
and the reusable widget API.

## Public API

```python
import json
from pathlib import Path

from game_gamer import ActionSubmission, Collective, SimulationBinding

definition = json.loads(Path("examples/minimal_collective/world.json").read_text())
game = Collective.start(definition)
binding = SimulationBinding(scope_id=game.scope_id, actor_id="sam")
action = ActionSubmission(
    action_id="contact-1",
    actor_id="sam",
    scope_id=game.scope_id,
    target_id="contact-1",
    expected_revision=game.project()["version"],
    action_type="send_contact",
    payload={"id": "contact-1", "recipient_id": "jo", "message": "Discuss a rehearsal?"},
)

decision = game.evaluate(action, binding=binding)
result = game.submit(action, binding=binding)
graph = game.project("network")
restored = Collective.from_history(game.history())
alternative = game.fork(at=1, branch_id="gathering-first")
```

Use `Collective.start(definition, path=...)` to create a SQLite-backed collective
and `Collective.open(path, scope_id=...)` to reopen it. A host supplies the
simulation binding and may implement the `CollectiveStore` protocol. All accepted
actions in this release have simulation authority.

See the [semantic model](docs/SEMANTIC_MODEL.md),
[transition contract](docs/STATE_TRANSITIONS.md),
[governance](docs/GOVERNANCE.md) and [persistence](docs/PERSISTENCE.md).

## Inspect the implemented decision graph

```sh
python -m game_gamer inspect decisions --format json --output decisions.json
python -m game_gamer inspect decisions --format mermaid --output decisions.mmd
python -m game_gamer inspect decisions --format dot --output decisions.dot
python -m game_gamer inspect decisions --audit --audit-output decision_audit.json
```

Extraction is read-only and deterministic, including without the terminal extra.
Engine schemas/rules and registered interface source drive the same canonical
graph. Contextual availability, scope selection, observed test coverage and release
comparison are described in [Decision inspection](docs/DECISION_INSPECTION.md).
Imperative branches that remain unresolved are explicit audit findings.

The reconstruction host now exposes an executable transition contract with stable
IDs, structured UI traces and passed-test release evidence. Use
`--scope exercise.reconstruct --view lifecycle` when Commons is installed.
`--filter uninstrumented` and the other finding filters keep remaining source-only
gaps visible. A scoped release gate never certifies the complete application;
see [the verification extension](docs/DECISION_INSPECTION.md#executable-transition-contracts-and-scoped-release-verification).

## Application extensions

Game-Gamer 0.3.0 exposes a versioned extension contract for registered commands,
policy hooks, initial state and projections. See [the public extension API](docs/EXTENSIONS.md)
and the independently packaged [Lantern Club example](examples/lantern-club/).
World-driven play is the default. Missions are optional mutable world objects,
and target locking adds explicit constraints to the same runtime.
