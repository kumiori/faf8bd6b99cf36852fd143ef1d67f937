# Contextual curation and global history

This sprint preserves the existing authoritative runtime, event ordering,
agreement mechanics, actor binding and reversible identity merges. New curation
requests are administrative actions, not new gameplay obligations.

## Controls and targeting

- **u Context** opens the reusable context panel beside the source screen. At
  widths below 90 columns, **Tab** switches between the main view and panel.
- The panel follows the explicitly selected object in directories, inspectors,
  reconstruction, the network and historical-object inspection. It displays the
  target name, object type and stable ID. An ambiguous matrix pairing requires
  an explicit choice; absence of focus never substitutes the player identity.
- **Tab** transfers keyboard focus without losing the source selection, scroll,
  graph type, observation layer or zoom. **u**, **b** or **Esc** closes the panel;
  Back first returns from its request/provenance subpages.
- Identity merge previews retain their explicit source/target and prevent focus
  switching until cancelled or confirmed. Profile, visibility, merge and reversal
  operations require confirmation and continue using engine-enforced permissions.
  Reversal choices are restricted to merges involving the focused identity.
- If a correction or merge removes the target from a filtered source view, the
  panel retains the explicitly changed identity (the canonical target after a
  merge). Moving in Main resumes following its selection. There is no fallback
  to the player. Historical contexts expose read-only inspection.
- Yellow **CURATOR** indicates existing engine permission; opening a panel never
  grants that permission. Ordinary players see request/provenance/history controls.
  Direct editing remains limited to the existing actor-profile operations; other
  object types support inspection and correction/review requests.

The multiplex explorer adds **T Types** alongside **L Layers** and **S Scope**.
People, organisations, resources, relationships, agreements, capacities, needs,
evidence, objectives, policies and invitations use the existing graph projection.
The centre remains a visible anchor when its type differs from the filter.
Relationship filtering retains relationship edges and excludes structural
institutional/agreement links. Every displayed bundle retains its source records.
Labels distinguish **Playing as**, **Inspecting**, and **Offers → Needs**.

## Request protocol and storage

Three commands extend the normal action registry:

| Command | Required fields | Authority |
| --- | --- | --- |
| `request_curation` | `target_id`, `request_type`, `reason` | Bound active player |
| `review_curation_request` | `request_id`, `decision`, `reason` | Curator |
| `clarify_curation_request` | `request_id`, `reason` | Original requester, after clarification is requested |

Request types are `correction`, `duplicate_merge` and `profile_review`.
Duplicate requests identify a second actor through `related_id`; correction
requests may include declarative `proposed_changes` for the existing profile
fields. Role changes cannot be proposed or granted through these commands.

Lifecycle: `submitted → approved / rejected / needs_clarification`;
requester clarification returns to `submitted`. Approved/rejected reviews are
final. Every review records its actor, reason, authoritative timestamp, action
ID and commit reference. Exact action retries resolve inside the existing commit
boundary, including after SQLite reopen.

**Approval is a review decision, not automatic application.** An approved
request offers Open Target; correction/merge then uses the existing separate,
confirmed operation. This preserves merge preview/version checks and records
review and application as distinct events.

Records live in the existing configuration table under `curation-requests`,
with schema `game-gamer/curation-requests/v1`. Initialization is additive on the
first request. No SQLite migration, source-data rewrite or live-world migration
is required. Replay applies the same authoritative mutations as before.

## Global history

**History** is available in the main path menu and persistent navigation through
uppercase **H**. Lowercase **h** retains contextual object history.

- **+ / -** selects Overview, Detailed or Technical. Overview describes collective
  actions; Detailed includes actors, affected objects, changed fields, before/after
  values and outcomes; Technical includes the complete original event with IDs,
  revisions, authorization, provenance and payload.
- **f** filters by actor, object, action, mission/objective, or inclusive time bounds.
  Time filters use the event's authoritative `occurred_at` value, with explicit
  timezone; they do not manufacture real-world timestamps from simulation time.
- **Enter** opens an event and then its affected objects as they were after that
  event. **b** returns to the exact event/list selection and scroll position.
- Display names use the current directory's stable aliases; Technical and the
  historical object retain original identifiers and recorded data. Long values in
  Detailed are explicitly abbreviated; Technical retains the complete values.

All views derive from the original event history. There is no second history
store. Revision-scoped caches hold detached history projections and formatted
rows; navigation never submits actions or recomputes the authoritative state.

## Implementation boundaries

Portable runtime: `game_gamer.runtime.curation_requests`.
Portable read model: `game_gamer.projections.history`.
Shared terminal rendering: `Screen.panel` and `CursesViewport.draw_panel`.
Host navigation/composition: `commons_game.curation_panel` and
`commons_game.global_history`.

The optional standalone Game-Gamer terminal retains its own presentation and
can open its existing History view with H; the full contextual panel and history
navigation in this sprint are mounted by the Commons terminal host. No terminal
package is imported into the authoritative engine.

The decision inspector registers the new request module, permissions and source
digest; its engine export snapshot is refreshed for this additive registry change.
Existing full-application decision-graph artifacts remain historical snapshots,
not a claim of fresh verification of every interface path.

## Validation

Regression coverage includes explicit counterparty targeting, ambiguous/no
focus, cancellation, historical read-only contexts, type/layer/zoom preservation,
independent main/panel scrolls, ordinary-player permission denial, requester-only
clarification, approval/rejection, forged actor binding, exact retries, SQLite
reopen, authoritative replay, all history filters, detail levels and object-return
navigation.

`tools/playtest_consolidation.py` drives a real curses PTY using fictional data.
It covers reconstruction, confirmations, contextual merge/reversal, request
review, wide/narrow layouts, history drilldown/filtering and isolated tutorials.
It emits text captures, ANSI output and an asciinema recording to a fresh output
directory outside the repository. No private Montréal save is changed.

Final validation on 2026-11-08:

- Commons: **253 passed**, including the Hube compatibility subprocess, local
  HTTP checks and isolated wheel installation.
- Game-Gamer: **47 passed**, including request permissions, canonical requester
  ownership, replay, restart, exact retries and decision-inspector consistency.
- Full curses playthrough: **passed**, with review approval, merge reversal,
  144-column and 70-column panels, history detail/filter/drilldown and tutorials.
- `git diff --check`: passed.

Fictional terminal evidence for this run is in
`/tmp/commons-context-history-validated/`: `session.cast`, `terminal.ansi`,
`11-curator-operations.txt`, `15-reviewed-request.txt`,
`16-narrow-context-panel.txt`, `18-global-history.txt`,
`19-technical-history.txt`, and `20-filtered-history.txt`.
Changes are uncommitted on `main`; unrelated earlier work is retained.
