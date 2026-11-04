# SADDLE PATHWAYS — The Commons Game

**A central authoritative engine to enforce decentralised decision rules.**

The project investigates how a collective becomes capable of acting together.
Possibility, promise, contract, commitment, authoritative commit, execution and
verified outcome remain distinct.

SADDLE PATHWAYS names the passage where a small transformation can change a
collective system's possibilities. The current sprint connects declared potential,
acknowledged contact and negotiated commitments, with independent direct contract
proposals. See the [implementation and mathematical audit](docs/13-complementarity-to-collective-action.md).

## Play

```sh
saddle-pathways
```

No subcommand, mock manifest or internal identifier is needed. The default private
world is **Montréal Commons**. Choose a person, then **CHOOSE YOUR PATH**:
Ecosystem, Gathering or Scenarios. Interactive play opens a full-screen viewport;
`play --choose-world` deliberately selects another saved simulation. All current
play is **SIMULATION MODE ONLY**.

```sh
# From this checkout without activating the virtual environment:
.venv/bin/saddle-pathways
# Portable decorations; source names remain unchanged in the engine:
.venv/bin/saddle-pathways play --plain
# Scripted or unsupported-terminal fallback:
.venv/bin/saddle-pathways play --line-mode
# Browse without assuming a role:
.venv/bin/saddle-pathways play --explore
```

Ecosystem opens the matrix explorer: uppercase **O** offers, **N** needs and
**W = O Nᵀ** directional matches. Rows offer expertise; W columns request it.
The fixed count bands remain **0, 1, 2–3, 4–6, 7–10, 11+**; `z` switches numbers.
`*` marks your axes, `?` unknown inputs. Partial observations show match bounds;
complete empty answers remain distinct from missing responses. `/` finds a
person or domain. First names are used throughout; stable `(1)`, `(2)` labels
distinguish different people sharing a first name without exposing surnames.

Enter a cell to inspect both directions and matching domains; `d` expands source
details. **j Invite to connect** records a simulated contact request; the recipient
can accept or decline through their inbox. **k Propose a contract** independently
opens explicit contributions and terms, with no invitation requirement. Draft
invitations can be saved and sent later. No real message or email is delivered.

`w` opens Hack's network renderer. **S** selects whole graph, player/person,
contract or invitation/connection scope; **L** filters layers; `[ ]` pages hidden
nodes. Counts distinguish rendered nodes/relationships from the full projection.
`3` enables an **experimental** depth-aware 3D camera (`r` yaw; `{ }` pitch);
planar mode remains the default. Coordinates carry no social or physical meaning.
`x` also offers People, Organisations and Resources.

The inbox has one entry per object, with decision badges and **F** filters. On a
contract, **y** accepts the current version, **j** negotiates, **R** rejects and
**X** withdraws where permitted. Amendments require renewed acceptance. Party
acceptance, institutional authorisation and verified outcomes remain distinct.

**Playing**, **Focus** and the selected relationship are separate contexts.
Following a person or contract never changes the simulated player. Breadcrumbs
and Back preserve the preceding relationship, selection and scroll position.
New agreements return to the relevant relationship with their contract link
selected; the other party has not consented merely because terms were proposed.

Use arrows and Enter, a displayed number, or `/` to search by first name. `a` shows
engine-permitted actions, `c` contracts, `i` the inbox, `p` changes the simulated
person, `h` shows history, and `?` explains the current screen. `m` chooses a path;
`e`, `g` and `s` switch modes in the same saved world. Single-key shortcuts act
immediately in full-screen play; `b` or Esc returns, preserving selection and
scroll. PgUp/PgDn scroll long content. Actor search also matches organisation
labels; `v` previews a profile before selection.
Contracts have stable short references such as `K-001`; `open latest contract`
also works through the `:` command prompt. Line mode retains entered commands
followed by Enter. Changing actors changes perspective, preserving the shared world.

The shared presentation dictionary supplies object symbols, colours and labels.
Ordinary play hides transaction hashes, source IDs and JSON. `metadata` exposes
source details on demand. Inferred complementarities remain labelled as potential
rather than documented collaboration or consent. A development-only simulation
authority issues a role when the player explicitly selects it; imported presence
or affiliation never grants real authority.

