# SADDLE PATHWAYS — terminal architecture

The terminal is the first playable laboratory. Existing browser files are legacy
scaffolding and are neither expanded nor required by this checkpoint.

Entry: `python -m commons_game play [scenario] [--actor ID] [--hot-seat]`, also
available through `subtle-pathways play`. `--db PATH` precedes the subcommand.
Use the installed optional trajectory integration for trajectory inspection and
the end-to-end demonstration. No curses, web framework or plotting dependency.

## Navigation

Startup selects a fictional scenario, then one active actor in the shared world.
Reopening a database preserves its scenario and history. A requested conflicting
scenario fails explicitly. Identity selection is local simulation, not production
authentication. A session stays bound to that actor; only explicit `--hot-seat`
enables switching, which the interface labels as development behaviour.

1. Ecosystem: inspect actors, relationships, reported capacities/needs, inferred
   complementarity; declare information or review a proposal.
2. Gathering: inspect unresolved objectives, resources/reservations, invitations,
   responsibilities and verified support; act through the same command boundary.
3. Scenarios: inspect contracts and their exact versions; propose, negotiate,
   accept, authorise, initiate, report fulfilment and independently verify.
4. History & trajectories: atomic event history, current trajectory, state at a
   selected transaction, explicit hypothetical branch, package YAML export, replay.
5. Help: vocabulary, actor boundary, controls and current scope limitations.

`b` returns; `q` exits; `0` cancels a form. Invalid values repeat the question.
Forms collect values before one engine submission. Cancellation creates no
partial records. Player-authored strings are never evaluated as executable code.

## Authorisation and concurrency

`ActorSession` is the TUI's write boundary. It rejects a mismatching actor in a
payload and binds every accepted command to the selected actor. Available actions
are candidates checked through `CommonsGame.validate`; the renderer owns no
alternative transition rules. Evidence placeholders are used only in pure
availability checks, never submitted as player evidence.

Every submitted action uses the state version that was inspected. The SQLite
adapter serialises reload, validation and append; a changed world returns a
conflict and requires review. Parties accept only the displayed immutable version.
The raw JSON CLI remains a clearly documented trusted development boundary.

Trajectory branches operate on detached replay instances and never submit to the
saved world. The terminal displays historical, simulated and hypothetical context
alongside package projections and evidence status. A completed scenario can still
be inspected, exported and replayed.

## Initial scope

Exercise the existing synthetic bilateral research-access agreement end to end.
Do not claim it is the actual Gallica arrangement. Do not add new governance
rules, empirical imports, Hube contracts or strategic branching mechanics just
to demonstrate the adapter. Those retain their existing M1–M5 acceptance gates.
The integration supplies inspection/simulation branches; it does not complete M5.
