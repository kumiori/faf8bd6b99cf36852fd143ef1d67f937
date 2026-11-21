# Public application extensions

Game-Gamer 0.3.0 supports trusted application extensions through
`game-gamer/extension/v1`. An extension supplies command schemas, transition
handlers, policy hooks, initial state and projections. All changes use the
existing atomic event store. World-driven play is the default. Missions are
optional world objects, and target locking is a game configuration.

## Register application mechanics

The complete independent application is in `examples/lantern-club/`. It has its
own Python distribution, one custom command, one membership policy and one
projection. It imports only Game-Gamer's public API.

```python
from game_gamer import CommandDefinition, Extension, PolicyHook

application = Extension(
    id="fictional.lantern-club",
    version="1.0.0",
    commands={
        "record_visit": CommandDefinition(
            required={"shelf_id"},
            optional=set(),
            target_field="shelf_id",
            handler=record_visit,
        ),
    },
    policies=(PolicyHook(before=members_only),),
    projections={"visit_count": visit_count},
)
```

`handler(world, command, *, actor, timestamp, sequence, action)` edits the
candidate world and may add affected IDs to `action['target_ids']`. It raises
`DomainError` to reject a transition. Command schemas reject missing, unknown
and reserved fields. Custom command names cannot replace built-in commands.
`target_field` identifies the payload field that must equal the public action
wrapper's `target_id`. Use `None` for commands without an object target.

Application state belongs in records in the existing authoritative tables,
normally `configuration`. Every record retains its stable `id`. Additional
top-level tables and destructive record deletion are rejected because the event
schema cannot replay them. Use a recorded status transition to retire a record.

A policy has optional `before` and `after` handlers with the same call signature.
Before handlers inspect a detached world. After handlers extend the proposed
state. A rejection at either stage discards the entire candidate transition.
These functions must be deterministic and free of external side effects because
validation may run them before the commit attempt. External service calls belong
in the host, with their results subsequently recorded through the engine.

A projection receives a detached world and returns a read model. Applications
may add projection names or supply `network` and `possibilities` providers.
`world`, `log`, `timeline` and `now` remain runtime-owned projections. An optional
`initialise(world, definition)` callback seeds application configuration inside
the genesis event. The engine validates standard world references afterward.

The contract accepts installed trusted Python callables. Player-submitted worlds,
contracts and saved extension descriptors contain declarative data. Descriptors
never import or execute Python from a saved module path.

## Construct and restore

```python
from game_gamer import Collective, SimulationBinding

game = Collective.start(definition, extension=application, path="club.sqlite")
binding = SimulationBinding(scope_id=game.scope_id, actor_id="lee")
decision = game.evaluate(submission, binding=binding)
result = game.submit(submission, binding=binding)

reopened = Collective.open(
    "club.sqlite", scope_id=game.scope_id, extension=application,
)
restored = Collective.from_history(game.history(), extension=application)
alternative = game.fork(at=1, branch_id="another-choice")
```

`start`, `open`, `evaluate`, `submit`, `from_history`, historical attention views
and `fork` retain the same extension. Forks run in separate memory with the
existing explicit counterfactual scope. `game.command_registry` exposes the
active immutable schemas, including application commands. Existing calls that
omit `extension` keep their previous built-in behaviour.

The genesis state records the required extension ID, exact version and contract
in configuration record `game-gamer:extension`. Loading requires matching code.
An unavailable extension raises `extension_unavailable`. A different supplied
version raises `extension_version_mismatch`. An unsupported contract raises
`unsupported_extension_contract`. Extension metadata is immutable during play.

Applications may explicitly call `register_extension(application)` when their
installed module loads. A descriptor can then resolve through that registry.
An explicit extension argument avoids dependence on process-wide registration.
The runtime never silently substitutes another installed version.

The lower-level `CollectiveEngine(extension=application)` and
`EngineFactory(application)` support existing host clients and stores. Engine
`record_transition(before, after, summary, actor=...)` is the trusted setup/import
boundary. It checks the before-state under the engine lock and preserves required
extension metadata. Use `engine.transaction()` for a multi-step trusted setup
operation. Player actions continue through `submit` and its authorization checks.

## World driven and target locked games

A world definition can omit missions entirely. Players can still inspect the
world, record contact, negotiate contracts and execute registered application
commands. The `mission_create` action proposes a mission during play. Its payload
contains an ID, title, rationale, target, criterion descriptions and governance
with explicit `adopters`, `verifiers` and `operators` actor lists.

Missions are first-class records with `kind=mission_definition` in authoritative
configuration. They have stable IDs, immutable version snapshots, exact-version
adoption receipts and the same event history as all other world objects.

The governed lifecycle is proposed, adopted, pursued, verified and completed.
An authorised operator can abandon an active mission or reopen a closed one.
Reopening creates a new proposed version and requires renewed adoption.
`mission_challenge` records a contested rationale, need, target, feasibility or
requirements. An independent authorised operator applies a proposed revision
through `mission_revise`. Earlier receipts and revisions remain in history.

`mission_verify` independently verifies a contribution. `mission_verify_outcome`
checks all declared criteria against verified contribution evidence and records
an explicit mission-version verification. `mission_complete` records completion
following that verification. Accepted contributions remain distinguishable from
verified evidence. Missions can share criterion IDs and verified support while
retaining their own objectives and completion decisions.

An initial `missions` array can seed proposed missions in genesis. Each record
uses the `mission_create` fields with `id` replacing `mission_id`, plus
`proposed_by`. A target-locked definition supplies explicit constraints.

```json
{
  "gameplay": {
    "mode": "target_locked",
    "mission_id": "reading",
    "allowed_actions": [
      "record_visit", "mission_adopt", "mission_join", "mission_commit",
      "mission_accept", "mission_verify", "mission_verify_outcome",
      "mission_complete", "mission_abandon", "mission_reopen"
    ]
  }
}
```

The selected mission must exist in the seeded authoritative world. The runtime
rejects commands outside `allowed_actions`, commands addressing a different
mission and commands after completion/abandonment except an explicitly permitted
reopen. The same policies, action validation, event ordering, reservations and
replay machinery apply in both configurations. Resource contributions retain
the existing distinction between offers and contract-backed reservations.

## Version and release discipline

Bump the application extension version whenever interpretation or policy changes.
The contract version changes when the callback/descriptor protocol changes.
Game-Gamer's package version is independent of both. Commons pins Game-Gamer
0.3.0 and bundles its immutable wheel with a SHA-256 lock in the host release
bundle. Historical 0.2.0 Hube consumers retain the public transaction interfaces.
