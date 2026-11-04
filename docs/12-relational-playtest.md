# Heatmap, relational navigation and game modes

Playtest correction, 4 November 2026. **SADDLE PATHWAYS**.

The existing Commons engine, authorised Notion-derived actor catalogue, agreement
lifecycle, persistence, event schemas and pinned trajectory compatibility remain
unchanged. This correction changes read-only presentation and entered forms;
it does not add a second graph/state authority or assign source people permissions.

## Implemented, wired and exercised

| Capability | Player surface | Evidence |
|---|---|---|
| Fixed-scale heatmap | Ecosystem landing screen; `z` numeric toggle; arrows, `o` own row and `n` own column | Actual colour backgrounds asserted through PTY and ttyd; real 41-person world, monochrome fixture and browser rendering checked |
| Separate agency and focus | Playing/Focus header, directed relation context and breadcrumbs | Jeanne remains the simulated player while following counterpart, contracts, policies, objectives and scenarios; Back restores the selected relation |
| Bidirectional relationship | Enter a heatmap cell | Both W directions, exact counts, matching domains, answer states and source references; observation-only notice for a third party |
| Actual Network diagram | `w` from relation/profile, or `x` → Network | Extracted Hack camera/raster draws selectable typed nodes and directed/bundled links; existing contract, parties, policy and objective followed locally and through ttyd |
| Scenario catalogue | Scenarios → scenario inspection → current-world objective → contract → party | Authored workshop framing is distinct from objectives and contracts; source provenance and implementation status are visible |
| Contextual proposals | `a` on a relationship or profile | Current player remains proposer; counterparty is preselected; acceptance is never implied; the created contract is selected in the relevant relationship |
| Gathering status | Gathering conditions view | Registered fixture shows attendance intent and agreement gates; Montréal explicitly reports no registered event objective |

## Heatmap semantics and fixed scale

The read-only matrix remains **W = O Nᵀ**, over the approved common domain codes.
Row i offers; column j requests. No normalisation, quantile scaling, reweighting,
symmetrisation or source response imputation occurs.

| Matching domains | Requested background | Unicode shade | ASCII shade |
|---|---|---|---|
| 0 | `#172331` | `·` | `.` |
| 1 | `#26445e` | `░` | `:` |
| 2–3 | `#296584` | `▒` | `=` |
| 4–6 | `#3c8c96` | `▓` | `+` |
| 7–10 | `#66b0a2` | `▉` | `#` |
| 11+ | `#d4c98a` | `█` | `@` |

The legend carries the same fixed colours. Curses maps these requested colours
to the nearest supported xterm palette; glyphs/counts preserve meaning without
colour. `NO_COLOR` is honoured and `play --plain` uses ASCII. `?` is unknown,
distinct from the known-zero band; `-` excludes self-pairings from gameplay.
`[]` marks selection; `*` marks the player's row/column. Exact counts and matching
domains are shown for selection and in the relationship inspector. The raw
analytical diagonal remains intact. Both axes remain labelled while selection
scrolls through the complete population. Numeric view is one key away.

The existing capture still contains 41 people, 17 common expertise domains,
211 offer selections and 290 need selections. Its 1,640 off-diagonal cells remain
1,218 positives, 382 known zeros and 40 unknowns. No additional Notion capture,
private answer import or write-back was needed for this correction.

## Three independent interface contexts

`playing_actor` comes only from the explicit simulated actor session.
`focused_actor` describes the person under inspection or network centre.
`focused_relation` retains the original **source actor IDs** for the directed
cell, not a name join or mutable list index. Profiles, network, contracts and
scenario links inherit that relation context without changing agency.

Each route retains selection and scroll. Breadcrumbs show the actual route stack.
An observer may inspect both directions of another pair but cannot submit as
either person. A new agreement proposed from an inspected profile is the
current player's own proposal to that person; it returns to that actual pair's
relationship rather than presenting it as an agreement between observed third
parties. A material amendment still clears current-version receipts under the
existing engine rules. Historical views remain read-only.

## Hack renderer audit and reuse

The inspected sibling is **app_protocol_hack / PROTOCOL Hack**, revision
`74f0cfab96cebf1a7b453227423596b72bc7a802`.

| Existing source | Responsibility and dependencies |
|---|---|
| `temporal_graph/renderers/terminal/projection.py` | Camera rotation, orthographic/perspective projection, near-plane clipping, depth-ordered raster, directed arrow placement, structural/crystal glyphs; NumPy and Rich.Text |
| `temporal_graph/renderers/terminal/app.py` | Textual `CrystalApp`, layer toggles, selection/inspection, camera/zoom/rotation, playback and source diagnostics; Textual/Rich |
| `temporal_graph/visualization/adapter.py` | Read-only temporal frame/view adapter, layer styles, cached view variants and history inspection |
| `temporal_graph/visualization/layout.py` | Seeded incremental 3D layout and softened force relaxation with continuity, fixed points and disclosed geometric energy; NumPy |
| `tests/temporal_visualization/test_terminal.py` | Projection, clipping, deterministic raster, navigation, small/large viewport and playback checks |

