# Commons extension boundary migration

Commons registers `commons.application` version `1.0.0` against
`game-gamer/extension/v1`. Its source-identity command, profile approval policies
and questionnaire/topology projections are application callbacks. Game-Gamer
owns validation, atomic transactions, event ordering, persistence and replay.

`CommonsGame` remains available for existing callers. Its constructor supplies
the registered extension to the public `CollectiveEngine` constructor. It has
no private engine method overrides. Host imports, role provisioning, mission
installation and profile synchronisation use `record_transition` and the
public transaction context. Generic rendering receives Montréal layer styles,
labels and navigation metadata from Commons configuration.

## Existing saves

Open existing Commons logs with `CommonsGame` or an existing
`SQLiteStore(path, CommonsGame)`. Existing genesis events and historical prefixes
retain their original bytes and digests. The legacy loader retains the original
Commons schema and its construction rules.

Legacy logs predate extension descriptors. The application loader supplies the
Commons ruleset explicitly. An application-specific command, or a policy hook
that changes the proposed state, adds the required extension descriptor in that
new event. Earlier history is preserved. A generic loader encountering that
required descriptor must have the matching registered extension or receive it
explicitly. Historical extension versions must remain available when their
saved worlds are supported.

Portable world definitions use `Collective.start(..., extension=COMMONS_EXTENSION)`.
Their genesis state declares the exact extension requirement. Their histories
support the complete portable `open`, `from_history` and `fork` API. Legacy
Commons-format logs retain their existing lower-level save/replay interface.

Existing curated Montréal missions preserve their `open` status, contribution
rules and verification semantics. Newly proposed governed missions use the
versioned mission lifecycle documented in the shared package. Entering a world
continues to work before any mission is created. A target lock is supplied as an
explicit game configuration.

## Install the reproducible release bundle

Commons requires `game-gamer[tui]==0.3.0`. The local release bundle includes the
Game-Gamer wheel in `vendor/`, the wheel hash in
`config/game-gamer-release.json`, and a hash-checked requirements file.

```sh
python -m pip install --no-deps --require-hashes -r requirements/game-gamer-release.txt
python -m pip install .
```

For offline use, prepare a wheelhouse containing that verified wheel, the Commons
wheel and the terminal dependency wheels, then install using `--no-index` and
`--find-links`. The independent installation test follows this path from a fresh
virtual environment outside both source trees. Public registry publication is a
separate release operation. The bundled wheel supplies the reproducible local
release required by this application.

## Migration checks

Run the shared package suite and the Commons suite. The independent Lantern Club
package exercises one custom command, policy and projection across rejection,
retry, restart, replay and branching. Commons fixtures exercise profile policies,
source reconciliation, contracts, reservations and historical reconstruction.
Hube compatibility exercises the existing shared transaction API and launcher.

The current development environment previously had an outdated Hube editable
installation whose launcher omitted `game_gamer_semantics`. Validation refreshes
that installation from a wheel built from a temporary copy of the current Hube
package. The Hube source checkout is preserved.

See the [compatibility report](23-extension-compatibility-report.md) for the tested
release artifact, validation results and remaining migration limits.
