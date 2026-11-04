# SADDLE PATHWAYS: from complementarity to collective action

Implemented checkpoint, 4 November 2026. This extends the existing authoritative
Commons engine; it does not introduce another game-state or identity authority.
All actions described here are simulated. No participant is contacted outside the
game. Existing private captures and the user's saved Montréal world are unchanged.

## Mathematical audit and the reported 4/5 discrepancy

The audit reads one immutable history prefix, not two independently refreshed
screens. The checked empirical world is state **8**, SHA-256
`38d69476845367958a9160fd56add5759b6206f5e9e0340ca0fc3bdc4708167d`.
The source version is
`b35a99805379fd4c38c8d5e726b63d1bf5b2b8b80639c3b39eb4fefaf40237f1`.
Its expertise assertions exactly match the parsed existing private minimal capture. Re-import into a detached fresh Commons world reproduces actor
ordering, O, N, W, bounds, vocabulary and observations. Import-event provenance
naturally belongs to the fresh world's different history prefix.

The source has **41 eligible people**, **17 shared expertise domains**, **211
offered-domain selections**, and **290 requested-domain selections**. All 41 offer
responses are answered; 40 needs responses are answered and one is skipped.
All **1,681 cells**, including the raw analytical diagonal, match the independent
per-domain calculation. Exact counts equal the lengths of their matching-domain
lists. Missing values remain separate observations.

The 4/5 symptom is reproducible without any arithmetic disagreement: **two
distinct source people share the first name Nathalie**. With the same Catherine
and source snapshot:

| Provider display | Heatmap | Inspector | Contributing domains |
|---|---:|---:|---:|
| Nathalie (1) | 5 | 5 | 5 |
| Nathalie (2) | 4 | 4 | 4 |

The original screenshots do not identify which canonical source person each
selected, so their exact provenance cannot be established retrospectively. The
current evidence establishes a display-identity ambiguity, not an O/N/W arithmetic
mismatch. Both people remain separate actors. Surnames stay hidden; collision
ordinals now appear consistently in selectors, matrices, profiles, graph labels,
contract participants and inbox badges. Ordinals follow actor creation order,
not seniority or permission; inactive actors retain their slots. Later appended
actors with the same unchanged first name cannot reassign existing slots. Source
name corrections and historical prefixes may change the derived display mapping;
authoritative IDs remain the identity reference.

Two synthetic regressions cover this: a single actor's score legitimately changing
4 → 5 between captures while every view of one prefix agrees, and distinct actors
sharing a first name without collapsing their displayed identities.

### Source-grounded path

1. `montreal_capture.pages` paginates source records and selected properties.
2. `capture_montreal` resolves participant links/identifiers, chooses the latest
   permitted submitted inventory, and reads only the shared choice taxonomy.
   Names never join identities. Raw text and contact fields are not expertise.
3. `declared_topics` preserves explicit skip/defer/partial/missing states.
   Unknown and Other codes never become invented taxonomy domains.
4. `ecosystem_import.import_snapshot` validates and commits the minimal assertions
   once through the existing engine. There was no new live capture or write-back.
5. `expertise.matrix` supplies the same ordered actors and sorted domain codes to
   O, N, W, the inspector and potential-edge projection.
6. `projections.complementarity` is now the single arithmetic implementation.
   `expertise.cell` derives its matching list from those actual incidence rows.
7. Full-screen heatmaps and inspectors use the same immutable display frame.
   Context retains actor IDs, rather than treating row positions or first names
   as identities. Optional source details show exact assertions separately.

For complete vectors, **W = O Nᵀ**. For partial vectors, selected codes are 1,
explicitly observed absences are 0, and unobserved domains are unknown. Each
product is 0 if either input is known zero; 1 if both are known one; otherwise
unknown. The score is exact only when its bounds coincide. Otherwise the UI shows
an unknown score and its lower/upper bounds, with the confirmed matching domains.
An absent taxonomy cannot establish an empty-vector zero. A complete empty offers
vector can establish zero even when the other participant's needs are missing.
The original empty-vector regression expectation was corrected for this case.

The optional `observed_absent_codes` field supports explicit absences in partial
observations without guessing them from unselected codes. Full answered vectors,
including explicit empty answers, retain their existing representation. Unknown
inputs are exhaustively tested against all binary completions for two domains.
Confirmed matches from partial observations can appear as inferred potential;
they carry their bounds and never imply consent or established competence.

