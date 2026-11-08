# Decision graph inspection

`game_gamer.inspection` projects the installed implementation into a deterministic,
read-only graph. It reads the runtime's `FIELDS` registry and Python source, not a
live player session or a second hand-maintained graph. The optional host adapter
also reads the installed Commons interface source. It never parses rendered text.

```sh
python -m game_gamer inspect decisions --format json --output decisions.json
python -m game_gamer inspect decisions --format mermaid --scope exercises --output exercises.mmd
python -m game_gamer inspect decisions --format dot --output decisions.dot
python -m game_gamer inspect decisions --audit --audit-output decision_audit.json
python -m game_gamer inspect decisions --format json --output decisions.json --audit
python -m game_gamer inspect decisions --diff previous.json current.json
```

`--interface auto` selects portable terminal source and, when installed, Commons
source. `--interface terminal` is portable; `--interface commons` requires the
host; `--interface none` extracts the engine alone. Source inspection does not
import curses or wcwidth. If a registered interface's source is unavailable,
the graph and audit explicitly report unavailable navigation coverage. This API
supports normal Python source/wheel installations; sourceless bytecode interfaces
require an additional adapter.

`--scope` accepts ecosystem, gathering, scenarios, exercises, shared, engine, or a
stable node ID prefix. Boundary nodes are retained so exported references remain
valid. `--level navigation|decision|state` selects a representation. An audit of a
filtered graph measures that selection, including boundary nodes, not the whole
game. Unknown scope prefixes produce an empty selection.

## Read-only contextual inspection

World selectors follow the existing portable CLI convention: a world definition
JSON file, rather than a host-specific world nickname. An exported `history()`
document is also accepted. `--db` optionally reads an existing SQLite log through
a read-only connection and restores a detached in-memory snapshot.

```sh
python -m game_gamer inspect decisions \
  --contextual --world examples/minimal_collective/world.json --actor sam \
  --interface terminal --limit 50 --output decisions_sam.json
```

The same action definitions are evaluated against real `action_options` candidates.
Availability is **enabled**, **disabled** with machine-readable reason codes, or
**unknown** when the payload/target is not yet known. Aggregate availability is
based on the full candidate set; `--limit` bounds exported candidates per action,
not evaluation. A proposal requiring unentered terms is unknown, not enabled.
Unconditional actor/role permission guards can still resolve to disabled.

Contextual exports omit developer UI source navigation and curator action types
for noncurators. Hidden/archived actors' records are not enumerated. They do not
export world profiles, invitation messages, agreement terms, or private notes.
The structural API is a local developer/curator introspection surface, not a new
player endpoint. A deployed host must enforce its own developer/curator access
before exposing structural inspection. No live authentication authority is added.

## Canonical schema 0.1.0

Every export starts with `schema_version: "0.1.0"` and `graph_type: "decision"`.
The canonical JSON fields are:

| Field | Meaning |
| --- | --- |
| `levels` | Navigation, decision, symbolic state layers in this document |
| `mode`, `context` | Structural or actor/world contextual evaluation |
| `nodes` | Stable IDs, kinds, labels, scopes, source provenance and optional action definitions |
| `edges` | Stable IDs, endpoints, option labels, action references, guards, effects and recovery flags |
| `interfaces` | Adapter IDs, source modules, availability and completeness |
| `sources` | SHA-256 of inspected installed source modules |
| `implementation_digest` | Deterministic fingerprint used to reject stale coverage |
| `diagnostics` | Explicit unresolved or unavailable adapter metadata |
| `coverage`, `selection` | Optional observed coverage and scope/level selection |

Node kinds are `screen`, `question`, `route`, `interaction`, `action`, and `outcome`.
A registered screen is a source `Screen(...)` construction site; reusable widgets
are included. A question is a registered input call or a screen entry-selection
site. Labels remain separate from machine IDs. Source provenance records module,
qualified function, and one-based start/end lines. IDs use semantic source
expressions and enclosing branch conditions, not file paths or line numbers.
Changing wording/branch expressions can change an interface ID; adding unrelated
lines does not. Duplicate source declarations with identical semantics form one
registered structural branch. Dynamic rosters/contracts remain parameterised.

Engine nodes come directly from the authoritative action registry. They carry:

- Required/optional payload field names and envelope fields.
- Implemented validation expressions, validator names, reason codes and conditional
  `when` expressions. Permissions are a subset of these guards.
