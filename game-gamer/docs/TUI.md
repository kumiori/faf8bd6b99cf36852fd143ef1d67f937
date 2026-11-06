# Game-Gamer terminal extension

Install `game-gamer[tui]` to enable the standalone terminal. The extra supplies
`wcwidth` for Unicode column measurement. The semantic API remains usable with
the base distribution. The full-screen viewport uses curses where supported,
with a scriptable line viewport for streams and other terminals.

```sh
python -m pip install 'game-gamer[tui]'
game-gamer play examples/minimal_collective/world.json --db rehearsal.sqlite
```

Start with the [fictional rehearsal world](../examples/minimal_collective/world.json).
On the matrix, move to Jo's row and Sam's column, then inspect the inferred
rehearsal-room match. Simulate Jo and press **j** to propose contact. Switch to
Sam with **p**, open the inbox with **i** and accept the invitation. In
Gathering, Sam can invite Jo to attend. As Sam, press **k** in Scenarios to
propose the rehearsal agreement. After any revision, Sam and Jo each accept the
new terms. Pat records stewardship approval, a party activates, both parties
record execution and fulfilment, and Pat independently verifies the result.
Run the same command again to resume the saved collective.

## Controls and rendering

| Context | Keys |
| --- | --- |
| Global | **m** Paths, **e** Ecosystem, **g** Gathering, **s** Scenarios, **c** Contracts, **i** Inbox, **p** Player, **?** Help |
| Navigation | **Enter** Inspect, **b/Esc** Back, arrows Select, PgUp/PgDn Scroll, **h** History |
| Matrix | Arrows move, **Enter** inspects, **+/-** changes detail, **Home** returns to origin, **f** fits around selection, **z** toggles numbers |
| Network | **Tab** canvas/list, **S** scope, **L** layers, **B** background, **[ ]** page, **f** centre, **+/-** zoom, **r** rotate, **3** experimental 3D, **{ }** pitch |
| Decisions | **Tab** separates decisions, links and details. **y** Accept, **j** Amend, **R** Reject or decline, **X** Withdraw. Line mode accepts a displayed `a1`, `a2`, and so on. |

The matrix has Compact (two display columns), Standard (three) and Detailed
(variable width) levels. Compact and Standard use an absolute band when heatmap
display is active. In numeric mode, `+` marks a score wider than the cell;
inspection exposes the exact value. A prefix `>` marks selection and `*` marks
the player's axis. The viewport computes visible rows and columns independently
of the detail level. Direction and actor IDs remain in the logical cell.
Saddle Pathways supplies its own O/N/W values and bounds. The independent example
counts inferred match records and displays absent matches as unknown.

Planar and perspective views use the same focused graph and raster.
`layout_graph` returns terminal coordinates and supports node hit testing.
The default Dim background gives disconnected actors a ring and other
off-scope actors a dot. Hidden omits the backdrop and Full draws it at normal
brightness. Dense rosters use deterministic bins, with digits for counts two
through nine and `+` for larger bins. Foreground cells have priority.

Forms hold local inputs until a confirmed submission. Esc (or `/cancel` in
line mode) offers a discard choice, and resizing keeps the current prompt
buffer. The explicit **Save shared draft** invitation choice submits an
authoritative draft inside the world.

## Embedding

```python
from game_gamer import Collective, SimulationBinding
from game_gamer.tui import TerminalGame

game = Collective.start(definition, path="rehearsal.sqlite")
binding = SimulationBinding(scope_id=game.scope_id, actor_id="sam")
TerminalGame(collective=game, binding=binding).run()
```

Pass `hot_seat=True` to permit deliberate simulated role switching. A host
can supply a viewport for automation or embedding. `NavigationState` stores
local routes, scroll, selection and per-mode context. `Screen` and
`inspector` model menus, decisions, links and details. `MatrixView`,
`MatrixCell`, `MatrixViewport`, `format_cell` and `render_matrix` are in
`game_gamer.tui.matrix`. `focus_graph`, `layout_graph` and `draw_graph`
are in `game_gamer.tui.network`.

The terminal reads the public `Collective.project`, `inbox` and
`action_options` methods. `action_options(binding=..., at=...)` returns one
revision and candidate decisions with rule errors for disabled actions. It
reuses engine validation, while `evaluate` checks a completed submission and
`submit` applies it through the atomic store. Disabled decisions are
inspectable in Details. Historical views use a committed prefix and remain
read-only in the terminal.

## Raster provenance

The camera and raster retain the inspected Protocol Hack implementation from
`temporal_graph/renderers/terminal/projection.py` at commit
`74f0cfab96cebf1a7b453227423596b72bc7a802`, source SHA-256
`a692f1520d8cc893445dd9e6fa4c2ba41ce7af7f951b655695629daec321073c`.
The adapter uses scalar camera arithmetic, neutral text spans and explicit
visual graph records. It adds fitted coordinates, graph styles and markers for
unknown direction. Camera and raster parity are covered by the host suite.