Reproduce the empirical comparison without writing the saved world:

```sh
.venv/bin/python tools/audit_matrices.py \
  --world "$HOME/.local/share/saddle-pathways/commons.sqlite" --at 8 \
  --source "$HOME/.local/share/saddle-pathways/captures/2026-11-04-matrix/ecosystem-snapshot.json" \
  --pair 'Nathalie (1)' Catherine
# Repeat with --pair 'Nathalie (2)' Catherine.
```

Without `--world`, this tool audits a fictional fixture. Ambiguous display names
are rejected with the available disambiguated labels. Public tests contain no
private source participant records or questionnaire answers.

## Implemented interface

- Uppercase **O**, **N**, **W** select offers, needs and directed matches.
  Lowercase `o`/`n` retain own-row/own-column navigation; lowercase `w` opens the
  network. Initial selection is the player's matrix position.
- All matrices have fixed axis headers, cell navigation, participant/domain
  search, categorical unknowns, optional numbers and exact inspection. W retains
  the fixed absolute bands 0, 1, 2–3, 4–6, 7–10, 11+; the final band is explicit
  overflow, never a silently rescaled maximum.
- The relationship inspector shows forward/reverse scores, matching domains and
  answer coverage. `d` expands source IDs and timestamps. Profiles summarise
  capacities/needs and offer four potential counterparties before paged network
  exploration; complete incidence lists are behind a separate entry.
- **Invite to connect** and **Propose a contract directly** are independent,
  visible actions in a player's relationship, another person's profile, an
  invitation inspector and the contract registry. `j` invites and `k` proposes
  from a matrix relationship. Third-party observation exposes no agency for
  either inspected person. Enter follows links; Back restores the preceding
  cell, direction and scroll state.
- A contact form has an editable message, optional purpose, displayed identity and
  context, and **Send now / Save draft** choices. Drafts can later be published
  or withdrawn from their inspector.
- Contract forms retain separate title, purpose, parties, offered/requested
  contributions, conditions and optional resources. A settings review allows
  validity, governance policy and wider objective selection. The engine still
  requires an objective; the default generic simulation objective is shown
  explicitly rather than inventing a source-recorded objective. Matching domains
  are origin metadata, never automatically generated obligations.
- Contract inspectors show participant roles once, current version/lifecycle,
  pending decisions, terms, conditions/resources, policy and evidence count.
  **y** accepts, **j** negotiates, **R** rejects and **X** withdraws where valid.
  Invalid actions are omitted from the footer and cannot be submitted through
  these shortcuts; the explanation or valid-action menu remains available.
- The inbox consumes one canonical record per invitation or contract. Overlapping
  categories are badges and filters, not duplicate rows. **F** selects incoming,
  outgoing, acknowledged connections, proposals, my decision, other parties,
  agreements in progress, verification requests or history. Long badges wrap
  within the same numbered entry, including monochrome terminals.
- Every screen identifies the playing actor, world and state version. Focus and
  selected relationship remain separate. Actor changes never reset the world.

The power-user `connect` / `invite to connect` command starts a contact invitation;
`open I-001` and history accept stable short invitation aliases. The older `invite`
command remains explicitly labelled **Invite to a gathering** and retains its
scenario attendance semantics. `respond` routes contact decisions to the inbox.
No advertised player command lacks a registered handler.

## Invitation domain and authoritative lifecycle

The `relationships` table already represents event-backed directed records.
Contact invitations therefore use kind **contact_invitation**, distinct from the
existing gathering kind **invited**. Each has an ID, sender (`source_id`), recipient
(`target_id`), editable-before-submission message, optional purpose/origin/expiry,
status, response, logical creation timestamp, simulated-delivery provenance and
related commit references. Its projected node is independently inspectable.

| New command | Required fields besides actor/key | Result |
|---|---|---|
| `draft_contact` | id, recipient_id, message | Saved draft, absent from recipient inbox |
| `send_contact` | id, recipient_id, message | Sent in-game contact invitation |
| `publish_contact` | invitation_id | Draft becomes sent |
| `respond_contact` | invitation_id, response = accept/decline | Recipient decision |
| `withdraw_contact` | invitation_id | Sender withdraws draft or pending request |

