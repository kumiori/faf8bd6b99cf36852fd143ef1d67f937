# Trajectory package audit

Inspected: 3 November 2026. This supplements the frozen Hube baseline; it does
not change Hube or declare another milestone complete.

## Source identity and reproducible baseline

The supplied [GitHub address](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18)
is a real, public GitHub repository, not a gist. The connected GitHub repository
API resolved it successfully, with default branch `main`. Its current
[commit](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/commit/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d)
is `757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`, release `0.2.0`.
The generic web reader returned a cache miss for GitHub and could not fetch the
possible gist URL; the connected GitHub API resolved the actual source, so
there is no outstanding source-access blocker.

The local checkout at
`/Users/kumiori3/Documents/WIP/Society/code/trajectory-engine` has that same
HEAD and origin, but contains unrelated uncommitted changes, including a new
shared-goal store and `trajectory-bundle/v3`. Those changes are **not** the
audited release. Source claims below refer to the immutable commit above,
inspected through `git show` and a pristine archive. No files in either
trajectory checkout were modified.

The embedded copy in
`/Users/kumiori3/Documents/WIP/Society/app_protocol_hack/packages/trajectory-engine`
declares `0.1.0`; its last path-specific commit is
`1d2853a16c279a5ba2e2748078f54d8c1491b005`. It is an older extraction, not the
dependency selected here. The upstream
[downstream handoff](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/docs/downstream-0.2.0.md)
also identifies Protocol Hack's embedded copy as a consumer requiring an
explicit update.

## Technical inventory

| Question | Actual implementation |
| --- | --- |
| Principal structures | Python mappings and sequences, canonical `trajectory-plan/v2` documents, shared goals, independently authored contribution records and `trajectory-bundle/v2` bundles. `ControlNode` is an internal frozen dataclass for spline geometry. |
| State | A plan snapshot with initial condition, goal, primitives, uncertainty intervals and view metadata. It is not a general graph-world state, contract state machine or event-sourced game state. |
| Trajectory | Discrete authored primitives with stable IDs and semantic fields, plus derived continuous piecewise Hermite geometry. Native coordinates are `(normalised time, uncertainty state, energy)`. |
| Events | Primitives include event/action/update/milestone and planning moves such as sharing resources or delegating. These are descriptive planning categories, not executable authorisation or resource rules. |
| Time | Authored `time_parameter` is clamped to `[0,1]`. Qualitative anchors run from Now to Landing. Linear date horizons, relative-unit labels, optional ISO calendar anchors, authored actual timestamps and time expressions coexist. A calendar pin adds a constraint without changing the authored parameter. |
| Uncertainty | Named interval modifiers with start/end parameters, Light/Marked/Strong strengths and balanced/expands/contracts evolution. Geometry generates uncertainty radii/envelopes/tubes. This is not a probability distribution or a model of empirical evidence confidence. |
| Serialisation | `trajectory_yaml` uses safe YAML encoding; `load_trajectory_yaml` loads, validates and normalises. Canonical version is v2; unversioned/v1 imports have compatibility handling; unknown versions fail explicitly. Dates become ISO strings. |
| Reconstruction | Reconstructs a normalised plan document and derives geometry. It does not replay authoritative Commons commands or reconstruct game state from transitions. |
| Analysis/view interfaces | Pure geometry sampling, time-display ticks, time–energy display projection, event points, uncertainty meshes and binary branch stems. The optional example app uses Plotly/Streamlit; the package core imports neither. No general governance analytics or game-history analysis API exists. |
| Branching | Explicit branching topology, two labelled branch identities and an optional branch-parent field. The branch renderer uses the **first** branch point and keeps later primitives common to both stems. It does not provide arbitrary branching world histories or independent per-branch game states. |
| Provenance | Contribution author/agent, source and revision; primitive collaborators, responsible actors, timestamps, notes and evidence strings. Planned versus realised statuses exist. Empirical observation, participant declaration, simulation, hypothetical scenario and independent verification are not native epistemic categories. |

