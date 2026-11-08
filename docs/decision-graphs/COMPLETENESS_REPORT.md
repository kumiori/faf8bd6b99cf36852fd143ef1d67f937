# Decision graph completeness and verification

The reconstruction exercise now has an executable transition contract. Its UI
buttons, menu choices and keyboard dispatch consume the registered IDs, the graph
projects those registrations, and passing tests collect the runtime observations.
The remaining application is source discovery, not a verified transition model.

## Baseline diagnosis

The original graph and report are preserved under `baseline/`. The inventory is
`baseline/diagnostic_inventory.json`; it reconciles every requested finding.

| Baseline category | Rows |
| --- | ---: |
| Unmapped options | 132 |
| Missing recovery paths | 41 |
| Untested transitions | 527 |
| Uninstrumented transitions | 376 |
| Total diagnostic rows, including overlaps | 1,076 |

Those rows concern 568 distinct graph subjects. In particular, the 132 unmapped
options are also uninstrumented and untested; these are not three separate bugs.
Every row contains the requested diagnostic, adapter, source, screen/question,
option/transition, target, guard, action and reason fields. Unknown values are
null. A source line belongs to the archived graph's source snapshot. The inventory
also states whether the current owning file still matches that snapshot's hash,
and whether a location is a call site, node registration or action definition.

| Root cause | Finding rows | Interpretation |
| --- | ---: | --- |
| Dynamic provider consumer not registered | 318 | 106 branches, each reported as unmapped, uninstrumented and untested |
| Menu value handler not registered | 78 | 26 branches with the same three diagnostic categories |
| Route dispatch not registered | 33 | A route value has no resolved source-adapter dispatcher |
| Recovery handler not registered | 8 | Cancellation, return or stack recovery is implicit |
| Runtime transition observer not registered | 488 | 244 other branches lack an execution observer and corresponding coverage |
| Instrumented transition not observed | 137 | An observer exists, but the baseline test manifest has no traversal |
| Engine outcome not observed | 14 | A particular symbolic authoritative outcome has no recorded traversal |

**925 finding rows across 417 subjects are extraction uncertainty.** The remaining
151 rows are measured verification gaps. **Zero baseline rows establish a
confirmed application defect.** This is not a claim that the 417 uncertain
subjects are correct: they remain unverified. A null destination or missing
source-level recovery edge is not a gameplay reproducer.

The collectors' former acceptance of observations from failing tests was a
verification weakness. The new gate consumes only passed-test transition evidence;
raw source-call coverage is insufficient to open it. This repair does not turn
any of the baseline unknowns into a confirmed gameplay defect.

## Why both source adapters were incomplete

`terminal` and `commons` encountered the same ownership problems:

- Picker results can be data values assigned into a form, not screen destinations.
- Choices assembled with comprehensions, loops, list mutation or runtime data need
  their consuming handler and constraints, not guessed return destinations.
- `if`/index dispatch, generic `push(*target)`, delegated screen builders and
  per-mode route stacks hide the actual navigation binding.
- Back and escape act on the live stack; `Cancelled` unwinds forms through the
  viewport and caller. A local Python return does not prove recovery to a screen.
- A normal function return or executed source line does not prove action success,
  actor permission, feedback, persistence, or a complete transition.
- IDs computed from source expressions also incorporate displayed wording.

No additional Python control-flow guessing was added. The old adapters remain
explicitly marked `source_only` outside the release contract. Their graph IDs are
discovery identifiers, not shared runtime identities or verification evidence.
The portable `Registry`, `Choice` and `TraceSession` APIs are available for future
terminal/host slices without introducing a host dependency into the core engine.

## Executable reconstruction contract

The owning declarations are in `commons_game/reconstruction_transitions.py`.
`reconstruction.py`, `reconstruction_filters.py`, `exercises.py` and the full-screen
controller execute the same registry. The portable machinery is in
`game_gamer/transitions.py`. Definitions bind source states, allowed outcomes and
destinations, handlers, guards, providers, criticality and engine references.
Callbacks are executed; their Python bodies are not inferred into a second graph.

The connection identities are:

```text
exercise.reconstruct.connect.recall
exercise.reconstruct.connect.prior_relationship
exercise.reconstruct.connect.invite
exercise.reconstruct.connect.dispute
exercise.reconstruct.connect.retract
exercise.reconstruct.connect.cancel
```

They remain unchanged when the displayed label changes. Send-now and save-draft
also have separate registered delivery choices, referencing `send_contact` and
`draft_contact`. Their parent workflow records the actual submitted action type;
it does not conflate a draft with a sent invitation.

Engine action nodes expose their `ui_transition_ids`. Authoritative events retain
their existing shape and commit IDs. UI observations link the stable transition
ID to the actual submission result and receipt. No UI identity or telemetry field
is injected into commands or persisted as an authoritative relationship.

Source-state and destination checks detect contract violations. Recovery restores
UI navigation and unsent drafts, never the authoritative world. A rendering/input
failure after a commit leaves that commit intact and returns to a safe view.
Keyboard interruption records an exit; it does not manufacture a cancellation
claim about an unobserved commit. Shared contracts, inboxes, histories and other
modes are explicit scope boundaries. Their internal gameplay is not certified by
this release. Remembered mode stacks are resolved against their actual top route;
they are not falsely mapped to mode roots. The return bridge covers a direct
shared inspector whose immediate parent is reconstruction, not arbitrary nested
shared navigation.

