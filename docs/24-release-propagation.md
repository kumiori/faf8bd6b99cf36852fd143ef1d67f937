# Game-Gamer release propagation

Game-Gamer's [release protocol](../game-gamer/docs/RELEASES.md) publishes immutable
wheel and manifest assets. Commons and Hube are registered consumers. Their
scheduled/notification workflows create draft upgrade proposals, independently
validate the candidate and require a review before adoption.

The Commons production dependency remains pinned to its reviewed 0.3.0 wheel
until the upgrade PR is accepted. Developing 0.3.1 under `game-gamer/` does not
replace that bundled artifact. The lock checker compares package identity and
checksum; it additionally compares runtime sources when the checkout and pin
refer to the same version. New release manifests do not rewrite the older wheel.

Bootstrap publication uses committed application sources and excludes unrelated
untracked art, generated output and private databases. Hube's source snapshot is
`a98aab5`; its unrelated local edits are preserved. Its initial dependency remains
the exact historical Game-Gamer Git commit until the proposal changes the pin.
Release tooling copies live under `.github/game-gamer/`, outside the gameplay
runtime, with no dependency on sibling directories.

The updater preserves the previous wheel and application extension versions.
Only synthetic worlds are created by compatibility probes. Existing fixture
histories and canonical application trajectories supply legacy replay coverage.
The main branch review gate and required compatibility status prevent an
automated update from being adopted merely because an artifact was published.

The consumer's ordinary application suite remains part of the gate. Optional
vision, browser or sibling-only tests can be skipped in an isolated host; their
actual output is attached. Such skips do not establish optional-feature coverage.
Engine compatibility and application mechanics must pass.

The hosted publication and PR links, test outcomes and known restrictions will
be recorded after exercising the first real release.

## First hosted release — 21 November 2026

[Game-Gamer 0.3.1](https://github.com/kumiori/113a4cce0c9191877e82b1a0b6767a70/releases/tag/v0.3.1)
is published as an immutable release (ID `453719371`), with all five required
assets. Its wheel SHA-256 is
`c9a5a3bacefc8b580f399a8d8a6d6d3656af399c03442f724c95681faa023b25`.
The tagged source is `7b83b8d426bc7e58c0030fe974695ca7d0e54465`. Two clean
builds produced the same wheel bytes. The installed wheel suite passed all 72
tests without Commons being installed.

Publication automatically dispatched both registered consumer workflows:

- [Hube upgrade PR](https://github.com/kumiori/417b59f6d2dcf1c058b91f87871ddca9/pull/1):
  all ten checks passed; legacy suite 30 passed; application suite 106 passed,
  one optional test skipped.
- [Commons upgrade PR](https://github.com/kumiori/faf8bd6b99cf36852fd143ef1d67f937/pull/1):
  the first run correctly blocked adoption when two application tests lacked the
  optional trajectory dependency. The pipeline repair installs the application's
  declared trajectory and terminal-test extras using a compatible pinned build
  backend. Its initial failing report remains in the Actions artifacts.

Both proposals are drafts. Main branches require an approving human CODEOWNER
(`@kumiori`) and the compatibility status, including for administrators. GitHub's
coupled Actions create/approve setting was enabled only after this human-only
review gate was verified; bot review cannot satisfy that gate. The workflows
contain no approval, merge or deployment operation.

The manifest advertises 26 supported capabilities. Neither historical wheel had
an earlier manifest, so automated feature differences are marked unknown rather
than presenting 26 existing features as newly implemented.

The [upstream source PR](https://github.com/kumiori/113a4cce0c9191877e82b1a0b6767a70/pull/1)
remains open for review; no default source branch or consumer upgrade PR has
been merged. The maintainer publisher was exercised using existing GitHub
credentials. No administrator token or cross-repository secret was copied into
Actions; future unattended publication requires the scoped token described in
the release guide. Consumer hourly polling works without it.

Read-only verification still finds 25 events in the existing local Commons save,
with state digest
`aae0d98ad6c450af0e2de5cbb011a81858f2738ce85f747cc4ab0fe2f28b7e54`.
Hube's unrelated local edits and Commons' untracked `art/` are untouched.