- Source expressions for state effects, called helpers and generated event names.
- Allowed/rejected outcome edges. These identify action *types*; they do not
  enumerate possible world states or promise that every payload is valid.

`action_ref` plus `field` references metadata on an action node without copying it
onto every edge. Input types and domain constraints are represented by actual
validation expressions, not an invented JSON Schema for arbitrary payloads.
Effects/events are symbolic Python expressions with provenance, not executable
code in the exported graph. Guard expressions referring to helper-local names
retain those names and their source; this is an inspectable source projection,
not a general Python symbolic evaluator. Rejection commits no state. Exact retries
are accepted by the existing commit boundary and may return a prior result.

Interface source adapters project registered functions, calls, Screen construction,
prompts, literal option lists, static list mutations, literal menu-building loops,
route pushes, input dispatch, explicit `Cancelled` outcomes and engine references.
Literal loops such as the reconstruction menu preserve recollection, prior
relationship and new invitation actions as separate branches. List comprehensions
and runtime providers are represented symbolically with their source expression
and enclosing constraints; structural extraction never enumerates the world.

An unresolved destination has `target: null`, `resolution: "unresolved"` and a
specific diagnostic. It is never silently treated as a completed action.
A local input-return outcome means only that a value returned to the calling
function; continuation edges expose that caller's subsequent branches.

Mermaid groups scopes and retains canonical node/edge IDs in comments. DOT uses
canonical IDs as node names and `id` attributes. Their legends are presentation
nodes outside the canonical graph. JSON retains complete metadata; labels in the
Mermaid overview are shortened when necessary. Neither visual format executes
source expressions.

## Actual audit semantics

The audit counts registered source screen sites, question sites, declared option
branches (each dynamic branch once), and authoritative action types. Function-call,
render and dispatcher edges establish source-level structural paths but do not
add to option counts. Explicit cancellation branches are options.

Reachability follows resolved directed edges from registered entry functions.
Required screens without a path are errors. Recovery checks follow resolved edges
to an entry point, explicit cancellation, completion, or a valid recovery edge.
Options with no destination/action and broken references are errors. Missing
observed transition coverage and incomplete/dynamic metadata are warnings.
Disabled actions are informational. All counts are calculated from the graph.

The Python adapter is deliberately conservative about imperative dispatch. Current
incomplete cases include data-selected destinations (`push(*target)`), handlers
selected by list indices or dynamically assembled strings, some delegated route
renderers, and runtime provider values whose handler cannot be statically resolved.
Shared widgets use dynamic titles/labels and expose expressions rather than a
concrete world-specific label. Source call paths are an overapproximation of
control flow: the audit cannot prove satisfiability of arbitrary Python guards.
A structurally reachable screen therefore does not certify playability.
These limitations are reported by `source_adapter_incomplete` and per-edge
findings. The interface audit currently fails on unresolved options/recovery;
it must not be described as complete navigation coverage or a mechanics failure.
Use JSON diagnostics to distinguish an adapter gap from a broken game transition.

Audit returns exit code 1 for unexcepted errors, 0 otherwise; CLI/input failures
return 2. Export files are still written when an audit fails. `--audit-output`
contains every finding; stdout remains concise.

Document exceptions in a JSON list supplied via `--exceptions`:

```json
[{"code":"unreachable_screen","id":"stable.screen.id","reason":"Deprecated screen retained for compatibility."}]
```

Exceptions remain visible on findings and do not change counts. A reason and
exact code/ID are required. An unused exception is a warning.

## Observed automated coverage

```sh
python -m pytest -p game_gamer.inspection.pytest_plugin \
  --decision-interface terminal --decision-coverage decisions_coverage.json
python -m game_gamer inspect decisions --interface terminal \
  --coverage decisions_coverage.json --audit --audit-output decision_audit.json
```

The opt-in plugin profiles actual returned engine submissions, prompt selections
and navigation calls. It records stable edge IDs against pytest node IDs. It does
not infer traversal from test names or from executing a source line. Exceptions
are not recorded as successful navigation. Coverage can also be collected through
`CoverageRecorder(graph).capture(test_ref)` in integration tests. Nested decision
recorders are supported; unrelated active profilers are rejected explicitly.