The terminal raster has been **extracted**, not replaced by a separate drawing
algorithm. `commons_game/renderers/hack_terminal.py` retains its camera formula,
clipping, depth arbitration, line stepping and arrow placement. The exact
inspected source SHA-256 and adaptations are recorded in
[hack-renderer-source.json](hack-renderer-source.json). Tests compare its output
against the inspected original, including all camera axes, clipping, ASCII and
Unicode raster output.

The extraction replaces NumPy's small camera multiplication with equivalent
scalar arithmetic and Rich.Text with a neutral text/span sink. Optional per-node
glyph/colour, edge pattern/colour and an unknown-direction marker extend the
existing raster's vocabulary. Original defaults remain compatible. The reusable
component knows nothing of Commons actors, contracts, permissions or the store.
It requires an explicit visual projection. No runtime NumPy, Rich, Textual,
Hack checkout or private Hack cache is required by the installed Commons game.

The Commons adapter provides deterministic, viewport-fitted radial coordinates
around the chosen centre. These are **visual layout only**, not a new force or
energy model and not evidence of social distance. The full Hack relaxation,
temporal playback and its independent source reconstruction are not imported into
the Commons authority boundary. Rotate/zoom reuse the extracted camera;
automatic fit keeps the ordinary diagram on screen before deliberate zooming.

### Commons multiplex compatibility

`network_view.focus_graph` consumes the existing authoritative graph projection:

- People, organisations, resources, contracts, objectives, governance policies,
  capacities/needs and evidence retain their object types and shared vocabulary.
- Recorded affiliations and relationships remain separate from inferred
  complementarities. Unknown source direction has a `?` marker and no invented
  arrow; known directions retain arrows. Proposed contract-party links are
  dotted amber; accepted agreement-party links are solid sage. Inferred potential
  is dotted steel blue. All states/provenance remain attached to original records.
- Multiple expertise-domain edges for a directed pair are bundled for drawing,
  with every original edge retained in `records`. This changes neither W nor
  the canonical graph. Selection opens the usual Commons inspector.
- The actor centre, selected counterpart and their existing contracts get
  priority. Contract objectives, governing policies, parties and resources are
  included, even when two hops from the actor. There is no invented relationship
  from the player to a counterparty's contract.
- The diagram pages six or eight neighbours according to terminal size; omitted
  neighbours are counted, not discarded. `[ ]` page, Tab/arrows select, Enter
  inspects, `f` centres a selected node, `r` rotates, and `+/-` zoom. `b` restores
  the relation/profile from which the network was opened.

This is one canonical Commons graph, a heatmap over its source expertise mapping,
and multiple disposable views. The renderer cannot write state or decide consent.

## Scenarios: source, objective and agreement

The registry previously mixed four installed **world definitions** with one
generic Montréal collaboration objective. A world definition is not itself a
complete strategic scenario. `scenario_catalogue.py` now supplies a distinct
read-only catalogue without changing the engine's existing scenario/API names.

The empirical foundation is the actual authored workshop questionnaire:
`app_protocol_hack/question_sets/montreal_communs_2026/short.yaml`, questionnaire
`montreal_communs_data_ai_short_2026`, revision 5. The source SHA-256 and exact
sections are retained in the packaged `workshop-catalogue.json`.

Its **Montréal → Geneva: a future for data commons** situation uses prospective
backcasting: desired outcomes → necessary steps and actors → possible personal
contributions/positions. Fifteen source-authored outcome choices are translated
as possible desired conditions, including coalition, protocol, shared resource,
collaboration, policy and learning from failure. They are not manufactured
participant responses, completed engine objectives or verified collective goals.
No previously excluded synthesised nine-scenario set has been reintroduced.

The source itself flags international-summit claims for review before production.
The catalogue treats Genève 2027 as workshop framing and makes no assertion that
those future events or outcomes occurred. Source wording remains in the sibling;
interface summaries use British English. No raw participant scenario answers are
made public or imported by this change.

The generic `montreal-collaboration` objective is labelled as a **simulation
collaboration context**, not completion of the workshop scenario. This explicit
presentation association allows scenario → current-world objective → actual
contracts → parties/profiles, and the reverse contextual link, while preserving
each distinct domain meaning. Installed bilateral, Montréal–Geneva mentoring
and Gathering fixtures have separate synthetic statuses and descriptions.
Selecting a catalogue description never silently switches saved worlds.

