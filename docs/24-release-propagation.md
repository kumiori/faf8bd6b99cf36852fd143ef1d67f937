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
