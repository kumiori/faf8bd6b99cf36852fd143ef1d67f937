# Immutable releases and consumer proposals

The release protocol is `game-gamer/release/v1`. A release contains a wheel,
`capabilities.json`, `CHANGELOG.md`, `release.json` and `SHA256SUMS`. The capabilities
schema is separately versioned as `game-gamer/capabilities/v1`. The package version,
extension contract version and application extension versions are independent.

The manifest is packaged in the wheel. `game_gamer.get_capabilities()` returns a
detached copy, and `game-gamer capabilities` works without the terminal extra.
Capability names describe implemented interfaces, not proof that any particular
world achieved an outcome. `optional_extras` identifies terminal capabilities.
Removing an advertised or required capability blocks an automated upgrade.

## Publish

Use Python 3.11, setuptools 75.6.0 and wheel 0.45.1, and run the package tests.
Commit the exact candidate, then create its version tag. Never move a published
tag or replace release assets. Enable repository release immutability before
publication. Build from a clean source copy with fixed `SOURCE_DATE_EPOCH`:

```sh
python -m release.bundle --output /tmp/game-gamer-release --source-commit FULL_COMMIT_SHA
python -m release.publish /tmp/game-gamer-release
```

The publisher checks the repository immutability setting, creates a new draft,
uploads the complete asset set, publishes it and checks `immutable=true` in the
result. Existing releases are never overwritten. A maintainer can also dispatch
the release workflow against a version tag. Its preflight needs Administration read access to inspect the immutable
setting and Contents write access to publish: configure a narrowly scoped
`RELEASE_TOKEN` when the default Actions token cannot perform that check. Without
sufficient permission it fails closed. Maintainers can use the same CLI with
their existing authenticated GitHub account; no personal token is copied into
repository secrets by these tools.

The publisher notifies the consumers in `config/consumers.json` by dispatching
their update workflow. Cross-repository Actions dispatch requires a GitHub App
token or fine-grained token supplied as `CONSUMER_DISPATCH_TOKEN`. Without it,
scheduled polling remains automatic and requires no cross-repository secret.
Notifications contain only the repository/workflow identity; consumers resolve
and independently verify the trusted upstream release themselves.

## Register a consumer

Install `release/*.py` under `.github/game-gamer/release/`, and the registry under
`.github/game-gamer/consumers.json`. These are versioned bootstrap tools, not a
second runtime. Copy the update and compatibility workflows from the Commons
consumer. Configure `config/game-gamer-consumer.json` with exact previous pins,
baseline wheel, supported extension contracts, required capabilities and existing
legacy/application tests. The release supplies no executable test commands or
destination paths. Changes to the updater itself are reviewed separately.

Enable Actions to create PRs. Protect the consumer's main branch with at least one
approving review and the `Game-Gamer compatibility` status check. Disable direct
pushes, force pushes and bypasses where the hosting plan permits. No workflow
merges, enables auto-merge, deploys, provisions a player, migrates a save or edits
application extension versions.

The updater runs hourly, on release notification or on manual dispatch. It:

1. Requires an immutable stable release from the configured upstream.
2. Resolves its tag to the exact source commit and checks every asset digest,
   wheel metadata and embedded manifest.
3. Updates only configured exact pins, a new vendored wheel, checksum, manifest
   and next-run pin metadata. Previous wheels remain available.
4. Compares the baseline and candidate public API and installs each outside the
   source trees. Synthetic probes test extension binding, rejection, retry,
   restart, replay and branch isolation.
5. Installs the consumer and runs its legacy-save and complete application tests
   in a disposable environment, with synthetic data paths.
6. Attaches JSON/Markdown reports and test logs. A valid artifact with failed
   compatibility still produces a draft PR carrying a failing required status.
   Invalid artifacts never update pins. Existing proposals and rejected versions
   are retained rather than overwritten on each poll.

A PR remains **awaiting approval**, including after tests pass. A consumer's CI
re-downloads the exact immutable release and compares it with the checked-in pin.
For the first manifest, the prior wheel may contain none: the report marks the
feature difference unknown rather than treating all listed features as new.
Tests must not use production database paths. Skips and logs remain visible; a
passing automated report does not establish human gameplay acceptance.

Supported historical application extension implementations remain in the host.
The updater cannot synthesize or bump them. When interpretation changes, keep the
old implementation available and review any separate migration explicitly.

Dependabot/Renovate registry updates are deferred until the package is actually
published in a supported registry. GitHub Releases and exact wheel digests are
the implemented update channel.

GitHub references: [immutable release publication](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository),
[immutability API permissions](https://docs.github.com/en/rest/repos/repos#enable-immutable-releases)
and [workflow token triggering rules](https://docs.github.com/en/actions/concepts/security/github_token).