The conformance tests additionally exposed a race in the new outcome classifier:
an unrelated client could advance the world while an exact retry returned its old
receipt. Classifying from a UI revision difference called that a new commit.
A deterministic two-client regression now verifies the original receipt, one
original command event and the `idempotent` outcome. Retry resolution is observed
under the engine's re-entrant commit lock; event and world schemas remain unchanged.

## Verification and technical release gate

The parameterised transition tests assert actual state and history effects,
permission rejection, two-client stale revision rejection, UI messages and screens,
selection/filter recovery, exact retries, store reload and every replay prefix.
Shared fault-injection tests check failures before submission and after a saved
commit. Navigation-family tests exercise the real controller and dynamic choices.
These are complete transition tests rather than hundreds of source-branch probes.

Evidence is published only after pytest setup, call and teardown all pass.
Failed/xfail/skipped trials are not accepted as release evidence. Test references
include the package name so package and host test paths cannot collide. Checks
such as `persistence`, `replay` and `recovery` are recorded only after corresponding
assertions, and are linked to their actual test references. A check with no
observed transition is rejected. Stale or unsupported evidence is rejected.
A JSON round trip cannot change the gate's required normal outcome.

The current result is in `reconstruction/release_gate.json`. It checks zero
unmapped/recovery gaps, zero untested/uninstrumented **critical** transitions,
required outcomes and questions, all committed engine variants, state consistency,
persistence/replay, unexpected execution errors and an actual responsiveness
measurement. The default local benchmark budget is p95 <= 100 ms over at least
20 samples; it is an explicit policy threshold, not a fabricated measurement.
`reconstruction/responsiveness.json` contains the measured result, fixture size,
sample count and source digest. The fixture has 200 synthetic people; no live
world is modified. This is not a deployment-load or human-usability acceptance.

Noncritical uncovered transitions remain in the audit and filters. A passing
critical slice gate is not full transition coverage. The gate refuses filtered
views and an application-wide source graph. **Complete application verified is
always false for these deliverables.** There is no world migration, release
publication or deployment in this work.

## Four graph views and diagnostic filters

`application-overview`, `screen-navigation`, `decision-actions`, and
`transition-lifecycle` have Mermaid and DOT exports at the root and within
`reconstruction/`, backed by their canonical JSON graphs. The CLI also exports JSON views on demand. The application-level views retain amber source-only discoveries
outside the declared slice. They display coverage and extraction limitations.
Canonical IDs/transition references are retained; overview/lifecycle presentation
nodes are explicitly derived views, not new application screens.

The lifecycle view connects source states to request/guard/input/submission/
receipt/feedback/recovery paths. Cancellation and guard denial bypass submission.
Error paths distinguish failure before submission from failure after an accepted
receipt. Recovery destinations reconnect to their registered continuation choices.
`reconstruction/recall-lifecycle` is a focused starting point.

`filters/` contains the five requested finding views: unmapped, missing recovery,
untested, uninstrumented and unresolved dynamic branches. They select actual
findings from the canonical graph. Red denotes a confirmed graph-reference defect;
amber denotes extraction uncertainty or a conditional path. No source uncertainty
is relabelled as a confirmed application defect.

## Reproduce

From the repository root, collect both suites separately (their historic test
module names overlap):

```sh
(cd game-gamer && ../.venv/bin/python -m pytest -q \
  -p game_gamer.inspection.pytest_plugin --decision-coverage=/tmp/core-coverage.json)
.venv/bin/python -m pytest -q -p game_gamer.inspection.pytest_plugin \
  --decision-coverage=/tmp/host-coverage.json \
  --transition-evidence=/tmp/reconstruction-evidence.json
.venv/bin/python tools/build_decision_audit.py \
  --transition-evidence /tmp/reconstruction-evidence.json \
  --coverage /tmp/core-coverage.json --coverage /tmp/host-coverage.json
```

The host's HTTP/installation tests need ordinary localhost and dependency access.
The builder rejects mismatched manifests, unions only compatible observations,
regenerates the inventory/views, runs the disposable benchmark and evaluates the
gate. It preserves the original baseline graph/report.

```sh
python -m game_gamer inspect decisions --scope exercise.reconstruct \
  --transition-evidence docs/decision-graphs/reconstruction/evidence.json \
  --responsiveness docs/decision-graphs/reconstruction/responsiveness.json \
  --release-gate --release-output /tmp/release_gate.json
python -m game_gamer inspect decisions --view overview --format mermaid --output overview.mmd
python -m game_gamer inspect decisions --scope exercise.reconstruct --view lifecycle \
  --format dot --output lifecycle.dot
python -m game_gamer inspect decisions --filter uninstrumented --format json --output pending.json
python -m game_gamer inspect decisions --audit --inventory-output diagnostics.json
```

For an actual diagnostic trace, the primary UI accepts
`commons play --ui-trace-output ui.jsonl`. With `--line-mode`, that option selects
the same interaction controller over the line viewport. It is not supported by
the older developer/actor console. New trace files are created with mode 0600;
trace and world paths must differ. Default recording is a bounded in-memory ring.
The sample JSONL comes from an actual passing synthetic transition test.

Every trace contains `transition_id`, `session_id`, `actor_id`, `source_state`,
`requested_action`, `outcome`, `destination_state`, `duration_ms`, and
`correlation_id`. Additional fields contain sanitized receipt references,
submission-boundary observations, reason codes and contract checks. Messages,
notes, search text, agreement terms and profiles are not copied. A retry receipt
may contain the original mutation count; `idempotent` says those mutations were
not newly committed by this request. A store-level stale rejection may have no
engine event at all. A concurrent revision change is not attributed to this UI
action without its receipt. UI traces are diagnostic observations; engine events
remain authoritative.
