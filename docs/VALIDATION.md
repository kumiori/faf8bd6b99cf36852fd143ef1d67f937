# M0 validation — 3 November 2026

## Fresh regression evidence

| Check | Result |
|---|---|
| Original Hube suite | 58 passed |
| Final Commons checkpoint suite | 36 passed |
| Hube suite invoked from Commons compatibility test | All 58 original tests passed |
| Shared engine identity | Hube `Game` is a `commons_engine.WorldEngine` subclass |
| Frozen Hube acceptance artefacts | 6/6 SHA-256 hashes unchanged |
| Original Hube inspection manifest | Only four reviewed extraction/dependency files differ; `game/_shared.py` was added |
| Hube gameplay edits after checkpoint | None |
| Commons gameplay edits during M0 realignment | None |

Commands run with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider` and temporary
pytest output under `/private/tmp`. HTTP integration tests were run with loopback
socket permission. Infrastructure failures are not reclassified as domain failures.

```sh
# In ../game_hube
pytest -q -p no:cacheprovider --basetemp /private/tmp/commons-m0-hube-freeze

# In game_commons
pytest -q -p no:cacheprovider --basetemp /private/tmp/commons-m0-final
```

The Commons suite covers bilateral and multilateral fixtures, version conflicts,
unauthorised approval, missing institutional authorisation, resource conservation,
two competing processes using SQLite, idempotency, expiry, execution before
fulfilment, independent verification, replay/hash validation, declarations,
missingness-aware matrices, gathering attendance, actual HTTP submissions,
actor-session isolation and the real MIDI score parser. The new M0 test guards
the original Hube acceptance fixtures against silent replacement.

## Earlier UI evidence, not an M0 gameplay claim

Before this milestone realignment, the local scaffold was inspected in the browser:
introductory splash, exact declaration, optional MIDI sound, ecosystem, versioned
negotiation, separate authorisation, activation, execution, reported fulfilment,
independent verification and a gathering invitation/response. A 390-pixel layout
was checked without horizontal overflow. `splash-preview.jpg` is retained evidence
from that work. No new browser behaviour was added during M0.

That evidence does not establish an empirical Montréal import, contract-backed
Hube integration, scoped delegation or alternative mentoring strategies. Those
remain the explicit later gates in `MILESTONES.md`.

## Checkpoint provenance

The initial commits were created before M0 realignment edits:

* Commons: `f082967d47c87e97f4a62dbe7536b6f3743c097b`.
* Hube: `52fbfe1d74c1c46d804b45a39e25231399f090bc`.

`M0_BASELINE.json` records those refs and the frozen acceptance hashes. The M0
completion is recorded separately under each repository's `milestone/M0` tag.
Unrelated Hube `.DS_Store`, `ui-tests/` and `zine/` files were left untracked and
untouched. No existing saved world was reset or migrated.
