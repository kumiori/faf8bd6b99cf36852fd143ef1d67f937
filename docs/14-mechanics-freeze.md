# SADDLE PATHWAYS mechanics freeze candidate

This checkpoint covers the Montréal world and the current terminal interaction.
The reference for gameplay is commit `6c60009`. The authoritative rules,
canonical records, import logic and graph projection are unchanged. The
comparison used the private local Montréal save read-only and exercised additional
transitions with fictional fixtures.

## Domain vocabulary

| Concept | Canonical representation and meaning |
| --- | --- |
| Actor | A person or organisation with a stable ID, status, category, roles and provenance. The playing actor, an inspected actor and a bound identity are distinct. |
| Capability and need | `capacities` and `needs` records describe what actors report or source data records. Unknown inputs remain unknown. Domain matches and matrix cells are derived. |
| Relationship | A typed record in `relationships` with endpoints, status and provenance. A source affiliation is stored as a declaration. A potential complementarity is inferred. |
| Contact invitation | A directed `contact_invitation` relationship with sender, recipient, message, optional origin and expiry, and response. Acknowledgement creates a separate undirected `acknowledged_connection`. Gathering attendance uses the separate existing `invited` kind. |
| Contract | An `agreements` record and first-class graph node. It has parties, proposer, objective and numbered versions of declarative terms, responsibilities, conditions, resource allocations, expiry, policy and verification criteria. |
| Acceptance and authorisation | Separate receipts tied to a named actor, agreement ID, version, content digest and action. All parties must independently accept the current terms. Institutional approval applies the named policy. |
| Resource and reservation | A resource has an owner, control and quantity. Activation holds quantities through `reservations`; the engine checks the total held amount before committing. |
| Commitment | A responsibility assigned to a party and created on activation. It records execution, reported fulfilment and verification separately. |
| Evidence and outcome | Evidence links execution, reports or independent verification to the relevant action and agreement version. An objective counts an agreement only after its outcome is verified. |
| Action, event and commit | An accepted command produces an action record and one ordered event with atomic mutations. Commit metadata links that event to the acting authority and previous/resulting state digests. |
| Configuration and objective | World clock, source and simulation metadata, and registered success criteria. An objective's supporting agreements and status are computed on accepted transitions. |

The canonical table list is in [model.py](../commons_game/model.py). Commands
and governance checks live in [engine.py](../commons_game/engine.py) and contact
rules in [invitations.py](../commons_game/invitations.py).

## Transitions and permissions

| Command | Existing rule and effect |
| --- | --- |
| `draft_contact`, `send_contact` | An active person can draft or send to a different active person. An optional origin records source and world context. Delivery stays inside the simulation. |
| `publish_contact`, `withdraw_contact` | The sender publishes a draft or withdraws a draft or sent invitation. |
| `respond_contact` | Only the recipient can accept or decline a sent invitation. Acceptance records the response and acknowledged connection in the same event. It creates no agreement or acceptance receipt. |
| `draft`, `propose`, `publish_proposal` | A listed party creates a draft or proposal. A party may publish a draft. A proposal carries no implicit acceptance, including from its proposer. A contact invitation is optional. |
| `amend` | Any party may amend a draft, proposal, negotiation, accepted or authorised agreement. Prior terms and receipts remain in their superseded version. The new version begins in negotiation with fresh acceptance and authorisation. |
| `accept` | Each party accepts a proposed or negotiating current version in their own name. Duplicate and stale receipts are rejected. The agreement reaches accepted when every party has a receipt. |
| `authorize` | An eligible policy actor approves after party acceptance. The threshold, required actors and categories govern the institutional decision. |
| `activate` | A party activates after all acceptances, policy approval and resource checks. The transition creates commitments and holds allocations atomically. The existing gathering objective can also require attendance. |
| `initiate`, `fulfill` | A party assigned a responsibility records its execution, then reports fulfilment against the criteria. The agreement reaches fulfilled when all commitments have been reported fulfilled. |
| `verify` | An eligible verifier outside the parties records independent evidence after fulfilment. The agreement stays `fulfilled` with a distinct `outcome_status=verified`; commitments become verified, reservations are released and the objective is evaluated. |
| `reject`, `withdraw` | Any party may reject in draft, proposed or negotiating states. Any party may withdraw in those states and in accepted or authorised states. Both require a reason and close the agreement. |
| `suspend`, `resume`, `dispute`, `terminate` | A party can suspend active work, resume suspended work subject to policy, dispute active/suspended/fulfilled work, or terminate active/suspended/disputed/fulfilled work. Suspension and dispute retain holds. Termination releases them. Verified outcomes are final. |
| `advance_time` | A facilitator advances the world clock. Pending contact invitations and eligible unverified agreements expire inside that same transaction. |
| `declare`, `reconcile_resource` | Declarations record player provenance for approved relationship/capacity/need payloads. An independent resource verifier may reconcile an external resource without reducing its quantity below existing holds. |
| `invite`, `respond_invitation` | Existing gathering attendance commands. The recipient decides on a pending attendance invitation. These transitions are separate from invitations to connect. |

The current agreement withdrawal authority is the party rule above. The
proposer-only or explicitly delegated rule discussed in the freeze notes
would change gameplay and belongs to a future domain decision. The simulation
binds each submitted action to its selected actor via `ActorSession`.
Development hot-seat changes are explicit. Imported membership or provenance
does not confer live identity authority.