Reproducible fictional demonstrations (fresh output directories):

```sh
.venv/bin/python tools/playtest_collective_action.py --output /tmp/new-collective-playtest
# Add --ttyd /path/to/ttyd to drive the same journey through a loopback browser terminal.
.venv/bin/python tools/audit_matrices.py
```

## Montréal source coverage

The full approved capture inspected **41 person records and 58 response records**.
It imported **all 41 eligible people**, **28 source-local organisation mentions**,
**28 affiliations**, **211 declared capacities** and **290 declared needs**.
One additional submitted inventory has no resolvable person record. Three repeated
submitted inventories were reconciled by source identity; four unsubmitted legacy
trajectories and nine out-of-scope responses do not create additional people.
Thirteen profiles lack an affiliation. Organisation mentions have 26 distinct
labels and remain separate; no name-based identity merging is performed.

Private captures, the default saved world, earlier sample evidence and empirical
playtest transcripts live under `~/.local/share/saddle-pathways/`, outside this
repository. `SADDLE_DATA_DIR` selects a different private data directory. A fresh
public installation contains no private participant data; prepare an authorised
capture or deliberately choose one of the synthetic regression fixtures.

```sh
# Development capture: read-only Notion, complete query/property pagination.
python tools/capture_montreal.py --output /path/outside/repository/new-capture
# Offline import into an explicitly selected saved simulation:
saddle-pathways --db /path/to/world.sqlite start montreal-commons
saddle-pathways --db /path/to/world.sqlite import-ecosystem /path/to/ecosystem-snapshot.json
# Reproducible ordinary-play demonstration with fictional records:
python tools/playtest_playable.py --output /tmp/saddle-player-playtest
```

Live capture uses the existing sibling read-only adapter and its normal secret
configuration; install the optional `notion` extra to run it from this environment.
Snapshots retain only names, source-local affiliations and permitted structured
declarations. Contact details, credentials, raw responses and free-text Other
answers are not imported. There is no Notion write-back.

The matrix capture also retains minimal answer states and shared domain codes:
**41 answered offers, 40 answered needs, one skipped needs response**. Its
off-diagonal cells comprise **1,218 positives, 382 known zeros and 40 unknowns**.
Missing responses are never filled with zero. Source assertions remain distinct
from agreement or consent.

[Matrix-first sprint report, mode status, data audit and acceptance evidence](docs/11-matrix-first-navigation.md)
documents the earlier full-screen checkpoint. The current
[heatmap, relational navigation and renderer-reuse report](docs/12-relational-playtest.md)
includes the Jeanne playtest and the scenario/Gathering audit. Gathering has invitation/attendance
operations only in worlds with registered gathering objectives; Montréal currently
has none. Scenarios now has a distinct catalogue: the authored Montréal → Geneva
workshop framing is inspectable with provenance, possible desired conditions and
links to this world's simulation objectives. It is not presented as completed
strategy gameplay. Synthetic fixtures are labelled separately.

[Architecture, source coverage, design system, command repairs and regression evidence](docs/10-playable-terminal.md)
are documented together. The previous [two-person checkpoint](docs/09-montreal-collective-play.md)
is historical. Real authentication, genuine consent and institutional delegation
remain outside this simulation milestone.

Development follows [M0–M5](docs/MILESTONES.md). The [M0 Hube freeze](docs/04-M0-freeze.md)
is preserved. The trajectory/terminal checkpoint adds the smallest independently
tested integration, without claiming completion of the later gameplay milestones.
The [original specification](docs/COMMONS_SPEC_V0.1.txt) is retained verbatim.
The latest roadmap governs implementation order and terminal-first acceptance.

## Install the terminal laboratory