Creation optionally accepts purpose, bounded matrix context and expires_at.
Responses optionally accept a message. Recipient/sender rules, person eligibility,
current status, expiry and actor-bound sessions are checked by the engine. There
are no executable invitation conditions. The existing key/idempotence mechanism
returns the original commit for an identical submission; conflicting keys and
invalid responses create no mutation. Expiry occurs through the existing explicit
simulation-clock advance, not a hidden wall-clock task.

Acceptance atomically changes the invitation and adds a distinct **acknowledged_connection**
relationship. The acceptance event and action effects distinguish the invitation
response from connection acknowledgement. It is a game connection only, never
an institutional relationship, contract, evidence of data exchange or real contact.
The graph retains the inferred potential, invitation and acknowledged connection.
No contract is created automatically. Proposed contracts optionally retain
`interaction_context` (relationship origin and invitation reference), without
requiring an invitation or turning that metadata into responsibilities.

Existing exact-version acceptance, institutional authorisation, resource
reservation, execution reporting and independent verification gates are unchanged.
A third party cannot accept as a party, create party execution/fulfilment or submit
verification prematurely through these new pathways. Evidence references remain
simulation attestations; the engine does not prove the external truth of supplied
text. Acceptance is not verified fulfilment.

## Graph scope and renderer

The existing extracted Hack camera/raster remains the renderer. No adjacent Hack
checkout or new runtime dependency is required. **S** selects whole graph,
player-centred, selected-person, contract, or invitation/connection scope. **L**
selects a layer: affiliations, other documented relations, inferred potential,
pending invitations, accepted connections, proposed contracts, accepted/active
contracts, or verified outcomes. Filters are projection views only.

The screen reports rendered/full node counts, rendered/full original relationship
counts and the number of visual bundles. `[ ]` pages the bounded diagram; source
relationships within a bundle remain inspectable in the projection. Contract
neighbourhoods retain parties, resources, objective and policy. A hidden page is
explicitly a rendering reduction, never missing source coverage.

**Experimental:** `3` selects a deterministic three-dimensional layout with actual
non-planar depths; `r` changes yaw and `{` / `}` change pitch. Hack's depth-aware
perspective projection and raster arbitration remain in use. Planar mode is still
the default and can be restored immediately. These disposable coordinates have
no physical, sociological or inferred trajectory meaning. Dense diagrams can
still overlap; scopes, layers and pagination are the supported navigation tools.

## Persistence, migration and trajectory boundary

**No SQLite schema or historical-log migration is required.** No new top-level
world table was added, so old commit hashes remain valid. The existing version-8
empirical world loaded and replayed unchanged. New relationship kinds, optional
expertise observation fields and optional proposal context are additive. Use the
updated client to understand new invitation commands and UI projections.

The same `CommonsGame.submit`, `ActorSession`, optimistic version check,
`SQLiteStore`, commit hashes and deterministic replay apply to both pathways.
The trajectory adapter still stores the unmodified sequence/provenance in the
pinned package's `plan.commons_trajectory` extension. Derived frames now include
invitation states, acknowledged connections and the authoritative event kind.
Native geometry stays empty. Branch tests preserve the original SQLite bytes and
simulate alternatives only in a detached replay.

No production authentication, real messaging, blockchain settlement, legal
enforcement, external source write-back or automatic real-world verification was
added. Invitation text has no in-place amendment lifecycle; a new proposal is a
new ID, and responses may explain a proposed revision. Saved drafts can be sent
or withdrawn; reopening their text for editing is not yet a separate engine action.

## Demonstration and regression evidence

`tools/playtest_collective_action.py` uses only fictional Alex, Casey and Morgan.
It drives displayed keys/forms in a real PTY or a loopback ttyd WebSocket:

1. Select Alex, inspect O and N, return to W and inspect Alex → Casey and reverse.
2. Send a contact invitation; switch to Casey, read it once in the inbox and accept.
3. Inspect the acknowledged connection in the network, scope/filter controls and
   experimental yaw/pitch camera.
4. Propose a contract from that connection; accept once, amend as the other party,
   verify receipts cleared, then independently accept the same version 2.
5. Inspect authoritative history.
6. Select Alex → Morgan and propose directly with no invitation or connection
   involving Morgan. Independently accept the proposal as both parties.
7. Verify two accepted/unverified contracts, one accepted invitation, persistence
   after a fresh process, replay and native trajectory YAML round-trip.

