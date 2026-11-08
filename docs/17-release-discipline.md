# GAME-GAMER 0.1.x release discipline

Release objective: **playable Montréal network reconstruction**.
The release journey is **Enter → Discover → Connect → Observe**. Its state
changes are attributed historical recollection claims. Recording a recollection
does not grant consent, accept an invitation or establish verified historical fact.

## Decision rule

Choose one decision for an identified candidate, with dated evidence:

- **Release:** all mandatory gates pass and the known limitations are visible.
- **Revise:** no invariant violation is known, but required behaviour, evidence or
  release preparation is incomplete.
- **Block:** an invariant is violated or compatibility is broken. Repair the
  blocker and repeat the affected checks before reconsidering release.

A passing scripted journey establishes an executable path. First-time-user
completion requires a separate observation of an unfamiliar user following the
displayed instructions. Earlier test counts do not certify a later candidate.

## Mandatory gates

| Area | Acceptance requirement |
| --- | --- |
| Journey | Enter the exercise, discover another participant, explicitly confirm a recollection and observe its attributed network consequence. |
| No duplicate claims | Exact retries return the original result; a fresh submission cannot add another active claim for the same author, target, kind and context. Identity aliases must not bypass this rule. Retraction preserves history and permits a corrected claim. |
| No implicit consent | A unilateral recollection remains unilateral. Reciprocal accounts derive mutual recollection only. New contact requires a distinct invitation and recipient response; contracts retain their own acceptance rules. |
| Replay preserves state | Every tested history prefix reconstructs the same state and projections. Restart retains claims, disputes, retractions, event order and attribution. |
| Graph provenance | Historical sources, unilateral claims, mutual recollections, disputes, prior relationships, invitations, accepted contacts and inferred matches remain distinguishable, with source/claim/event references. |
| Verification | Run unit, integration, terminal interaction and persistence checks. Record performance measurements with dataset size, operation, samples and environment. Report failures and infrastructure restrictions separately. |
| Experience | Observe a first-time user completing Enter → Discover → Connect → Observe from the displayed instructions; record assistance and whether they understood the consequence of Connect. |
| Compatibility | Existing worlds remain operational and existing saves remain readable, with unchanged replay semantics. Check frozen trajectories and an existing save without rewriting it. |
| Abstraction | The participant directory is reusable. The exercise lifecycle has a reusable boundary for entry, activity, observation and return, with the Montréal wording and context supplied by the host. |
| Limitations | Historical whiteboard data has not yet been imported. Motivations are incomplete; missing values remain explicit. |

## Assessment — 7 November 2026

**Decision: Block.** The candidate permits duplicate recollections after identity
merging. Test failures, version alignment and incomplete experience/lifecycle
evidence also require revision.

This assessment covers the local working tree based on
`ffaf0abc3cdd93df06cac7d507b2879d593bdf06`, including the pre-existing uncommitted
reconstruction and curation changes. It does not certify that base commit alone
or an immutable release artefact. No version, tag or publication was created.
Other working-tree files continued changing during the assessment; rerun the
gates on the final fixed candidate. The duplicate reproducer still succeeded
when this report was completed.

The requested release line is **GAME-GAMER 0.1.x**, but
[`game-gamer/pyproject.toml`](../game-gamer/pyproject.toml) declares **0.2.0**, and
the host requires `game-gamer[tui]>=0.2.0,<0.3`. The host's own `0.1.0` version is
a separate package version. Resolve the intended release line and dependency
contract together before producing an artefact.

### Invariant blocker: duplicate claims through a merged identity

Observed through the public `Collective` / `ActionSubmission` API using fictional
participants:

1. `alias` records a recollection of `b` in context `forum`.
2. A curator previews and explicitly confirms the identity merge `alias → a`.
3. `a` records a recollection of `b` in that same context using a new action ID.
4. The second submission succeeds with no errors. Two active claims project as
   `a → b`, both in the recollection layer.

[`runtime/reconstruction.py`](../game-gamer/src/game_gamer/runtime/reconstruction.py)
checks duplicates against raw source/target IDs. The curator mapping resolves
those IDs later in the graph. Submission must account for resolved identity
without rewriting the original claims or their provenance. Cover both merged
authors and merged targets, reciprocal accounts, disputes, retractions, retries,
restart and merge reversal when repairing this boundary.

Reproduce from this checkout:

```sh
PYTHONPATH=game-gamer/tests .venv/bin/python -B - <<'PY'
from test_curation import start
from test_reconstruction import submit
from game_gamer.runtime.curation import merge_preview

game = start()
assert submit(game, 'duplicate', 'recall_connection', 'first',
              target_id='b', context_id='forum')['ok']
preview = merge_preview(game.project('world'), 'duplicate', 'a')
assert submit(game, 'curator', 'merge_profiles', 'merge', source_id='duplicate',
              target_id='a', reference='Fictional confirmed identity',
              identity_confirmed=True, preview_digest=preview['digest'])['ok']
result = submit(game, 'a', 'recall_connection', 'second',
                target_id='b', context_id='forum')
print('Duplicate accepted:', result['ok'])
print([(e['source_id'], e['target_id'], e['layer'])
       for e in game.project('network')['edges']])
PY
```

### Verification results

Environment: Python 3.11.12, macOS arm64, local source checkout and `.venv`.

