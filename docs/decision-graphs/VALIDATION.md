# Validation of executable decision contracts

Validated against the current worktree on 2026-11-07.

- Portable package regression suite: **43 passed**.
- Complete host regression suite: **239 passed** with the environment access
  needed by localhost HTTP and isolated wheel tests.
- Final focused inspection/verification/CLI suite after presentation changes:
  **29 passed**. Earlier focused transition tests also exercised all action
  variants, rejection/cancellation, replay, exception recovery and interrupts.
- The retry/concurrent-client reproducer went red with `committed` instead of
  `idempotent`. It passes after receipt classification moved under the commit lock.
- A canonical JSON round trip preserves the gate result and its required outcomes.
  Unsupported/stale evidence, missing evidence, failed trials, filtered views and
  invalid performance thresholds cannot open the gate.
- A fresh core wheel installed without Commons or `wcwidth`. The transition API
  imports, deterministic engine/terminal extraction, JSON/Mermaid/DOT CLI exports
  and a friendly missing-host error for the host-only scope were verified.
- Compatible package/host observation manifests were validated before union.
  Scoped evidence contains only passed tests and has no contract violations.
- All generated DOT files passed Graphviz `nop -p`. The application overview,
  connection decisions and focused lifecycle were rendered as SVG/PNG.
- `git diff --check` passed. Existing worktree changes were preserved.

The exact current results are in `reconstruction/release_gate.json` and
`reconstruction/responsiveness.json`. The reconstruction audit has 11 registered
screen states, 8 questions, 59 transitions/options and 6 authoritative action types.
All **17 critical transitions** are tested and instrumented. There are **18 uncovered
noncritical transitions**; the audit does not suppress them. The source contract
has zero unmapped options and zero missing recovery paths.

The benchmark used 200 synthetic participants and 100 read-only handle/render
samples with in-memory tracing. Its measured p95 was **4.112 ms** against the
configured local **100 ms** budget. Source digests bind the measurement and passed
evidence to the actual contract. No production-load or human-usability acceptance
is claimed.

The application-wide source graph remains incomplete: **126 unmapped options**,
**32 unresolved recovery paths**, **515 untested transitions** and **351
uninstrumented transitions**. Those are not all confirmed gameplay defects.
The baseline inventory preserves the requested original 132 / 41 / 527 / 376
counts and every diagnostic row, with source uncertainty and verification gaps
classified separately. The complete application is **not verified**.

No world/event schema, saved-world migration, production write, publication or
deployment was introduced. UI traces remain observations; engine events remain
authoritative.
