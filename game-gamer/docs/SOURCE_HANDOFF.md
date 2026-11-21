# Standalone source handoff — 7 November 2026

This repository contains the reusable Game-Gamer package, extracted from the
local `game_commons/game-gamer` working tree based on Commons commit
`ffaf0abc3cdd93df06cac7d507b2879d593bdf06`. It includes the subsequent package
reconstruction, curation and practice components present at snapshot time.
The existing package version remains **0.2.0**.

The standalone repository includes source, documentation, tests and fictional
examples. It excludes the Commons host application and its Git history,
empirical participant data, databases, local captures, caches and old builds.
The renderer attribution in [TUI.md](TUI.md#raster-provenance) is retained.

## Validation

Validation on macOS arm64 with Python 3.11.12:

| Check | Result |
| --- | --- |
| Snapshot test suite, explicit `PYTHONPATH=src` | 30 passed |
| Source distribution and wheel, built with the setuptools PEP 517 backend | Passed |
| Wheel rebuilt from the source distribution | Passed |
| Distribution contents | Package modules and `exercises/tutorials.json` included; no host modules or databases |
| Fresh environment, core wheel with no dependencies | Fictional example and all three practice sessions passed, including replay |
| Optional terminal with `wcwidth` 0.2.13 | CLI help, line-mode launch, SQLite restart and replay passed |
| Installed-wheel suite, isolated Python with pytest 9.2.0 and no source path | 30 passed |
| Host extraction baseline, M0 artefacts and mechanics freeze against the snapshot | 9 passed |
| Installed dependency consistency | `pip check` passed |

The installed-wheel suite ran from outside the source checkout using `python -I`.
The base environment confirmed that neither the Commons host nor `wcwidth` was
installed before optional terminal validation. Generated distributions and
environments are local validation artefacts and are not committed.

The merged-identity duplicate regression is covered by
`test_canonical_claim_ownership_and_duplicates_follow_author_and_target_merges`.
The earlier curation helper error is fixed by including `merge_id` in the action
target selection. Neither the earlier failing test counts nor the earlier Block
assessment describes this snapshot without revalidation.

## Application release boundary

Pushing the reusable source package does not certify the full Montréal user
experience. First-time-user observation, historical whiteboard import and
complete motivation data remain application concerns. Authority is simulated;
recollections and mutual recollections do not imply present consent, accepted
contracts or verified historical fact. This handoff creates no release tag and
does not publish a distribution to a package index.