| Check | Observed result | Release interpretation |
| --- | --- | --- |
| Host suite, initial sandbox run | 173 passed, 6 failed | Four HTTP bind failures and one dependency-download failure were infrastructure restrictions; one stale Hube-count assertion remained. |
| HTTP and clean wheel installation rerun with required access | 6 passed | HTTP integration and isolated installation passed. |
| Standalone Game-Gamer suite | 22 passed, 2 failed | Both curation tests fail at the reverse-merge action envelope; the helper omits `merge_id` when choosing `target_id`. |
| Hube suite invoked by compatibility check | 67 passed, 1 skipped | Subprocess succeeded; the host test still asserts the literal text `58 passed`. The skipped Hube case remains unverified. |
| Reconstruction PTY | Passed | Entry, explicit actor choice, directory/profile, confirmed claim, reciprocal recollection, network observation, 52×20 / 144×34 resize and replay. |
| Matrix PTY | Passed | Versioned contract negotiation, history, mode switching, resize, restart and trajectory replay. |
| Collective-action PTY | Passed | Separate invitation and direct-contract paths, recipient acceptance, network/matrix navigation, restart and replay. |
| Existing local Montréal save | Passed read-only inspection | 43 people, 71 actors, 12 events; world and network equal after replay; SQLite file hash unchanged. |
| Saved-world screen widths | Passed | Directory, Profile and Network lines fit at 40×16, 52×20, 100×32 and 144×34. This is a width check, not first-time-user acceptance. |
| Whitespace check | `git diff --check` passed | No whitespace errors in tracked changes at inspection. |

The standalone failures do **not** demonstrate that merge reversal itself is
broken: a direct submission with `target_id=merge_id` succeeded. Correct the
test helper and rerun the tests. Replace the host's fixed Hube test-count check
with an assertion about successful test completion while retaining the frozen
acceptance artefact and trajectory checks.

The passing reconstruction tests cover raw-ID duplicate rejection, exact retries,
actor binding, separate contact consent, disputes, retractions, concurrent SQLite
submissions, restart, historical prefixes, detached directory models and source
provenance. They do not cover the merged-identity duplicate reproduced above.
The host's frozen trajectory and frozen Hube artefact checks passed in the host
run, within the aggregate result reported above.

### Performance measurements

Operation: revision check, selection movement and two reconstruction screen
builds at 144×34, after an initial screen build; 100 samples per dataset.

| Dataset | Median | p95 | Maximum |
| --- | --- | --- | --- |
| Fictional reconstruction PTY save, three people | 3.207 ms | 8.549 ms | 124.424 ms |
| Existing Montréal save, 43 people / 71 actors / 12 events | 4.209 ms | 5.650 ms | 18.011 ms |

These are local frame measurements, not measurements of claim writes, cold
startup, remote clients or larger worlds. No performance acceptance budget has
been agreed. Read-only checks left the existing saved SQLite bytes unchanged.

### Experience and reusable boundaries

The scripted reconstruction journey passed. No unfamiliar user's completion was
observed during this assessment, so the first-time-user gate remains open.
For that check, start at entry with an explicit simulated participant selection,
ask the user to find another participant, inspect their profile, record a
recollection and explain the resulting network observation. Record any help
needed and check that they do not interpret the claim as the other person's
consent.

`ParticipantDirectory`, profile/filter models and deterministic portraits are
reusable package components. `NetworkReconstructionExercise` supplies a reusable
presentation definition, but introduction/entry transitions, action dispatch and
return navigation currently live in the Montréal host controller. A reusable
exercise lifecycle across hosts has not yet been demonstrated; this gate is
partial. It does not require a second authoritative event history.

Historical whiteboard import capability exists, but no actual whiteboard data
was imported for this assessment. Motivations remain incomplete and are displayed
as **Not yet recorded**. These declared limitations can remain in a scoped
release once the mandatory gates pass.

### Work required before another decision

1. Repair canonical-identity duplicate detection while preserving raw claim
   attribution and history; add the regression coverage described above.
2. Correct the two test-harness problems and obtain passing host and standalone
   suites on the final candidate.
3. Align the release line and dependency metadata.
4. Complete the first-time-user observation and demonstrate or finish the reusable
   lifecycle boundary.
5. Record the final performance measurements and remaining verification evidence
   against an identified final candidate. A performance budget would make future
   regression decisions more explicit.

## Reproduction commands

Run from the repository root with test, TUI and terminal-test dependencies
installed. HTTP tests require loopback access; the installation test may need
package-index access for `wcwidth`.

```sh
.venv/bin/python -m pytest -q
(cd game-gamer && ../.venv/bin/python -m pytest -q)
.venv/bin/python -m pytest -q tests/test_http.py tests/test_standalone_install.py

release_output=$(mktemp -d /private/tmp/game-gamer-release.XXXXXX)
.venv/bin/python tools/playtest_reconstruction.py --output "$release_output/reconstruction"
.venv/bin/python tools/playtest_matrix.py --output "$release_output/matrix"
.venv/bin/python tools/playtest_collective_action.py --output "$release_output/collective-action"
.venv/bin/python tools/benchmark_playability.py \
  --db "$release_output/reconstruction/reconstruction.sqlite" --samples 100
git diff --check
```

This assessment's fictional terminal artefacts are under
`/private/tmp/game-gamer-release-20261107-reconstruction`,
`/private/tmp/game-gamer-release-20261107-matrix` and
`/private/tmp/game-gamer-release-20261107-collective-action`. Temporary artefacts
are local evidence and may be removed by the operating system.
