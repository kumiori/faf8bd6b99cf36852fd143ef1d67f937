# SADDLE PATHWAYS — trajectory/terminal checkpoint

Validated 4 November 2026. The source audit and compatibility assessment were
written before implementation. This is the minimal integration checkpoint,
not a declaration that M1–M5 are complete.

## Delivered

* [Trajectory source audit](05-trajectory-audit.md): real repository resolution,
  pinned `0.2.0` / `757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`, source/API inventory,
  dependencies and native modelling limits.
* [Compatibility contract](06-trajectory-compatibility.md): read-only native
  package document with versioned discrete history under `plan.commons_trajectory`.
* [Updated M0–M5 roadmap](MILESTONES.md): accepted distinctions and gates preserved;
  package compatibility and terminal-first requirements added to each milestone.
* [Terminal architecture](07-terminal-architecture.md) and working `play` command:
  scenario/actor selection, fixed identity, explicit development hot-seat, all
  three mode views, contract negotiation, evidence, history, trajectory inspection,
  hypothetical branch simulation, export and replay.
* `trajectory-demo`: a synthetic bilateral agreement, native YAML round-trip,
  exact Commons reconstruction, and accept/reject alternatives from a common state.
* Source lock and optional dependency: six package-module SHA-256 hashes checked
  against the pinned committed release. No dirty upstream working-tree dependency.

The actual boundary is:

```text
ActorSession / terminal → Commons validation → SQLite atomic append
                                      ↓
                                event history
                               /             \
                       Commons replay    trajectory adapter
                                                ↓
                                 trajectory-engine document / YAML
                                                ↓
                                 terminal inspection / export
```

No shared engine, Commons governance rule, Hube rule/fixture, browser application
or external trajectory-package source was modified by this integration.

## Fresh validation

| Check | Evidence |
|---|---|
| Complete Commons suite with trajectory dependency installed | **55 passed**, no skips, in 18.63 s |
| Original Hube regression suite | All **58 original tests passed**, invoked by the compatibility test |
| Frozen Hube acceptance artefacts | **6/6 unchanged** |
| Pinned upstream non-graphical public API suite | **10 passed** in a pristine committed-source archive |
| Actual CLI package export/import | Complete recorded trajectory plus two explicitly hypothetical branches; lossless nested round-trip and replay equality |
| Entered terminal playthrough | 12 transactions; revised contract v2; all parties accept; institutional approval; reservation; each party acts and reports; independent verifier establishes the synthetic outcome |
| Real pseudo-terminal smoke test | Entry screen, fixed actor, package trajectory inspection, consistent replay and normal quit |
| Distribution | Wheel built; TUI, adapter, actor boundary and source lock included; pinned optional dependency metadata and `subtle-pathways` entry point verified |

The suite includes the previous 36 checks plus 19 new adapter/session/TUI checks.
Compatibility tests exercise real native package APIs, not mocks. They preserve
full atomic event identities/order, mutation contents, epistemic provenance and
verification distinctions. Branch tests compare both source memory and SQLite
bytes before/after, retain rejected attempts as diagnostics, and validate parent
identity and deterministic branch resolution. Actor tests reject impersonation,
implicit switching and stale writes. Cancelled forms create no partial contract.

The 58 Hube tests run inside one Commons compatibility test; these totals should
not be added as if they were disjoint top-level tests. The original repository's
unrelated dirty files were preserved.

Commands used:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  --basetemp /private/tmp/subtle-full-suite
.venv/bin/python -B -m commons_game trajectory-demo bilateral-logs \
  --export /private/tmp/subtle-first-trajectory.yaml
.venv/bin/subtle-pathways --help
```

The full suite requires loopback permission for pre-existing HTTP adapter tests.
No web application was developed or launched for this checkpoint. Package/terminal
integration needs neither Streamlit nor graphical visualisation. The runtime was
installed from a pristine `git archive` of the audited commit into a workspace
virtual environment; no package code was copied into this repository.

Entered acceptance input and retained output:

* `tests/scenarios/subtle_bilateral.stdin`
* `tests/transcripts/subtle_bilateral.txt`

## Limits and remaining work

The trajectory package natively models authored trajectories and geometry, not
arbitrary world-state transitions or a generic game-history tree. Its native
serializer/normaliser is used; the discrete Commons envelope is a documented
extension. Native spline analysis is not available for these coordinate-free
histories. No physical quantities, normalized event positions or uncertainty
strengths are invented. The generic native `Done` status is never substituted for
independent verification.

History is recorded **within a synthetic simulation**. A verified simulation
outcome does not assert real Gallica access or institutional agreement. Raw source
provenance and unknown fields remain in the events; missing information is not
converted into numerical certainty. Existing event timestamps are logical
transaction times, not retroactively manufactured empirical observation times.

Local actor selection is not production authentication. Normal sessions remain
fixed; explicit hot-seat exists for development. The raw JSON CLI is a trusted
development boundary. Trajectory imports only reconstruct detached inspection
instances; there is no save/import-to-live-state operation.

Empirical Montréal import, scoped delegation/condition registry, shared-governance
extraction, contract-backed Hube feasibility and alternative mentoring strategies
remain the documented M1–M5 gates. The current integration and branch inspection
do not silently complete those gameplay milestones. Existing browser scaffolding
is retained but is not the first interactive laboratory.