A normal input-return edge may be observed while its downstream imperative handler
remains unresolved. Such a handler is **uninstrumented**, not covered. Both
uninstrumented and instrumentable-but-uncovered decision edges contribute to
`Untested transitions`; a separate count and per-edge status distinguish them.
Tests running in subprocesses/other threads are not included in the parent
profiler's manifest. Run the plugin in those processes to collect their coverage.
The core has no pytest dependency unless this opt-in plugin is imported.
Coverage manifests must match the exact implementation/adapter selection; stale
coverage raises an error. Re-run tests after source changes.

## Introspection API and adapter registration

```python
from game_gamer.inspection import InterfaceAdapter, extract_decisions
from game_gamer.inspection.audit import audit_graph
from game_gamer.inspection.export import export_graph, diff_graphs

adapter = InterfaceAdapter(
    id="my_terminal",
    modules=("my_package.interface",),
    entry_functions=("my_package.interface.run",),
)
graph = extract_decisions(interfaces="none", adapters=[adapter])
report = audit_graph(graph)
text = export_graph(graph, "mermaid")
```

Adapters register source locations and entry points, not a parallel list of
screens/options. Added prompts/actions become part of the next extraction.
For contextual use, pass both `collective=...` and `binding=...`. Returned data
is detached; no `submit` is called. Source resolution does not execute inspected
interaction functions or arbitrary guard expressions. Normal Python package
initialisers can run during module lookup.

## Compatibility and migration

No world schema, persistence format, event ordering, action semantics or terminal
behaviour changes are required. No saved-world migration is needed. The existing
`play` command remains available; `python -m game_gamer` additionally supports
module invocation. Runtime dependencies remain empty; the terminal extra remains
optional. Unsupported graph versions are rejected by release comparison. Diff
reports added/removed screens/options and changed mappings, guards, permissions
and recovery paths, ignoring source-line-only changes in semantic comparisons.
Source provenance and fingerprints intentionally change when source code moves.

## Executable transition contracts and scoped release verification

The Commons reconstruction scope now uses explicit registrations consumed by the
UI itself. `--scope exercise.reconstruct` selects this contract and does not run
the imperative source adapter over those interactions. Stable transition IDs are
independent of displayed wording. The former source-only graph is preserved as a
baseline for diagnosis, not treated as verified navigation.

The new switches are `--view overview|navigation|decisions|lifecycle`, repeatable
`--filter unmapped|missing-recovery|untested|uninstrumented|unresolved-dynamic`,
`--inventory-output`, `--transition-evidence`, `--release-gate`,
`--release-output`, `--responsiveness` and `--max-p95-ms`.

```sh
python -m game_gamer inspect decisions --scope exercise.reconstruct --audit
python -m game_gamer inspect decisions --view navigation --format dot --output navigation.dot
python -m game_gamer inspect decisions --filter unmapped --format json --output unresolved.json
```

The pytest plugin can write `--transition-evidence FILE`. Unlike raw observed-call
coverage, this evidence is accepted only from tests whose setup, assertions and
teardown all pass. Critical engine transitions require observed success/rejection/
cancellation, feedback/recovery, state assertions, persistence and replay. Missing,
stale or unsupported evidence blocks the release gate. Registered delivery choices
keep send-now and save-draft distinct. Contextual exports continue to omit developer
UI declarations and privileged navigation; a contextual scope yields its engine
availability, not a player-visible structural contract.

`game_gamer.transitions.Registry`, `Choice`, `Result`, `TraceSession`, and
`observe_transitions` provide the portable execution boundary. Registrations bind
actual handlers and allowed states/outcomes; the host consumes the registry for
key dispatch and menu options. A mismatch is recorded as a contract violation.
The core still installs without Commons or the optional terminal dependencies.
No command, event or saved-world schema migration is introduced.

The UI trace schema is `game-gamer/ui-trace/v1`. Records include the requested nine
identity/state/action/outcome/timing fields, safe receipt references and phase
observations. They omit raw payloads and profile data. The engine's command/result
is unchanged; retry resolution is observed under its existing re-entrant lock.
Submission observations distinguish engine results from earlier store/binding
rejections. Global world revisions are context, not proof of this action's effect.

See the repository's `docs/decision-graphs/COMPLETENESS_REPORT.md` and scoped
`reconstruction/release_gate.json` for the reconciled inventory, precise boundaries,
actual verification and benchmark limitations. A reconstruction gate result never
certifies the complete application. Source-only discovery remains explicitly
uncertain outside the registered slice.