Sources: [schema.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/src/trajectory_engine/schema.py#L45),
[geometry.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/src/trajectory_engine/geometry.py#L1),
[planning.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/src/trajectory_engine/planning.py#L12),
[contributions.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/src/trajectory_engine/contributions.py#L1).

## Public interfaces and dependencies

The root package re-exports the following through
[public.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/src/trajectory_engine/public.py):

- Documents: `SCHEMA_VERSION`, `build_trajectory_document`,
  `normalise_trajectory_document`, `trajectory_yaml`, `load_trajectory_yaml`.
- Planning/realisation: `QUALITATIVE_TIME_ANCHORS`, `REALIZATION_STATUSES`,
  `RELATIVE_DISPLAY_UNITS`, `TIME_DISPLAY_MODES`, `build_plan_payload`,
  `now_parameter`, `realize_primitive`, `resolve_actual_timestamp`,
  `temporal_display_ticks`.
- Geometry: `DIRECTIONAL_MODES`, `INFLUENCE_SCALES`, `TOPOLOGY_MODES`,
  `primitive_plot_label`, `project_time_energy`, `sample_trajectory`.
- Contributions: `build_shared_goal`, `build_goal_trajectory`,
  `revised_goal_trajectory`, `build_goal_bundle`.

`__version__` is `0.2.0`. Other module-level helpers include
`geometry.binary_branch_stems`, `trajectory_point`, `event_points`,
`uncertainty_tube_mesh`, `contributions.goal_bundle_yaml` and
`load_goal_bundle_yaml`; they are not root re-exports. Contribution revisions
check the contributing agent ID, but this is not a substitute for Commons
actor-bound authorisation. Bundle v2 permits one contribution per agent per
goal; it must not be mistaken for a common authoritative collective history.

[pyproject.toml](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/pyproject.toml)
requires Python `>=3.11` and `PyYAML>=6.0,<7`; the build backend is
`setuptools>=77`. Optional demo dependencies are `plotly>=6,<7` and
`streamlit>=1.49,<2`. Development extras are build, pytest, ruff and twine.
No numerical-array, graph, database, blockchain or game-engine dependency is
required. The [MIT licence](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/LICENSE)
allows reuse; copying or vendoring must preserve its copyright and permission
notice. Pin the exact audited commit or vendor its unchanged package sources
with that notice and a recorded source revision; do not vendor the dirty tree.

## Smallest compatible boundary

Use the existing package as a read-only **document/serialisation boundary**,
with a versioned Commons projection nested at `plan.commons_trajectory`.
Keep `primitives=[]` and `uncertainty=[]` until participants author genuine
trajectory semantics. Do not manufacture energy, uncertainty or normalized
event coordinates from commit counts, contract statuses or resource quantities.

The nested projection must preserve Commons initial state, ordered complete
atomic commits, action/actor identity, immutable contract versions and their
distinct lifecycle events, evidence, epistemic provenance, and explicit branch
parentage. Those are Commons adapter semantics, not features already supplied
by trajectory-engine. Reconstruction continues to use the existing Commons
replay path and invariants. A trajectory document never authorizes an action
or becomes a live world; any import used for inspection is validated before
replay into a detached world.

This placement follows the actual normalizer:
[schema.py:346–402](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/src/trajectory_engine/schema.py#L346)
copies arbitrary **plan** fields, but rebuilds the document's top-level keys
and forces outer `plan.source_kind` to `plan`. Consequently unknown top-level
metadata can disappear and outer source-kind cannot carry authoritative
empirical/simulated provenance. All such distinctions belong inside the
versioned Commons namespace. Its schema must reject unsupported versions.

Native realisation statuses are `Planned`, `Done`, `Changed`, `Skipped` and
`Cancelled`. None means independently verified. Preserve agreement acceptance,
reported execution and verified fulfilment separately in the Commons payload;
never equate a package `Done` label with verified reality. Likewise, the
package's two visual branch stems do not execute alternatives. Alternative
Commons actions must run through the same engine on detached replayed worlds,
with explicit simulation provenance and a common parent commit/state.

This is deliberately limited compatibility: the package reads, preserves and
serializes collective evolution in its document format; native spline
analysis cannot interpret arbitrary Commons histories. It provides a tested
starting boundary without copying its geometry or building a second engine.
A later upstream discrete-history extension would require its own schema and
acceptance tests rather than overloading physical-looking coordinates.

## Examples, tests and checks

The committed examples are short integration instructions:
[individual plan](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/examples/individual_plan/README.md)
and [shared goal](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/examples/shared_goal/README.md).
The runnable examples are `tools/smoke_test.py`, `app.py` and
`pages/01_temporal_constraints.py`; none is needed for terminal integration.

The pristine committed source was extracted into a temporary directory and
tested without writing to the original repository:

```text
PYTHONDONTWRITEBYTECODE=1 <trajectory-venv>/bin/python -m pytest -q -p no:cacheprovider
12 passed in 2.40s
```

This includes the two optional Streamlit AppTest checks because that
environment has demo dependencies. The remaining ten tests cover public
version, append-only realisation, unsupported-schema rejection, explicit
branch topology, registered uncertainty, calendar constraints, qualitative
time, view purity and geometry stability. See
[test_public_api.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/tests/test_public_api.py)
and [test_demo_page.py](https://github.com/kumiori/3868a1d2cf7234d3bb44ffc5455adc18/blob/757c2baeb17e9864eeff0900b5ad9ea3cec23d9d/tests/test_demo_page.py).

A separate executable probe built a document with no coordinates and nested
synthetic Commons events and hypothetical branch metadata, serialized it with
`trajectory_yaml`, and reconstructed it with `load_trajectory_yaml`. Exact
nested payload equality passed. It also confirmed the outer source-kind
normalisation described above. This establishes feasibility of the boundary;
Commons replay, authorisation, lifecycle and branch-isolation tests remain
the integration's responsibility.
