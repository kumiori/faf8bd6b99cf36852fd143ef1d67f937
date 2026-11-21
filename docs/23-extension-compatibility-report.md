# Public extension boundary: compatibility report

Validated on 21 November 2026. Commons now supplies its application behaviour
through the versioned `game-gamer/extension/v1` contract. The shared engine owns
the state, action validation, transaction boundary and event history.

## Delivered boundary

| Shared Game-Gamer | Commons application |
| --- | --- |
| `Extension`, `CommandDefinition`, `PolicyHook`, registration and exact-version resolution | `commons.application` version `1.0.0` |
| Engine construction, active command schemas, actor/session binding and atomic submission | Source-identity reconciliation command |
| `start`, `open`, `evaluate`, `submit`, `from_history`, historical inspection and `fork` | Profile correction policy and approved-profile synchronisation staging |
| Detached projections and generic rendering primitives | Questionnaire/complementarity/network projections |
| Public trusted `record_transition` and `transaction` setup boundaries | Imports, local role provisioning and source reconciliation setup |
| Optional TUI, configurable graph layers and route metadata | Montréal layer identity, palette, labels and navigation |

`CommonsGame` retains its public constructor and loaders, with no private engine
overrides. Unsupported payload fields and forged actor bindings remain rejected.
Missing or mismatched required extension versions fail explicitly. Candidates
with extra state tables or destructive record deletion are rejected before
commit; all application state remains representable in the existing event schema.

World-driven play works without a mission. New governed missions have identities,
version snapshots, independent adoption, challenges/revisions, contributions,
verification, completion, abandonment and reopening. Target locking constrains
that same runtime through configuration. Existing curated Commons missions retain
their previous semantics.

## Validation

| Check | Result |
| --- | --- |
| Game-Gamer package suite | **63 passed** |
| Commons complete suite | **274 passed**, including Hube compatibility, HTTP/session checks and independent installation |
| Existing local saved world, read-only | **25 events** loaded and replayed to the same state; original history preserved |
| Fictional independent Lantern Club application | Submit, membership rejection, actor binding, strict payload validation, exact retry, concurrent revision conflict, SQLite restart, portable restoration and isolated branching passed |
| Postcondition rejection / invalid extension state | No event or state change persisted |
| Independent installation | Fresh temporary virtual environment outside both trees; non-editable Game-Gamer, Lantern Club and Commons wheels |
| Dependency separation | Fictional app runs before Commons or TUI dependencies are installed; Commons runs without Hube or trajectory installed |
| Release reproducibility | Two clean source-copy builds produced identical wheel bytes; locked inventory matches current runtime sources |
| Text catalogue | 1,711 English keys validated; existing French fallback retained |
| Patch whitespace | `git diff --check` passed |

The Hube compatibility test runs the sibling's original suite and checks that its
engine still inherits the shared transaction runtime. The validation environment
was refreshed with a Hube wheel built from a temporary source copy to correct an
outdated editable launcher. No Hube source files were changed.

## Reproducible dependency

Commons requires `game-gamer[tui]==0.3.0`. Its release bundle includes
`vendor/game_gamer-0.3.0-py3-none-any.whl`, locked by
`config/game-gamer-release.json` and `requirements/game-gamer-release.txt`:

```text
SHA-256 8acd98406664c0a2f829b326a3558db051b7ca9c75a60755bef966cb626d0d00
```

`tools/build_game_gamer_release.py --check` verifies the artifact and its complete
runtime source inventory. The standalone installation test consumes this exact
artifact. The 0.3.0 bundle is local; it has not been published to a package
registry or pushed as an upstream release.

## Compatibility limits and follow-up

Legacy Commons saves continue through their existing `CommonsGame` /
`SQLiteStore(path, CommonsGame)` interface. Their `commons.0.1` schema is not
silently converted into the portable world schema. New portable definitions use
the complete `Collective` facade with `COMMONS_EXTENSION`. Converting a legacy
save into that schema remains an explicit future migration, rather than a rewrite
of its historical events.

Extension callbacks are trusted installed application code. Their version must
change when their interpretation changes, and supported historical versions must
remain installable. Callback purity and determinism are application obligations;
this contract does not sandbox arbitrary Python. Player payloads and saved
descriptors do not load executable code.

The governed mission API is available without a new gameplay interface. This
sprint does not redesign existing screens or claim full UI coverage for newly
registered custom commands. The existing optional terminal package remains
optional for non-terminal applications.

See [public API documentation](../game-gamer/docs/EXTENSIONS.md),
[migration notes](22-extension-boundary-migration.md) and the independent
[Lantern Club application](../game-gamer/examples/lantern-club/).