```sh
.venv/bin/python tools/playtest_collective_action.py --output /tmp/new-collective-pty
.venv/bin/python tools/playtest_collective_action.py --output /tmp/new-collective-ttyd \
  --ttyd /path/to/ttyd
.venv/bin/python -m pytest -q
```

The existing matrix/negotiation playtest also passes, including 52×18 resize and
restart. The broader suite retains frozen-engine/Hube compatibility checks,
HTTP sessions/CSRF, source pagination/privacy and a standalone wheel installation
without neighbouring Hube or trajectory checkouts. Initial sandbox-only HTTP
failures were localhost bind permission errors; rerunning with localhost access
resolved them. This is automated acceptance and local visual review, not an
independent novice usability study or a deployed service.

Validation results:

- Complete suite: **164 passed**, including the existing compatibility, HTTP and
  standalone-installation checks. The included Hube compatibility test executes
  its 58 original regression cases.
- Focused mathematical, playability, navigation and invitation tests: **93 passed**.
- Final local PTY dual-path/restart/trajectory evidence:
  `/private/tmp/saddle-collective-action-pty-final/`.
- Final ttyd dual-path/restart/trajectory evidence:
  `/private/tmp/saddle-collective-action-ttyd-final/`.
- Earlier matrix/negotiation/52×18 resize regression:
  `/private/tmp/saddle-collective-action-old-regression-01/`.
- Actual browser visual review and saved screenshots (fictional data only):
  `/private/tmp/saddle-collective-action-browser/relationship.png` and
  `/private/tmp/saddle-collective-action-browser/inbox-final.png`.
- `git diff --check` and Python compilation pass. The original empirical world is
  still state 8 with its original hash, and replay succeeds.

Every acceptance run leaves two accepted/unverified contracts and one accepted
contact invitation in its own fictional world at state 12. The visual-test server
on port 8768 was stopped; the user's port 8767 session was not replaced. Quit an
older running game with `q` and reconnect/reload the browser to load updated code.
Validation checkout: `main` in
`/Users/kumiori3/Documents/WIP/Society/game_commons`. Private captures, saved worlds
and terminal transcripts are outside the repository checkpoint.

## Files and interfaces changed in this sprint

This list separates this sprint's edits from the substantial pre-existing dirty
worktree. No earlier changes were discarded or silently committed.

| File | Change |
|---|---|
| `commons_game/expertise.py` | One bounded incidence product; partial observations; consistent cell/edge evidence |
| `commons_game/montreal_capture.py` | Preserve explicit partial answer state |
| `commons_game/invitations.py` (new) | Contact schema, validation, lifecycle, connection acknowledgement and expiry |
| `commons_game/engine.py` | Register contact commands; atomic existing-table transitions; optional contract origin |
| `commons_game/projections.py` | Invitation nodes, directed requests, distinct acknowledged connections and collision-safe person labels |
| `commons_game/player.py` | Engine-validated contact decisions; canonical deduplicated inbox records and filters |
| `commons_game/presentation.py` | Invitation vocabulary and first-name collision labels |
| `commons_game/catalogue.py` | Shared collision labels with unchanged canonical identity/order |
| `commons_game/commands.py` | Contact command and stable I aliases |
| `commons_game/play.py` | Readable contact forms/drafts, line-mode inbox/inspection and proposal settings hook |
| `commons_game/fullscreen.py` | O/N/W explorer, progressive inspectors, direct decisions, inbox wrapping, dual paths, graph scopes/camera |
| `commons_game/network_view.py` | Layer filtering, full/rendered coverage and experimental 3D adapter |
| `commons_game/tui.py` | Contact command/event presentation labels |
| `commons_game/trajectory.py` | Additive invitation/connection frame summaries; unmodified authoritative envelope |
| `tests/test_collective_action.py` (new) | Mathematical, identity, lifecycle, authority, dual-path, navigation and rendering regressions |
| `tests/test_matrix_navigation.py` | Correct exact-zero expectation for complete empty vector × missing vector |
| `tools/audit_matrices.py` (new) | Immutable-prefix read-only audit with optional existing private capture comparison |
| `tools/playtest_collective_action.py` (new) | Reproducible PTY/ttyd dual-path acceptance and restart/export evidence |
| `tools/playtest_matrix.py` | Adapt displayed settings/inbox route; optional third-person fixture need; robust child cleanup |
| `README.md`, `docs/MILESTONES.md`, this report | Player controls, implemented/experimental boundary and validation |
