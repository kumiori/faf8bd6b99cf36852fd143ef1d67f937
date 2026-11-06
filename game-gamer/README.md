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
