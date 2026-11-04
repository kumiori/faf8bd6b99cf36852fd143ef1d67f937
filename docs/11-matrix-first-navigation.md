# Matrix-first Ecosystem and coherent game navigation

Sprint evidence, 4 November 2026. **SADDLE PATHWAYS: THE COMMONS GAME.**

This records the numeric-matrix checkpoint. The subsequent
[relational correction](12-relational-playtest.md) adds the default heatmap,
extracted Hack diagram renderer and a distinct scenario catalogue.

The engine's contract rules, actor-bound writes, persistence and event schemas
remain authoritative. No second game state, matrix store or permission authority
has been introduced. Names remain first-name-only in player-facing labels;
source identities, provenance and replay retain the original records.

## Actual status of the three modes

| Mode | Implemented and wired | Verification and limits |
|---|---|---|
| Ecosystem | Matrix landing view; directed cell inspector; matching domains, answer states and source assertions; Network, People, Organisations and Resources alternatives via `x` | Real 41-person world opened and a cell inspected in the full-screen interface without changing its state or log. Fictional full-screen acceptance exercises discovery through negotiation. A positive score is reported potential, not competence certification or collaboration. |
| Gathering | Separate conditions screen; registered gathering objectives and invitation/response operations; shared contracts remain reachable | Navigation exercised locally and through ttyd. Existing gathering-fixture regression exercises invite/respond. **Montréal has no registered gathering objective**, so the screen explicitly explains that invitations/attendance operations are unavailable there. A new event planner has not been implemented. |
| Scenarios | Separate objectives screen, supporting graph links, recorded native trajectories, replay | Mode switching and trajectory/replay exercised locally and through ttyd. Strategy search, coalition optimisation and a new hypothetical-planning editor remain unimplemented and are labelled on screen. Existing developer branch tools remain available separately. |

`m` always offers the three paths. `e`, `g`, `s` switch directly. Each path retains
its root selection/scroll state. `c` contracts and `i` inbox are transversal;
governance-policy nodes are reached through typed graph links rather than a
fourth game mode. Mode switches never initialise or reset a world or actor.

## Source and matrix audit

The audit inspected the current read-only adapter and these existing analytical
sources in the adjacent `app_protocol_hack` checkout:

- `protocol/collective_presentation.py`: answered-only O/N incidence and strict
  directed W, including explicit empty vectors and raw diagonal retention.
- `protocol/multiplex_v2.py`: the same matrix-derived directed potential edges.
- `docs/COLLECTIVE_ANALYSIS_CONTRACT.md`: source-state precedence, no zero fill,
  participant identity and gameplay self-link exclusion.

The earlier Commons capture already contained selected offer/need domains linked
to source-derived actor IDs. It did **not** retain complete answer-vector states.
Positive declarations alone cannot establish all non-selected entries as known
zeros. The smallest added mapping is `saddle-expertise/v1`: shared domain
codes/labels, per-person offer/need answer state, selected allowlisted codes,
count of unmapped selections, source response reference/field and capture time.
No raw answer text, contact details or identity authority are imported.

`capture_montreal` version **v2** uses complete source/property pagination and
the existing submitted-inventory reconciliation. Explicit person relations are
preferred; scalar source identity is a fallback only when unique. Conflicting
relation/participant identities are now rejected and reported. A fresh read-only
identity audit found **zero conflicts** and the same imported expertise vectors.
People with identical first names remain distinct source identities.

The approved sources remain `protohack_Players` and `protohack_Responses` in
`config/montreal-scope.json`. Mapping version:
`b35a99805379fd4c38c8d5e726b63d1bf5b2b8b80639c3b39eb4fefaf40237f1`.
This fingerprints the scope/taxonomy, not an immutable remote database revision.

| Capture observation | Result |
|---|---:|
| Capture time | 2026-11-04 20:07:23 UTC |
| Inspected records | 99: 41 person records and 58 responses |
| Scoped response records | 49 |
| Submitted inventories | 45; three repeats and one unresolved person reference |
| Eligible / imported people | 41 / 41 |
| Organisations / affiliations | 28 source-local mentions / 28 affiliations; no name-based merge |
| Shared expertise domains | 17; `other` and `__empty__` are not expertise domains |
| Offers | 41 answered; 211 selected domains |
| Needs | 40 answered, one skipped; 290 selected domains |
| Unmapped selections | One; counted, with no free text imported |
| Exclusions | Four legacy/non-submitted records; nine outside scope; one unresolved person reference |
| Off-diagonal W cells | 1,640 = 1,218 positive + 382 known zero + 40 unknown |

