# Subtle Pathways — The Commons Game

**A central authoritative engine to enforce decentralised decision rules.**

The project investigates how a collective becomes capable of acting together.
Possibility, promise, contract, commitment, authoritative commit, execution and
verified outcome remain distinct.

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
.venv/bin/python -m pip install -e '.[trajectory,test]' -e ../game_hube
```

The trajectory extra pins the audited repository commit
`757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`. The adapter checks the source hashes in
`commons_game/trajectory-lock.json`. It does not silently use uncommitted changes
from another local checkout. For an offline source installation, archive that
commit into a temporary directory and install it with `pip install --no-deps
--no-build-isolation /path/to/pristine/archive`; then install this project editable.
The build environment needs setuptools >=77 and PyYAML >=6,<7 for that route.

## Play in the terminal

From this directory:

```sh
.venv/bin/python -m commons_game play
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
  document and serialization APIs. Commons remains the sole replay/state authority.
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

For installation into a development environment, install both local projects:

```sh
python3 -m pip install -e . -e ../game_hube
```

No blockchain, tokens, wallets, real financial escrow, legal enforcement or real
institutional data exchange is implemented. Empirical Montréal import, scoped
delegation, contract-backed Hube and open-ended scenario trajectories remain
explicit later milestones, not implied capabilities.
