# Extension 01. Reconstruct the Network

## Playing the first iteration

Start the Montréal world with `python -m commons_game play`. Select your
existing simulated participant, then choose **4 EXERCISES** under Paths and
**Montréal · Reconstruct the Network** in the Workshop. Activate the selected
**BEGIN RECONSTRUCTION** control after the interruptible opening.
Set `COMMONS_REDUCED_MOTION=1` for a static opening. The exercise is an Ecosystem activity
and uses the same authoritative world and actor session as the other paths.

Select a participant, inspect the profile, and press **c Connect**.
The choices distinguish a Montréal recollection, an invitation to connect
now, and a declaration that you already knew the participant before Montréal.
Confirming a recollection records your account. Your target receives no
acceptance receipt from that action. A new invitation uses the existing
contact form and recipient inbox. Contracts keep their existing workflow.

Use Up/Down to select, Enter to inspect, Tab to move among Directory,
Profile and Network, **n** to focus the network, **/** to search, **f** to
open counted facets, and **o** to sort. Values within a facet use OR, and
different facets combine with AND. A Connections value offers people whose
recorded offers match your needs. Within Profile, arrows scroll its contents.
Within Network, arrows scroll observation descriptions, **L** toggles observation
groups, **v** changes neighbourhood/collective view, **G** opens the full graph,
**d** inspects provenance, and **[ ]** pages the focused graph. **C** opens Contracts
in this screen because **c** is explicitly labelled Connect. The other global
shortcuts retain their meanings. Back restores the previous screen.

Wide terminals show three columns. Intermediate widths show the directory
beside profile or network. Narrow terminals show the selected region.
The curses screen reloads the shared world every 1.5 seconds while idle.
Pending forms keep their original expected revision and require a fresh
submission if another participant changes the world.

Profiles use the existing questionnaire observations and recorded affiliations.
Missing motivations read **Not yet recorded**. An answered empty expertise
field reads **None declared**. Unknown and partial observations retain their
status. Filters appear for fields with available data. Connection filters and
sorts count recollections in the selected exercise context. Shared-offer and
shared-need ordering compare declared attributes and imply no encounter.
Motivation similarity remains deferred.

Constellation portraits use a versioned SHA-256 seed, stable actor IDs and
declared offers/needs. The function supports three sizes, monochrome Unicode,
ASCII and a textual equivalent. Relationship changes do not affect the portrait.
The small glyph depicts a decorative fingerprint.

## Audit of the existing actions

| Need | Existing capability | Implementation |
| --- | --- | --- |
| Declare a generic relationship | `declare` records a reported `knows`, `collaborates_with` or `affiliated_with` relation | Preserved. It lacks historical context and retraction. |
| Invite someone | `send_contact`, or draft then publish | Reused unchanged. |
| Acknowledge current contact | The recipient's `respond_contact` accepts a sent invitation and creates the acknowledged connection atomically | Reused unchanged. |
| Reconstruct an encounter | No actor-owned, context-scoped historical claim lifecycle existed | Added the small claim extension below. |

## Claim and projection contract

All records live in the existing `relationships` table. The new commands
flow through the existing validation, actor binding, SQLite transaction,
expected revision and idempotency boundaries.

| Command | Payload beyond the existing envelope | Meaning |
| --- | --- | --- |
| `recall_connection` | `target_id`, `context_id`, optional `historical_date` and `note` | Attribute a directed recollection to the acting person. |
| `record_prior_relationship` | Same payload | Attribute a prior relationship declaration separately. |
| `dispute_recollection` | `claim_id`, optional `note` | Only the target can dispute a currently claimed recollection. |
| `retract_relationship_claim` | `claim_id`, optional `note` | Only the author can retract their active or disputed claim. |

The declaration time is the engine's recorded event time. The optional
historical date has its own field. Montréal's historical date remains unknown
until supplied from a source. The configured historical context is
`montreal-forum`. Context IDs are supplied by the trusted host configuration.

A person's first claim is stored as `claimed`. Two reciprocal, unretracted,
undisputed recollections in the same context derive one undirected
`corroborated_recollection` edge with both claim IDs and event references.
The underlying claims remain directed. A dispute derives a disputed view and
preserves its author. Retraction removes the claim from the active projection
while preserving the record and event history. After retracting, the author
can record a corrected claim. Different contexts and prior relationships
stay separate. Corroboration describes mutual recollection.

Exact retries return their existing result. Another active claim by the same
author, target, kind and context is rejected. Concurrent submissions are
serialized by the existing store. A stale revision is rejected for refresh and
retry. The client cannot bind a claim to someone else's actor identity.
Existing saves require no schema migration.

The network retains distinct layers for historical evidence, unilateral
recollection, mutual recollection, dispute, prior relationship, pending
invitation, accepted connection and inferred complementarity. Layer filtering
makes overlapping observations inspectable. The existing renderer draws
recollections dotted, mutual recollections solid, and prospective invitations
dashed. The exercise's ring means no recollection is recorded for that actor
here. Background points show actors outside the focus. Neither mark measures
their actual social connectedness.

Statistics distinguish active directed claims, unique recalled pairs,
corroborated pairs, unilateral pairs, disputed pairs, active contributors,
your active claims, pending invitations and accepted current connections.
Invitation counts cover contact records among this world's participants.
They do not establish that an invitation originated in this exercise.

## Optional historical sources

The exercise works with no imported sources. A trusted local import can later
add supplied participant statements, photograph references and explicit
whiteboard transcriptions into the existing `evidence` table.

```sh
python -m commons_game --db /path/to/world.sqlite import-reconstruction-sources sources.json
```

The document is ordinary JSON under the existing world/event architecture.

```json
{
  "schema": "game-gamer/reconstruction-sources/v1",
  "records": [
    {
      "id": "whiteboard-photo-01",
      "kind": "whiteboard_photo",
      "context_id": "montreal-forum",
      "reference": "archive/photo-01.jpg"
    }
  ]
}
```

A `participant_statement` additionally requires `actor_id` and `statement`.
A `whiteboard_connection` requires `source_id`, `target_id`, `directed`
(true, false or null), and `observation` (possible, transcribed or
verified_transcription). Every record requires an ID, context ID and source
reference. A verified transcription describes the source-reading status.

An import validates the full batch before one atomic
`reconstruction.sources_imported` event. Reimporting identical IDs is
idempotent. Conflicting content requires a fresh source ID. Photographs alone
produce no edges. Uncertain direction remains null. Source records preserve
their references and observation status. The standalone portable world schema
also accepts these records through its optional `reconstruction_sources`
field at initialization.

Whiteboard overlap analysis and Jaccard comparisons remain in iteration 2,
after identity, direction and observation conventions are agreed.

## Reusable boundaries and validation

Game-Gamer supplies the claim rules, source validation, reconstruction
projection, participant directory/filter/profile models, portrait generator
and responsive screen composition. The Montréal host supplies its context,
wording, participant roster and questionnaire mapping. The package's three
primary navigation modes remain Ecosystem, Gathering and Scenarios.

The public test boundaries cover authoritative submission and history,
SQLite restart/concurrency, detached projections and the terminal screen
controller. The golden Commons extraction baseline protects existing game
trajectories. The Hube suite remains a separate compatibility check.

```sh
python -m pytest -q
(cd game-gamer && ../.venv/bin/python -m pytest -q)
output=$(mktemp -d)
python tools/playtest_reconstruction.py --output "$output/reconstruct"
```

The terminal playthrough uses fictional participants, two explicitly selected
simulation roles, reciprocal recollections, narrow/wide resize and replay.

The implementation validation passed 179 Commons tests, 20 standalone
Game-Gamer tests and 58 Hube tests. The reconstruction, matrix and collective-action
PTY playthroughs passed. A read-only check of the saved Montréal world fitted
Directory, Profile and Network at 40×16, 52×20, 100×32 and 144×34, verified replay
and left the SQLite bytes unchanged.


The current consolidation adds a separate Workshop, three isolated tutorials,
permission-controlled curator operations and revision-based presentation caching.
See [the consolidation report](18-playability-consolidation.md) for measured
performance, schema details and current validation evidence. Montréal wording
is marked `COPY_REVIEW_REQUIRED: Natalie`.
