# The Commons Game

**A central authoritative engine to enforce decentralised decision rules.**

The project investigates how a collective becomes capable of acting together.
Possibility, promise, contract, commitment, authoritative commit, execution and
verified outcome remain distinct.

Development follows [M0–M5](docs/MILESTONES.md). The current accepted milestone is
the [M0 Hube freeze](docs/04-M0-freeze.md); later work is preliminary scaffolding,
with its gaps recorded explicitly. The [original specification](docs/COMMONS_SPEC_V0.1.txt)
is retained verbatim. The latest milestone roadmap takes precedence where it
changes implementation order.

## Run the existing local scaffold

Python 3.11+, standard-library runtime. From this directory:

```sh
python3 -m commons_game demo bilateral-logs
python3 -m commons_game demo montreal-geneva
python3 -m commons_game demo commons-gathering
python3 -m commons_game serve --port 8765
```

Open <http://127.0.0.1:8765>. The introductory splash offers optional original MIDI
music, followed by the declaration. The local browser play surface uses the same
Python engine as the CLI. Worlds persist independently in `.commons-worlds/`.
Actor selection is explicitly simulated hot-seat play, not production identity.
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
python3 -m pytest -q
```

Tests require pytest. HTTP integration tests open loopback sockets; a sandbox must
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
