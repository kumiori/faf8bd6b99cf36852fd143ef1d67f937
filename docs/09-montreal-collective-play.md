# SADDLE PATHWAYS — Montréal collective-play sprint

Historical checkpoint. The [playable-terminal sprint](10-playable-terminal.md)
supersedes the two-person sample and mock-manifest opening flow below. Sample
evidence was moved to the private external data directory; no source data was lost.

4 November 2026. Baseline: Commons `5405249`; the Hube M0 freeze and pinned
trajectory-engine source remain unchanged. This sprint extends projection and
interaction over the existing engine. It does not introduce a new governance
engine, graph store, history mechanism or authentication service.

## What the player can now do

The terminal supports ecosystem exploration without a role, explicit simulation
sign-in, profile inspection, pending claims, actor/contract neighbourhoods,
contract filtering, proposal/acceptance/amendment actions, an attention inbox,
historical graphs, recorded trajectories and replay. Successful contract actions
return a stable contract reference with `o`, `g` and `h` navigation.

Graph commands are `open ID`, `history ID`, `past SEQUENCE ID`, `act ID`, `list`,
and `contracts` with optional `actor=`, `status=`, `objective=` or `resource=`
filters. Inspecting an actor exposes their linked contracts; inspecting a
contract exposes its parties, current terms, resources, policy and evidence.
The existing `party_to` relation is reused. New relations are `proposed_by`,
`concerns_resource`, `serves_objective`, `requires_authorisation` and `has_evidence`.
No `addresses_need` edge is inferred from similar text: contracts currently have
no explicit need-ID field. Lifecycle status and `outcome_status` remain separate.

The registry retains rejected and expired contracts. Historical views use
`project('network', at=...)` over the same event prefix; they never mutate the
current world. Graph appearance is independent of acceptance and verification.
Long terminal lines wrap to the available width; `--plain` uses portable border
decorations while preserving source names and accents.

## Read-only source mapping

`saddle-ecosystem-snapshot/v1` contains `captured_at` and `records`. Each record has
`kind`, `data_source_id`, `record_id`, optional `database_id`, `created_at`,
`last_edited_at`, `epistemic_status`, `source_properties` and a domain `fields`
mapping. The importer only accepts the following domain fields.

| Kind | Fields | Commons meaning |
|---|---|---|
| person / organisation | label | Actor representation with no imported gameplay roles |
| affiliation | source_id, target_id | Reported affiliation; no representation authority |
| relationship | source_id, target_id, relation, directed | Source relationship with explicit or unknown direction |
| capacity / need | actor_id, domain, quantity, unit | Reported assertion; missing quantity/unit remain unknown |
| resource | owner_id, label, quantity, unit | External, reported resource; requires existing reconciliation rules before activation |

Stable IDs hash the source kind, data-source ID and record ID. Display names never
reconcile people. The import retains original property names and source/capture
timestamps separately, plus source fingerprints, epistemic status, import version
and read-only synchronisation status. Missing values never become negative facts.
Inferred records retain their status and do not become verified relationships or
accepted offers. Missing units do not yield a complementarity match.

Imports cannot supply contracts, commitments, approvals, identity grants or roles.
An import report lists created, updated, skipped and rejected records. Valid
records and the report are appended atomically to the existing event log under
the same SQLite transaction lock. An identical snapshot is a no-op. Older captures
are rejected per record; absent records are retained. Explicit archives require
review and do not silently remove an actor or alter a contract. A resource already
referenced by a contract is not overwritten by a changed source assertion.

Raw properties do not enter the world. Only allowlisted domain values, property
names and their fingerprint survive. Use private local paths for source snapshots,
worlds and exports; exporting a trajectory includes the empirical world records.

## Source evidence and adapter reuse

Inspected sibling interfaces:

* `temporal_graph/ingestion/notion_client.py`: the independent read-only transport,
  reused directly by `capture-notion` through its explicit sibling-project path.
* `ingestion/fetch.py`: full query/property pagination and conservative removal.
* `ingestion/normalize.py`: source-local identities, observation times and missingness.
* `protocol/ecosystem.py` and `protocol/multiplex_v2.py`: source provenance and
  separation of documented relations from potential complementarity.

The normaliser is not imported as a dependency: its questionnaire-specific
analysis stack and private profile handling do not belong in the game engine.
Commons implements its own small allowlisted mapping while reusing the transport.
The optional `notion` extra supplies the SDK; offline import needs neither SDK nor
credentials. Capture follows the sibling token precedence and exposes only reads.
Source mappings explicitly name property fields and reference source kinds/IDs.
`config/notion-mapping.example.json` is preparatory, not a source capture.