Python 3.11+. The core engine remains standard-library-only. Trajectory inspection
uses the optional, pinned `trajectory-engine 0.2.0` package and PyYAML; it needs no
Streamlit, Plotly, browser, graph renderer or numerical coordinates.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
# Optional trajectory inspection and development tests:
.venv/bin/python -m pip install -e '.[trajectory,test]'
# Optional tooling for actual full-screen PTY/ttyd acceptance:
.venv/bin/python -m pip install -e '.[terminal-test]'
```

The trajectory extra pins the audited repository commit
`757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`. The adapter checks the source hashes in
`commons_game/trajectory-lock.json`. It does not silently use uncommitted changes
from another local checkout. For an offline source installation, archive that
commit into a temporary directory and install it with `pip install --no-deps
--no-build-isolation /path/to/pristine/archive`; then install this project editable.
The build environment needs setuptools >=77 and PyYAML >=6,<7 for that route.

## Developer laboratory and retained scripted fixtures

The player viewport uses standard-library `curses` on supported POSIX terminals,
including ttyd. There is no new runtime dependency. `pyte` and `websockets` are
optional test tools: they reconstruct terminal frames and exercise ttyd's real
transport. The line interface remains available without either tool or curses.

```sh
.venv/bin/python tools/playtest_matrix.py --output /tmp/saddle-matrix-pty
# Install ttyd separately, then run the same acceptance through its transport:
.venv/bin/python tools/playtest_matrix.py --output /tmp/saddle-matrix-ttyd --ttyd /path/to/ttyd
# Jeanne's heatmap → profile → Hack network → contract → scenario → Back:
.venv/bin/python tools/playtest_relational.py --output /tmp/saddle-relational --colour
.venv/bin/python tools/playtest_relational.py --output /tmp/saddle-relational-ttyd --colour --ttyd /path/to/ttyd
# Explicit private read-only clone of an existing world; evidence stays outside the repository:
.venv/bin/python tools/playtest_relational.py --output /private/path/jeanne-playtest --world /private/path/commons.sqlite --colour
```

`--colour` in this test tool removes `NO_COLOR` only from its child process so
the colour path can be asserted. Ordinary play honours `NO_COLOR`; `--plain`
provides ASCII shading and the numeric toggle remains available. Hack's camera,
clipping, depth ordering and raster are extracted into a neutral component with
source fingerprints and parity tests. No new runtime dependency or neighbouring
Hack checkout is required.

From this directory:

```sh
# Developer-only scripted surface; ordinary play uses saddle-pathways alone.
.venv/bin/python -m commons_game play --developer-ui
# Explicit world and fixed local actor:
.venv/bin/python -m commons_game --db /tmp/subtle-world.sqlite play bilateral-logs --actor researcher
# Identity switching is a labelled development option:
.venv/bin/python -m commons_game --db /tmp/subtle-hotseat.sqlite play bilateral-logs --actor researcher --hot-seat
```

The installed `subtle-pathways` and existing `commons` commands expose the same
CLI. Select a scenario and local actor; explore Ecosystem, Gathering, Scenarios,
or History & Trajectories. Forms gather one action before submitting to the
engine. `b` returns, `0` cancels a form and `q` exits. Invalid input repeats the
question. The normal session cannot submit or switch to another actor. Local
identity selection is simulated identity, not authentication.

Every mode reads the same authoritative world. Available contract actions are
checked by the engine. Review exact versions, party acceptances, institutional
authorisation, reservations, obligations, execution notes and verification evidence.
Reopen the same database to see another local player's saved changes. Conflicting
submissions fail rather than overwrite history. No reference simulation runs
implicitly during interactive play.

## Minimal end-to-end trajectory integration

```sh
.venv/bin/python -m commons_game trajectory-demo bilateral-logs --export /tmp/subtle-trajectory.yaml
.venv/bin/python -m commons_game inspect-trajectory /tmp/subtle-trajectory.yaml
.venv/bin/python -m commons_game inspect-trajectory /tmp/subtle-trajectory.yaml --branch reject
.venv/bin/python -m commons_game --db /tmp/subtle-world.sqlite trajectory
```

The demonstration explicitly uses synthetic hot-seat play. It records negotiation,
all-party acceptance, institutional authorisation, resource reservation, execution,
reported fulfilment and independent verification. It exposes two hypothetical
alternatives from the same negotiated state, then checks native package YAML
round-trip and exact Commons replay. Existing export files are preserved.

The package's native document is `trajectory-plan/v2`. Its
`plan.commons_trajectory` extension is `subtle-trajectory/v1`, retaining the complete
ordered atomic log, commit/actor identities, source provenance and explicit branch
lineage. Native geometric primitives remain empty. No energy, physical uncertainty
or event coordinates are invented. Contract verification is never reduced to the
package's generic `Done` status. Imported trajectories are detached inspection
objects; there is no trajectory-to-authoritative-world write/import path.

Read the [package audit](docs/05-trajectory-audit.md),
[compatibility contract](docs/06-trajectory-compatibility.md),
[terminal architecture](docs/07-terminal-architecture.md), and
[checkpoint validation](docs/08-trajectory-terminal-validation.md).

The full entered terminal acceptance input is
`tests/scenarios/subtle_bilateral.stdin`; its synthetic transcript is
`tests/transcripts/subtle_bilateral.txt`. It reaches a verified outcome through
entered actions and explicit actor switches, not a hidden demo script.

## Earlier synthetic and browser scaffolds

```sh
python3 -m commons_game demo bilateral-logs
python3 -m commons_game demo montreal-geneva
python3 -m commons_game demo commons-gathering
python3 -m commons_game serve --port 8765
```

The optional legacy browser scaffold is at <http://127.0.0.1:8765>. Its splash offers optional original MIDI
music, followed by the declaration. The local browser play surface uses the same
Python engine as the CLI. Worlds persist independently in `.commons-worlds/`.
It is not the initial interactive development environment. Actor selection is
explicitly simulated hot-seat play, not production identity.
All demonstration actors/resources are fictional; no real institutional access or
finalised agreement is implied.

These three fixtures do not yet meet every M3–M5 acceptance gate. In particular,
the separate gathering fixture is not the planned contract-backed Hube upgrade.

## Inspect a saved world

```sh
python3 -m commons_game --db /tmp/commons-example.sqlite start bilateral-logs
python3 -m commons_game --db /tmp/commons-example.sqlite show agreements
python3 -m commons_game --db /tmp/commons-example.sqlite show log
python3 -m commons_game --db /tmp/commons-example.sqlite replay
```

`submit` reads one structured JSON command from stdin. Commands require a unique
`key`, an `actor`, a registered `kind`, and that command's declared fields. An
accepted exact retry is idempotent. Changed payloads with the same key conflict.
`--expected-version` on `submit` provides optimistic concurrency control. The
SQLite adapter additionally serialises reload, rule checks, reservations and append.

## Architecture

* `commons_engine/`: transaction machinery extracted from Hube, canonical mutation
  records, deterministic reconstruction and SQLite adapters.
* `commons_game/model.py`, `engine.py`: preliminary typed Commons records and
  domain rules. Reusable governance extraction remains an explicit M2 gate.
* `commons_game/scenarios/`: fictional seed worlds and objective/proposal data.
* `commons_game/projections.py`: multiplex view and missingness-aware `B`, `W`.
* `commons_game/player.py`, `tui.py`: fixed-actor terminal sessions and interaction.
* `commons_game/trajectory.py`: read-only adapter using actual trajectory-package
  document and serialisation APIs. Commons remains the sole replay/state authority.
* `commons_game/server.py`, `web/`: loopback HTTP adapter and presentation.
* `../game_hube/game/`: preserved Hube domain rules, clients, fixture and tests.

Contracts are first-class agreement nodes in graph projections. Acceptance receipts
bind actor, version and content digest. Institutional approval is separate.
All parties must explicitly accept; threshold authorisation does not replace
personal acceptance. Active commitments and held reservations are separate records.
Fulfilment reports do not satisfy objectives until designated independent verification.

State is reconstructed from ordered atomic before/after mutations. Commons commit
records also include state hashes and authorisation decisions. Hashes provide
internal consistency checks, not cryptographic identity or independent notarisation.

## Tests and installation

```sh
.venv/bin/python -m pytest -q
```

Tests require pytest and the trajectory extra for integration checks. Without the
optional package, those checks skip explicitly; the core and Hube still import
without it. HTTP integration tests open loopback sockets; a sandbox must
permit those. The suite includes competing-process SQLite reservations and runs
the original 58 Hube tests when the sibling checkout is available.

Commons installs independently. To run the optional sibling Hube regression world, install both local projects:

```sh
python3 -m pip install -e . -e ../game_hube
```

No blockchain, tokens, wallets, real financial escrow, legal enforcement or real
institutional data exchange is implemented. Scoped
delegation, contract-backed Hube and open-ended scenario trajectories remain
explicit later milestones, not implied capabilities.
