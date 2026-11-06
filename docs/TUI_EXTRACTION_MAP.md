# Game-Gamer terminal extraction map

The pre-extraction reference is the Saddle Pathways full-screen and line-mode
client at `a849cdb`, running against the locally extracted Game-Gamer 0.1.0
engine. The matrix and collective-action scripts exercise the reference through
a real PTY with fictional data. The existing golden semantic baseline fixes
world, history, graph and inbox outputs independently of terminal presentation.

| Class | Source | Dependency and responsibility | Extraction boundary and coverage |
| --- | --- | --- | --- |
| TUI_REUSABLE | `terminal_input.py`, `fullscreen.CursesViewport` | POSIX keyboard and line input, curses painting, menus, prompts, scrolling, resizing | Game-Gamer TUI input and viewport. Existing PTY and scripted terminal tests exercise the host. |
| TUI_REUSABLE | `fullscreen.Route`, `Screen`, mode stacks and event loop | Local navigation, view model, selection and scroll; the host currently mixes route changes with actor binding | Shared navigation state and screen loop. The host still resolves route targets and supplies content. |
| TUI_REUSABLE | `fullscreen.matrix_screen`, `heatmap.py` | Matrix geometry and absolute colour bands; host expertise supplies values, axes, bounds and wording | Typed matrix view model, viewport and formatter. Montréal supplies its original O/N/W data. Matrix navigation, PTY and display-column tests cover the seam. |
| TUI_REUSABLE | `network_view.py`, `renderers/` | Read-only graph selection, labels, camera, clipping, raster and depth arbitration | Shared graph layout and raster. The host supplies its privacy-preserving labels. Preserve inspected camera/raster parity and background visibility tests. |
| TUI_REUSABLE | `fullscreen` inspector regions, menus, help and status | Explore links, decisions, feedback and scroll share a screen grammar | Shared screen and inspector widgets. Individual host detail sections remain host copy. |
| CORE | `Collective`, decision checks, history and projections | Authority, persistence, exact versions, canonical records, match semantics | Terminal calls the public collective API. Add actor-bound action discovery only where required. Semantic freeze and store tests protect these paths. |
| ADAPTER | `commons_game.player`, `fullscreen` and `play` host routing | Legacy actor binding, saved paths, per-world labels, command templates and UI integration | Keep the compatibility layer in Saddle Pathways and have its full-screen client consume the shared TUI. |
| APPLICATION | `play.py`, `tui.py`, `commands.py` | Legacy line-mode transcript and grammar, proposal defaults, onboarding, scenario catalogue, trajectory inspection | Keep established workflows with the host. The independent app uses public actions and world data, including a host-supplied binding. |
| PROTOTYPE | Experimental yaw and pitch camera | Alternative geometry over the same read-only graph | Keep explicitly experimental. Camera transforms share node IDs, relationships and raster semantics. |
| DO_NOT_EXTRACT | Imported Montréal data, Notion transport, questionnaire matrix interpretation, terminal branding, private stores | Host-specific content, authoring and identity policy | Exclude from the distribution. |

Current keys are taken from `FullScreenTerminal.handle`, `CursesViewport.key`
and the host command registry. The top bar is m/e/g/s/c/i/p, with Enter, b/Esc
and ? for contextual inspection, Back and help. The matrix retains O/N/W,
arrows, Enter, o/n, z, w and /. Network retains Tab, S/L, [ and ], f, +/−, r,
and experimental 3 and braces. Agreement decisions retain y/j/R/X where
applicable. Forms reserve printable characters for input.

## Delivered package

```text
game_gamer/
├── cli.py
├── history/ · model.py · persistence/ · projections/ · runtime/ · schema/
└── tui/
    ├── application.py · forms.py
    ├── navigation.py · screen.py · viewport.py · keyboard.py
    ├── matrix.py · bands.py · text.py · objects.py
    └── network.py · renderers/
```

The [terminal guide](../game-gamer/docs/TUI.md) documents `TerminalGame`, its
viewport, matrix and network API, keyboard controls and the independent
rehearsal example. The additive `Collective.action_options` query exposes
revision-bound validation results for existing objects. The application uses
public projections, action evaluation and submission. Saddle Pathways
supplies legacy identity bindings, line-mode commands, the original workflow
and labels, scenario and source views, and its O/N/W interpretation.

## Acceptance

| Gate | Evidence |
| --- | --- |
| Semantic and save compatibility | 184 tests passed. This includes the frozen 0.1.0 trajectories, original compatibility regressions and HTTP integration over loopback. The installed 0.2.0 wheel reopened both a SQLite world and portable history produced by the installed 0.1.0 wheel. |
| Terminal parity | Both Saddle Pathways PTY scripts ran before and after extraction. The original and restart key sequences, 30 screen destinations, committed commands, final world and graph, inboxes, available actions and replay results matched. Comparison normalised random command and session IDs and excluded their dependent state digests. Both raw histories separately passed digest-validated replay. |
| Geometry | Tests cover two and three display columns, three detail levels, ANSI, accented and wide labels, overflow, empty and 120-by-120 matrices, directional selection, draft preservation, layout bounds and dense disconnected backgrounds. The installed CLI also passed a colour PTY smoke test covering resize, detail levels and planar and perspective views. |
| Standalone play | A clean wheel installation, launched from an unrelated repository, inspected three actors, explored the network and directional matrix, sent and accepted contact and attendance invitations, negotiated two versions of an agreement, recorded party and policy approvals, fulfilled and verified, and reopened the saved world. |
| Packaging | Clean base and `[tui]` installations resolved from the built artifacts. The base environment imported and ran the engine without `wcwidth`. The extra resolved `wcwidth` and launched the CLI. A second repository also installed `v0.2.0` from a temporary tagged bare Git repository. |
| Publication | The wheel and source distribution are built locally. External publication and an install from the published tag require a configured package remote. |