## Event and replay invariants

- Initialization, source import and pending binding requests emit
  `world.initialized`, `ecosystem.imported` and `identity_binding.requested`.
  Contact commands emit `invitation.drafted`, `invitation.sent`,
  `invitation.accepted`, `invitation.declined` or `invitation.withdrawn`.
  Other accepted commands emit `<command>.accepted`, including
  `reject.accepted` for the accepted command to reject a contract.
- Event sequence and event time are ordered. Replay checks the mutation chain
  and Commons state digests. Domain-clock changes are themselves recorded.
  Rejected commands append no event. Identical retries reuse their recorded
  result; reusing a key with different input fails.
- Contact acceptance, reservation and verification changes are atomic with
  their related records. A report and an independent verification remain
  separately attributed. `world_at` and restart derive state from persisted
  mutations. Network, inbox, matrices and trajectory views consume that state.
- The saved Montréal audit replayed all nine committed prefixes and checked
  their state and graph against historical reconstruction. Its event counts
  were one initialization, three imports, three proposals and two party
  acceptance commands. World and graph fingerprints matched before and after
  the changes, and the audit left the SQLite file byte-identical. That save
  contains no contact or verification history, so those paths were exercised
  with a fictional restart fixture and terminal playthrough.

## Montréal graph inventory

Counts refer to the full projection of the audited local save at event 9.
This is a typed graph of game objects and relations.

| Node kind | Count | Origin |
| --- | ---: | --- |
| Person | 43 | Actor records |
| Organisation | 28 | Actor records |
| Capacity | 211 | Individual offer records attached to actors |
| Need | 290 | Individual request records attached to actors |
| Agreement | 3 | Versioned contract records |
| Objective | 1 | Objective record |
| Policy | 1 | Governance record |
| **Total** | **577** | **71 actors and 506 other objects** |

Resources, invitations and evidence are supported node kinds with zero in this
snapshot. Expertise labels are attributes of the capacity/need records here.
Commitments, reservations, action records and approval receipts are available
through their world records and linked inspectors, with no standalone nodes
in this projection.

| Edge kind | Layer | Count | Origin |
| --- | --- | ---: | --- |
| `affiliated_with` | declared | 28 | Stored source affiliation assertions |
| `declared_by` | institutional | 211 | Capacity incidence |
| `expressed_by` | institutional | 290 | Need incidence |
| `party_to` | agreement | 6 | Agreement party references |
| `proposed_by` | institutional | 3 | Agreement creator reference |
| `requires_authorisation` | institutional | 3 | Current version policy reference |
| `serves_objective` | institutional | 3 | Agreement objective reference |
| `potential_complementarity` | inferred | 3,527 | Directed possible matches derived from source observations |
| **Total** | | **4,071** | **28 stored, 516 structural, 3,527 inferred** |

The 516 structural edges are regenerated from authoritative references. The
3,527 inferred edges describe potential complementarities, with no implication
of contact, consent or collaboration. All endpoints resolve. Two people have
zero incident edges in the full projection. The viewport can bundle multiple
edges or omit them by page/scope/layer. Dark points are people and organisations
outside the visible foreground, with rings identifying full-projection
isolation. Stable point slots depend on the actor roster and viewport dimensions.
Foreground marks may occlude points.

## Terminal interaction contract

In the full-screen terminal, `Esc` or `b` goes back, Enter inspects or confirms,
Up/Down moves through choices, and Tab/Shift+Tab changes available regions.
`?` opens help. `m` opens Paths, `e/g/s` resume Ecosystem/Gathering/Scenarios,
`c` opens Contracts, `i` opens Inbox, and `p` opens Player. Text-entry prompts
reserve printable characters for input and Esc cancels the form. The line-mode
fallback uses entered commands and numbered links.

Each route retains its selection, scroll, filters and viewport where applicable.
Graph `S` changes scope, `L` filters layers, `[ ]` pages objects, `f` centres
on the selected object, `+/-` zooms and `r` rotates. Enter follows the current
selection from the canvas or list. Planar layout fits the available canvas and
keeps fixed positions as selection changes. Labels use free cells, truncation
and fallback markers; object links and inspectors expose full display labels.
The 3D camera remains experimental.

The contract inspector separates engine-permitted **Decisions** from
**Explore** links and **Details**. The **Proposer** and **Counterparty** rows
show each party's independent receipt for the exact current version. Selecting
an object link changes focus and keeps the acting identity. Navigation context
is per terminal session; an application restart reconstructs the world and
history from the saved event log.

## Validation

The restart regression exercises invitation acceptance and decline, rejection
by a party, amendment, stale-version denial, separate party receipts, policy
approval, activation, execution, reported fulfilment and independent
verification. It compares the world and graph at every event prefix and checks
a new process against the persisted SQLite history.

Run the Commons suite and the two fictional terminal playthroughs with the
test, terminal-test and trajectory extras installed. Each playthrough uses a
fresh temporary output directory.

```sh
python -m pytest -q
output=$(mktemp -d)
python tools/playtest_matrix.py --output "$output/matrix"
python tools/playtest_collective_action.py --output "$output/collective"
```