The 41×41 raw matrix retains its diagonal analytically. Gameplay renders those
41 self-pairings as excluded and prevents actions on them. Rows are providers,
columns requesters. A skipped need makes that person's complete request column
unknown, including cells with no observed positive match. A known empty vector
gives zeros over the shared vocabulary. Unknowns remain `None`; no random,
symmetrised or inferred matrix entries are added.

The new projection uses domain **codes**, not a cross-vocabulary text join.
`O`, `N`, `W` and evidence derive from the same source-ID reconciliation.
Snapshots predating answer-state capture display unknown scores until the
mapping is available; their positive declaration records remain inspectable.
The older low-level matrix bounds API remains unchanged for compatibility;
the player projection follows strict whole-answer-vector missingness.

When this mapping is present, network potential edges use the same current
matrix observations. This prevents older positive records retained by the
non-deleting importer from silently creating stale matrix/graph matches.
Manually declared capacities remain recorded but are not silently mixed into
the empirical expertise score. Contract and documented relationship edges are
unchanged and remain independently inspectable.

Private evidence is outside the public repository:
`~/.local/share/saddle-pathways/captures/2026-11-04-matrix/` contains the minimised
snapshot, coverage report, import report and count-only identity audit. The
mapping import preserved the two contracts and seven events present at that
time, appending one ordinary import event. Subsequent real-world UI inspection
verified that the current authoritative world and log remained unchanged.
No Notion write-back occurred.

## Full-screen presentation and navigation

`fullscreen.py` separates neutral `Route`/`Screen` state from `CursesViewport`.
The ordinary executable selects it for supported interactive POSIX terminals.
`curses.wrapper` owns terminal restoration; resizing redraws the current viewport.
Only the active viewport is updated. Screens do not append transcript blocks.
Object inspectors, cells, contracts, history, trajectories, details and help
share one explicit stack; Back restores the preceding route and its position.

The opening is title/motto → searchable first-name catalogue → **CHOOSE YOUR
PATH**. Only one concise simulation indication is needed. No source database,
world version, commit sequence or internal ID dominates the opening. `d` exposes
technical/source detail when requested; historical views are marked explicitly
and reject gameplay actions.

| Key | Behaviour |
|---|---|
| Arrows / Enter | Move and inspect a cell or selected object |
| `o` / `n` in matrix | Jump to your offer row / need column; both are always marked `*` |
| `/` | Search participants/lists; actor search includes affiliation labels |
| `v` in actor catalogue | Preview the source profile before simulating it |
| `x` | Alternative ecosystem views |
| `a` / `c` / `i` | Permitted object actions / contracts / grouped inbox |
| `m`, `e`, `g`, `s` | Choose or change path in the same world |
| `p` | Change simulated perspective without resetting state |
| `h` / `t` | Object history / recorded native trajectory |
| `v` during play | Verify replay against the saved world |
| PgUp/PgDn | Scroll content; positions survive Back |
| `:` | Enter commands such as `open latest contract`, `history K-001`, `act K-001` |
| `d` / `?` / `b` or Esc / `q` | Optional details / help / Back / quit |

Single-digit choices also work; larger lists support arrows and search. The
typed registry shares the mode aliases. `g` now consistently means Gathering;
use `graph`/`list` or `x` for Network. Filtered contract commands remain supported.
Opening an invalid historical reference leaves the preceding screen intact.

ASCII/monochrome play is available with `play --plain`, `NO_COLOR` and locale
fallback. Colour supplements labels and symbols. All ordinary labels pass
through the shared presentation vocabulary. Curses handles terminal dimensions;
matrix axes scroll around selection instead of shrinking the whole matrix.
Very narrow windows truncate labels/footer text, while `m`, `?` and Back remain
available. The tested resize is **52 columns × 18 rows**.

### Framework/dependency decision