The catalogue is inspectable. New strategy search, coalition optimisation and
an executable backcasting planner are not implemented or advertised as playable.

## Gathering reuse and integration limits

| Existing mechanism | Reused now / remaining integration |
|---|---|
| Commons `invite` / `respond_invitation` | Existing registered event-objective operations remain reachable in Gathering fixtures |
| Attending-party activation gate | Counts accepted invitations plus proposer, intersected with contract parties; displayed alongside exact-version acceptance counts |
| Governing policy and resources | Existing approvals, reconciled/internal resource control and quantity reservations still gate activation |
| Fulfilment and independent review | Existing lifecycle/outcome rules remain separate from attendance intent or feasibility |
| Hube `derive_possibilities`, `project_need`, `evaluate_requirements`, `project('now')` | Inspected and preserved as regression mechanisms; no new cross-world adapter has been claimed or installed |

Hube's six-condition STOP-01 feasibility counts independently verified supports;
proposed/committed allocations do not become verified supply. Integrating those
requirements into a new empirical gathering would require registered objectives,
resources, evidence/verification roles and an explicit cross-engine mapping.
This correction does not invent them. Montréal has no event objective, so its
Gathering screen clearly reports invitation/attendance operations as unavailable.
An accepted invitation or a feasible set of conditions is not verified realisation.

## Acceptance and regression evidence

```sh
.venv/bin/python tools/playtest_relational.py --output /tmp/saddle-relational --colour
.venv/bin/python tools/playtest_relational.py --output /tmp/saddle-relational-ttyd --colour --ttyd /path/to/ttyd
# Actual imported-world copy; requires the explicit private saved-world path:
.venv/bin/python tools/playtest_relational.py --output /private/path/jeanne-playtest --world /private/path/commons.sqlite --colour
.venv/bin/python -m pytest -q
```

Public fixtures are fictional. `--world` clones an explicit saved world with its
history; output is required outside the repository and uses private permissions.
The demonstration itself is read-only. `--colour` omits `NO_COLOR` only from its
test child; normal play continues to honour it. Reconstructed terminal frames,
entered keys, raw ANSI, replayable SQLite history, native trajectory and a
machine-readable result are retained in each evidence directory.

Jeanne has one unambiguous catalogue identity, 18 positive outgoing cells and
no contract directly attached to her in the inspected world. Two positive
counterparties are already parties to existing contracts. The real-data
acceptance follows one such relation and existing contract; it does not create
one to make the demonstration pass.

Both local PTY and real ttyd verified the requested sequence with **41 people and
the existing two contracts**: choose Jeanne, inspect her row/column, toggle exact
numbers, choose a positive outgoing cell, inspect both directions/sources,
follow the counterparty profile without changing player, Back, open Hack Network
centred on Jeanne, inspect the existing contract's parties/policy/objective,
follow the authored workshop scenario and return through the same stack.
Colour backgrounds were observed; selected context, state, log, replay and
trajectory round-trip were preserved.

Evidence:

- `/private/tmp/saddle-relational-jeanne-pty/`: private real-data local acceptance.
- `/private/tmp/saddle-relational-jeanne-ttyd/`: private real-data ttyd acceptance.
- `/private/tmp/saddle-relational-colour-02/`: fictional colour navigation acceptance.
- `/private/tmp/saddle-heatmap-negotiation-verified/`: proposal → revised version →
  both acceptances, accepted/unverified, historical read-only guard, mode switching,
  resize, replay and actual restart through the ordinary player CLI.
- `/private/tmp/saddle-relational-browser/`: fictional rendered browser checks of
  heatmap, fitted Network and contract navigation.

Final regression results: **148 tests passed** in the complete suite, including
the compatibility check that runs **58 original Hube tests**, frozen artefact
hashes, HTTP sessions/CSRF, native trajectory round-trip and an actual standalone
wheel installation without neighbouring projects. The 37 focused matrix and
relational tests cover fixed bands, exact values, unknown/zero separation,
observational agency, contract return context, scenarios, Gathering gates,
network navigation and upstream raster parity. Compilation and
`git diff --check` passed; no remaining test failures are known.

The original private saved world's state and full log were compared again with
the acceptance copy and remain identical. Browser checks used fictional data.
No independent novice usability study or production deployment is claimed.
The legacy entered line interface remains a developer/script fallback; the new
diagram and heatmap are in the full-screen interface, including its ASCII and
monochrome modes. Private captures and the original saved world remain outside
the public repository.