For the initial empirical world, the connected Notion service was queried
read-only. Montréal scope was checked through linked questionnaire response
records. A controlled subset of two people was exported using only source URL,
creation time, `Name` and `institution`. The capture, selection note, snapshot,
mock manifest, SQLite world and entered terminal transcripts are local under
`.commons-private/`, ignored by Git. No Notion record was written.

An institution stored as free text has no independent organisation page in that
source. It becomes a **source-local organisation mention**, retaining the person's
page ID and original `institution` property in its provenance. The importer neither
invents an organisation database ID nor merges equally named mentions across
people. Reconciliation with a canonical organisation database remains future work.
Source creation time dates the source record, not the founding of an organisation.
Last-edit time was unavailable in the selected connector export and remains null.
Engine event times remain deterministic simulation times; actual source/capture
times live separately in record provenance and are not reconstructed from them.

## Identity and claiming boundary

`PlayerIdentity`, `ActorBinding` and `IdentityProvider` are separate interfaces.
The only implementation is `MockIdentityProvider`: selecting a provisioned subject
simulates sign-in. Its local manifest explicitly grants simulation bindings.
It never consumes a Notion password, email, access key, affiliation or consent
checkbox to grant authority. A personal binding cannot represent an organisation;
an organisational mock role needs an explicit `organisation` grant.

A bound player session injects its actor and rejects actor spoofing. It cannot
switch actors through hot-seat; the player signs out and signs in again. The
provider grant is checked on each action. Session context in commands, audit
records and trajectories says `mode=simulation`, `authenticated=false`. Mock
acceptance receipts use `method=mock_identity_simulation`. Legacy actor-selected
sessions retain `local_simulated_identity`; their purpose is local development.

Claims are pending records in the existing world's configuration/event history.
They never grant bindings or create actors. Repeated identical requests are
idempotent. An unbound mock player may request an existing representation or a
new profile for later review, avoiding automatic display-name-based duplication.
No claim-review or approval UI is implemented. Update a trusted development
manifest to provision a mock grant; that is not identity verification.

**Genuine login, real consent and live play remain unavailable.** Production
OAuth/OIDC token verification, secure session handling, independent claim review,
revocation and institutional delegation require a separate authorised milestone.
The raw local CLI and legacy loopback browser remain simulation tools, not
production security boundaries. All three modes still share one engine.

## Acceptance evidence

| Feature | Implemented | Wired | Verified |
|---|---|---|---|
| Contract visibility and navigation | Existing projection extended | Ecosystem, graph, inspectors, direct references | Entered terminal play and lifecycle/replay tests |
| Ecosystem import | Conservative mapper and import reports | CLI capture/import and Montréal world | Connected Notion subset imported and terminal-inspected; generic mapper tests |
| Player identity and binding | Provider/identity/binding interfaces | Mock sign-in, profile, sign-out | Independent players; spoofing, missing grants and organisational boundaries tested |
| Claims | Pending, replayable records | Onboarding/profile request flow | Idempotence and no-grant tests |
| Contract inbox | Pure permission-aware projection | Inbox to inspector and actions | Second player discovers and accepts; lifecycle attention tested |
| Persistence and trajectory | Existing SQLite log/native adapter | Restart, history, graph-at-event, package export | Concurrent submissions, stale writes, duplicate retries, restart and round-trip |

The empirical playtest proposed one contract, inspected its graph, signed out,
entered the second mock player, accepted both parties' exact version, restarted
and reconstructed the native package export. Five events recover the same world.
Final lifecycle is **accepted**, outcome **unverified**. No delivery or independent
verification was fabricated. The original synthetic end-to-end verification path
remains available and tested independently.

`tools/playtest_collective.py` reproduces the same CLI flow using fictional records
and preserves entered input, transcript, database and native trajectory in a new
output directory. It uses separate processes for players and restart. Public
tests contain no private source identities. The previous bilateral input and
transcript remain historical checkpoint artefacts; their filenames and schema
identifiers are retained for compatibility.

Final validation: **70 Commons tests passed**, including the compatibility test
that runs all **58 original Hube tests** and checks the frozen baseline artefacts.
The full suite ran with loopback access for the existing HTTP tests. The public
fictional CLI demonstration passed independently. Editable package installation
and the installed `saddle-pathways --help` entry point also passed.
The standalone SDK capture path has pagination tests using a fake read-only
client; the live empirical capture used the connected Notion service rather than
the optional SDK. No production identity provider or deployment was exercised.
