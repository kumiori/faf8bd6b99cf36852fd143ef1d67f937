# Decision graph diagnosis and verification

Start with [the completeness report](COMPLETENESS_REPORT.md).

- [Baseline inventory: all 1,076 requested rows](baseline/diagnostic_inventory.json), grouped by root cause.
- [Scoped technical release gate](reconstruction/release_gate.json).
- [Scoped actual audit](reconstruction/audit.txt) and [responsiveness measurement](reconstruction/responsiveness.json).
- [Passed-test evidence and runtime observations](reconstruction/evidence.json).
- [Four-view application overview](application-overview.mmd), [screen navigation](screen-navigation.mmd),
  [decisions/actions](decision-actions.mmd), and [lifecycle](transition-lifecycle.mmd).
- [Focused reconstruction lifecycle](reconstruction/recall-lifecycle.mmd).
- [Diagnostic filters](filters/) for unmapped, recovery, untested, uninstrumented and dynamic findings.

Canonical JSON accompanies the complete application and scoped graphs; each view has Mermaid and DOT exports. JSON views can be generated on demand through the CLI. `reconstruction/` provides
views restricted to the executable release contract. `decisions.*` and the root
audit/inventory include the remaining source-only application. They are not an
application-wide verification claim. The immutable original graph/report/coverage
are in `baseline/`; `baseline_comparison.json` records the structural changes.

Regenerate with `tools/build_decision_audit.py` after collecting compatible test
manifests. The builder rejects stale evidence and measures only a disposable
synthetic world. No live player world is loaded or changed by graph generation.