[Textual screens](https://textual.textualize.io/guide/screens/) provide a managed
screen stack, and its [DataTable](https://textual.textualize.io/widgets/data_table/)
provides table cursors. [Rich's alternate-screen context](https://rich.readthedocs.io/en/stable/reference/console.html)
also supports replacing terminal output. Both were evaluated. This sprint uses
standard-library `curses` for the existing synchronous POSIX input boundary,
bounded redraw and resize/key handling, keeping the core installation free of
a new runtime dependency. The neutral screen and projection boundary remains
testable without curses. This is not a claim of Windows-native curses support.

`play --line-mode`, redirected input and unsupported terminals retain the
existing scriptable interface. That fallback retains its transcript layout;
it is not presented as the full-screen matrix experience. Developer hot-seat,
mock-manifest, fixture, replay and branch entry points remain separate.

The optional `terminal-test` extra adds **pyte** to reconstruct actual terminal
frames and **websockets** to drive ttyd's real transport. Neither is needed by
ordinary play. ttyd is an external test/hosting tool, not a runtime game dependency.

## Contract forms, policy inspection and inbox

The empirical proposal form separates title, purpose, proposing actor,
counterparty, offered contribution, requested contribution, optional conditions
and resource allocations. It does not reuse the generic scenario objective as
the contract title. With multiple objectives, linking a wider objective is an
explicit optional choice. The existing engine still requires an `objective_id`;
without an optional wider link it uses the world's collaboration context. No
optional-objective domain redesign has been introduced.

Suggested counterparty obligations grant no acceptance. The final review
explains who is affected and what will change. A successful proposal immediately
opens its inspectable graph node. A material amendment revises purpose,
contributions and conditions through the existing versioning rules: prior
receipts remain in history, and the new version requires renewed acceptance.
Synthetic regression scenarios also expose editable title/purpose/contribution
defaults in full-screen play, while retaining their registered parties, resource
constraints and governing policy. Selecting a different party explains the
fixture restriction instead of silently proposing to someone else.

The inspector shows Proposed by, Parties, Governing policy, Linked objective,
Resources and Evidence. Typed graph links follow each surrounding node.
Governance-policy inspection explains exact-version party consent, additional
approval threshold, required/eligible approvers and categories. Lifecycle and
verification outcome remain separately labelled.

Inbox groups are derived per actor: Proposals received, My proposals, Awaiting
my acceptance, Awaiting other parties, Other actionable requests. The proposer's
own unsigned proposal is explicitly their proposal, never simply incoming.
Negotiation/rejection are available alternatives, not misleading additional
requests; Other actionable requests contains approvals/execution/verification.

## Reproducible acceptance and regressions

```sh
.venv/bin/python -m pip install -e '.[test,terminal-test,trajectory]'
.venv/bin/python tools/playtest_matrix.py --output /tmp/saddle-matrix-pty
.venv/bin/python tools/playtest_matrix.py --output /tmp/saddle-matrix-ttyd --ttyd /path/to/ttyd
.venv/bin/python -m pytest -q
```

The same ordinary CLI is driven through a real PTY and a real loopback ttyd
WebSocket. Fictional records only enter public fixtures. Evidence includes
reconstructed active viewports, raw ANSI output, entered keys, SQLite history,
native trajectory export and a machine-readable result. Each run starts with a
new directory/world; neither touches the player's empirical simulation.

The demonstration selects Alex, chooses Ecosystem, selects Alex → Casey,
inspects source assertions, proposes, records Alex's initial acceptance,
switches to Casey, opens the received proposal, negotiates new contributions,
accepts the new version as each party, follows historical state, rejects action
in the historical view, checks trajectory/replay, switches modes, resizes,
quits and restarts to inspect the saved accepted contract. Final outcome:
**accepted / unverified**, two versions, old acceptance retained in history and
two current-version acceptances. No execution or verified outcome is fabricated.

Local acceptance artefacts:

- `/private/tmp/saddle-matrix-pty-verified/` — local terminal frames and restart.
- `/private/tmp/saddle-matrix-ttyd-final/` — ttyd 1.7.7 / libwebsockets 4.3.5,
  12 main viewport snapshots plus restarted contract inspection.
- `/private/tmp/saddle-matrix-line-fallback-01/` — retained entered line-mode flow.
- `/private/tmp/saddle-matrix-empirical-inspection/` — private real 41-person
  matrix/cell inspection; state and log unchanged.

A rendered browser check additionally exercised the splash, actor selection,
profile preview, matrix and cell inspection through ttyd. No external usability
study or production deployment is claimed.

Regression results: **125 passed** in the complete suite, including the test that
runs **58 original Hube tests**, frozen artefact hashes, actor spoofing, stale
writes, native trajectory round-trip, HTTP sessions and an actual standalone
wheel installation without neighbouring Hube/trajectory packages. After the
final scenario-form and invalid-history guards, **16 focused matrix/navigation
tests passed**, including the two additional cases: **127 distinct tests covered**.
The complete-suite HTTP checks ran with local socket permission; their earlier
sandbox bind failures were environmental, not test skips or relaxed assertions.
Compilation and `git diff --check` passed. No remaining test failures are known.

Known limits: unsupported terminals use line mode; synthetic source fixtures are
not genuine identity; matrix scores apply to the approved shared vocabulary;
Gathering needs registered objectives; Scenarios has no new coalition planner;
the empirical world remains simulation-only. Frozen M0 and later M1–M5 gates
are not relaxed by these interface improvements.
