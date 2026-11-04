# Commons development milestones

Roadmap adopted on 3 November 2026; supplemented on 4 November 2026 for
**SADDLE PATHWAYS**, trajectory compatibility and terminal-first development.
The accepted conceptual foundations and M0–M5 order are preserved. M0's Hube
freeze remains intact. The small terminal/trajectory integration below is an
architectural checkpoint, not completion of every later gameplay milestone.

## 4 November sprint — playable terminal and complete scoped capture

The subsequent [relational playtest correction](12-relational-playtest.md) makes
the fixed-scale heatmap the default, preserves separate player/focus/relation
contexts and extracts Hack's existing terminal raster into a neutral component.
Network is now a selectable typed diagram with contract/objective/policy links.
Scenarios distinguishes authored workshop framing from registered objectives
and contracts. Gathering exposes the existing invitation/activation gates without
claiming Hube feasibility integration or a registered Montréal event objective.

Jeanne's complete observation/navigation sequence passed in local PTY and real
ttyd transports on private copies of the 41-person saved world, following an
actual matching counterparty's existing contract. No contract or consent was
invented for that acceptance, and the copied state/history remained unchanged.
The proposal/negotiation/restart acceptance also remains operational. These
corrections preserve engine semantics and do not close unimplemented gameplay gates.

The subsequent [matrix-first navigation sprint](11-matrix-first-navigation.md)
adds a full-screen POSIX/ttyd viewport, persistent screen stack, explicit mode
selection, the directed expertise matrix with strict missingness, negotiated
contribution forms, typed policy links and a perspective-specific grouped inbox.
The authorised capture now retains minimal offer/need answer states and domain
codes in a read-only source mapping. All 41 eligible people are reconciled;
40 off-diagonal matrix cells remain unknown because one needs response was skipped.

Local PTY and real ttyd acceptance exercise proposal, initial acceptance,
counterparty negotiation, renewed acceptance, historical inspection, native
trajectory/replay, mode switching, resize and restart. They end
**accepted / unverified**. Montréal's missing gathering objective and the absence
of coalition strategy search are explicitly labelled. These presentation changes
do not close later M1–M5 governance or planning gates.

Current player entry point: `saddle-pathways`, with no subcommand. The ordinary
simulation interface uses the full imported person catalogue, name search,
organisation filtering, numbered/cursor navigation, connected-object inspection,
contract short references, an inbox and contextual command help. No mock manifest
or production-login entry is required. Developer fixtures remain separate.

The complete authorised source capture inspected 99 records (41 people, 58
responses). All 41 eligible named person records appear in the default world.
The capture includes 28 source-local organisation mentions, 211 capacities and
290 needs. One submitted inventory lacks a resolvable person record; it is reported
without inventing an actor. Organisations are not merged by label.

The player-facing demonstration selects a person, discovers an inferred peer,
proposes, switches simulated participants, responds, inspects consequences,
restarts and replays using names/numbers only. It ends accepted/unverified.
The default private world preserves the earlier five-event checkpoint and contract.

The shared presentation vocabulary, source reconciliation, command audit and
regression/standalone-install evidence are recorded in
[10-playable-terminal.md](10-playable-terminal.md). These are interaction and
capture improvements; the remaining M1–M5 gates are not retroactively closed.

## Earlier 4 November checkpoint — inhabitable collective play

The definitive title is **SADDLE PATHWAYS**. All new prose and interface labels use
British English; existing API/schema identifiers remain compatible. The first
empirical world is **Montréal Commons**. Montréal-to-Geneva remains a possible
scenario; Hube remains the frozen regression world.

| Deliverable | Current status and evidence boundary |
|---|---|
| Contract visibility | Implemented and exercised in terminal: proposal reference, graph neighbourhood, parties, objective, resources, policy, evidence, lifecycle and separate outcome; historical projection and replay agree |
| Read-only ecosystem import | Implemented for people, organisations, affiliations, relationships, capacities, needs and documented resources; connector capture of a controlled Montréal subset imported and inspected locally |
| Identity binding | Implemented and tested with an explicit local mock provider; bindings are independent of Notion, and organisational grants are explicit; genuine authentication is not implemented |
| Onboarding | Exploration, mock sign-in, profile inspection, sign-out and pending claims; unverified claims grant no actor or acceptance authority and do not duplicate actors |
| Inbox | Derived from authoritative state and engine permissions: responses/amendments, authorisation, obligations and independent verification requests |
| Persistence and trajectories | Separate mock players negotiate in one SQLite log; stale writes fail, exact retries are idempotent; restart and native package round-trip recover the same world |

All actions remain simulated. The empirical two-player demonstration ends at
**accepted / unverified**: no fulfilment or independent verification is fabricated.
Production OAuth/OIDC, verified claim adjudication, institutional delegation and
public deployment remain preparatory. See [the sprint evidence](09-montreal-collective-play.md).
These deliverables do not close all of M1–M5.

## Checkpoints and scope

* Commons `f082967d47c87e97f4a62dbe7536b6f3743c097b`, tag
  `checkpoint/commons-before-m0-m5`.
* Hube `52fbfe1d74c1c46d804b45a39e25231399f090bc`, tag
  `checkpoint/hube-before-contract-upgrade`.

These capture work already present when the commit-first instruction arrived.
They are not retroactively described as pre-extraction snapshots. The original
inspection's hashes remain in `hube-baseline.json`; current frozen scenario and
acceptance hashes are recorded separately in `M0_BASELINE.json`.

## Frozen distinctions and decision rule

* A promise is a declared intention, with its own epistemic status.
* A contract is a first-class graph node recording parties, versioned terms,
  obligations, conditions, acceptance rules and evidence.
* A commitment is an accepted responsibility; it is not a transaction commit.
* A commit is an authorised, auditable change to authoritative state.
* Execution, reported fulfilment and verified outcome remain distinct.
* Acceptance immediately changes governance state. Verification later changes
  fulfilment state. Neither transition must be withheld to simulate the other.

For M1 and the first vertical slice, **every party explicitly accepts the same
immutable version**. An amendment invalidates current acceptance and approval;
old receipts remain in history. Institutional authorisation is additional to
party acceptance. A threshold of institutional approvers does not replace the
parties' own acceptance.

Collective authorisation may later bind an organisation only through an explicit,
previously agreed voting/delegation rule. It is not an implicit exception. Scoped
delegation in M2 must identify principal, delegate, permitted operation, subject,
version, validity and revocation. It must not silently permit personal acceptance
on someone else's behalf.

Contracts contain declarative data. A registered, restricted governance rule
interpreter resolves them. No player-provided Python, JavaScript, callable,
expression evaluation or arbitrary predicate execution is permitted.

**One authoritative engine.** The trajectory package consumes read-only
projections of Commons history; it never decides governance outcomes, writes a
saved world, or independently applies authoritative transitions. K in the frozen
state decomposition denotes commitments. Commits remain transaction records;
the trajectory integration does not silently redefine that distinction.

**Terminal first.** The initial interactive environment is the terminal laboratory.
No Streamlit application, web dashboard or graphical network is required for any
M0–M5 acceptance gate. Existing browser files are preliminary legacy scaffolding;
they are not extended in this checkpoint.

## M0 — Audit and freeze Hube

Objective: establish and preserve the actual functioning baseline. Deliverables:
`04-M0-freeze.md`, source inventory, checkpoint refs, frozen fixture hashes and
the existing 58 regression tests. Preserve interactive play, deterministic
simulation, provider consent, independent verification, quantity allocation,
six-condition feasibility, history, persistence, replay and locale equivalence.

No new gameplay. A test failure or unexplained canonical-state drift blocks M1.

Add the actual trajectory-package audit, [05-trajectory-audit.md](05-trajectory-audit.md):
the supplied address is a repository, release `0.2.0`, pinned commit
`757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`. Record its public interfaces, Python /
PyYAML dependency, native `trajectory-plan/v2` representation, authored geometry,
time/uncertainty and branch limits. Preserve dirty upstream work by installing
the committed source. [06-trajectory-compatibility.md](06-trajectory-compatibility.md)
defines the versioned read-only adapter. Original Hube tests and frozen hashes
remain acceptance requirements for the integration.

## M1 — Contracts as first-class nodes

Start bilateral. Expose Draft → Proposed → Accepted → Active → Fulfilled →
Verified, with rejection, cancellation, expiry and dispute branches. Keep
institutional authorisation inspectable between acceptance and activation.
`outcome_status=verified` may represent the verified lifecycle stage without
conflating it with reported fulfilment.

Deliver a small negotiated agreement whose terms, responsibilities and evidence
are inspectable. Critical acceptance: one actor-bound session cannot accept for
another actor. Test amendment after acceptance, stale versions, invalid lifecycle
steps, rejection and reported fulfilment without verification.

Existing scaffold: versioned agreement objects, approval receipts, graph nodes,
execution/evidence and a synthetic bilateral demo. Remaining work includes the
named lifecycle presentation, explicit cancellation semantics and a standalone
governance boundary. Do not label all of M1 complete from a successful demo alone.

Trajectory gate: contract creation, exact-version acceptance, authorisation,
execution, reported fulfilment and independent verification must survive native
package serialisation as distinct events and states. No generic package `Done`
status may replace the Commons lifecycle or imply verified reality.

## M2 — Governance and resource constraints

Extract scenario-independent contract rules into a governance module. Support
multilateral acceptance, atomic reservations, restricted declarative transition
conditions, scoped/revocable delegation and designated independent verifiers.

Acceptance: resource conservation under competing processes; out-of-scope,
expired and revoked delegation rejection; no delegation of personal acceptance
under the all-party policy; unsupported condition types rejected atomically.

Existing scaffold: all-party acceptance, named/threshold/category approval rules,
managed reservations and a real SQLite competing-process test. Missing: scoped
delegation, a condition registry, and extraction from the current Commons domain
dispatcher. No tokens, wallets, settlement or blockchain are required.

Governance trajectory gate: preserve authorisation decisions, actor identities,
reservation quantities and release, future delegation scope/revocation, and
verification evidence without lossy status normalisation. Branches run the same
rules against detached event prefixes. Adapter operations must leave both the
authoritative in-memory world and its SQLite history unchanged.

## M3 — Ecosystem

Import the existing Montréal ecosystem read-only with source IDs, source kinds,
capture times, epistemic status and missingness. Documented relations, participant
declarations and `W = O Nᵀ` potential complementarity stay separate layers. Preserve
the raw diagonal in analysis while excluding self-potential edges in gameplay.

Deliver discovery → explicit contact → proposed contract. An inferred match must
never itself create accepted collaboration or a verified fact. Keep local
empirical material separate from synthetic public demonstrations.

Existing scaffold: synthetic ecosystem projections and strict missingness-aware
matrix derivation. The current sprint adds a controlled empirical snapshot importer
and actor-to-contract navigation. Broader coverage and identity reconciliation
remain open. Source package: sibling `app_protocol_hack`, including
`protocol/ecosystem.py`, `protocol/multiplex_v2.py`, and its temporal capture/export
boundary. Inspect that package's contracts before choosing an import format.

The first exploration is terminal-based: actor/relationship/capacity/need inspection,
provenance-aware discovery and contact-to-contract proposal. The new TUI can
inspect and act in synthetic fixtures and the controlled Montréal Commons import.
Preserve missingness and uncertainty in both terminal output and exported
trajectory metadata. Do not turn inferred complementarity into documented cooperation.

## M4 — Gathering: first fully playable Commons mode

Upgrade Hube through an explicit, opt-in compatibility path. Preserve the original
six minimum conditions and ending. Use the shared governance implementation for:

Need → Offer → Contract → Verified support → Existing feasibility evaluation.

The original Hube fixture/client and saved logs must remain readable and retain
their semantics. Contract support must be part of the same authoritative world
transaction; synchronising two separately authoritative simulations is not an
acceptable bridge. Test withdrawal, partial beds, reservation conflicts and the
complete verifiable ending.

Existing scaffold: Hube and Commons share transaction/replay/storage machinery.
The separate synthetic gathering fixture is **not** yet a contract-backed Hube
upgrade. M4 remains open until that integration and its terminal traversal pass.

The first complete Commons mode must be terminal-playable through actor-bound
sessions over shared governance. Verify the entire unresolved-need → offer →
contract → independently verified support → feasible-ending trajectory. Normal
play binds one identity; switching is explicitly development hot-seat only.
Graphical visualisation is not an acceptance prerequisite.

## M5 — Scenarios

Begin with the Montréal-to-Geneva mentoring network and a limited action vocabulary.
Make objectives, strategies, coalitions, responsibilities and outcome criteria
declarative. Permit different trajectories and genuinely distinct outcomes,
including unmet objectives and partial progress.

Existing scaffold: a synthetic mentoring fixture with one prescribed objective.
It is not evidence of open-ended strategy/outcome support. Freeze alternative
strategies and their constraints before implementing outcome rules.

Use the trajectory package to inspect recorded histories and explicitly
hypothetical alternative strategies from a common state. Authoritative replay
and simulated alternatives remain distinct. A terminal trajectory inspector and
package YAML export suffice; native spline geometry is not required and no
physical quantities are fabricated. The current adapter supports isolated branch
simulation, but does not itself supply alternative mentoring strategies or complete M5.

## First vertical slice — the Gallica agreement

Motivating context: Andrés needs research data; Jean-Philippe may facilitate access.
This does not establish institutional authorisation or a finalised real contract.
Automated tests and public demonstrations use fictional actors and synthetic logs.

1. Ecosystem: discover a possible collaborator, preserving the source of that report.
2. Negotiate a versioned data-access contract: purpose, privacy, duration, conditions.
3. All parties accept the exact version using their own actor-bound sessions.
4. Record necessary institutional authorisation separately.
5. Gathering: assemble the permissions and reserve the required managed resource.
6. Record actual provision in the simulation and a fulfilment report with evidence.
7. An authorised independent verifier records the outcome; the scenario objective
   advances only according to the declared verified-outcome rule.

Signing or accepting is not completion. The slice passes only when proposal,
agreement, authorisation, execution, fulfilment and verification remain separately
visible in state and replay. It crosses the modes using one authoritative world.

## Shared component boundaries

| Component | Responsibility |
|---|---|
| World model | Actors, resources, capacities, needs, relationships and provenance |
| Action engine | Validate, authorise and apply atomic transitions |
| Governance engine | Declarative contracts, permissions, acceptance, reservations |
| Scenario engine | Objectives, constraints, conditions and success criteria |
| Event store | Ordered append-only action/evidence history and reconstruction |
| Game modes | Ecosystem, Gathering and Scenarios workflows over the same world |
| Presentation | Terminal, graph, timeline and actor-bound multiplayer interface |

The engine decides whether a transition is valid. Decision rights belong to the
actors under the explicit governance rules they have accepted.

## Trajectory and terminal checkpoint — minimal implemented boundary

The source-grounded compatibility assessment precedes adapter implementation.
The pinned package supplies document construction, normalization and YAML I/O.
Lossless Commons events, provenance and branch lineage live in its supported
`plan.commons_trajectory` namespace (`subtle-trajectory/v1`); native geometric
primitives remain empty. Commons performs every state reconstruction.

`play` provides actor-bound terminal navigation, state/contract inspection,
negotiation and evidence entry, available actions validated by the engine,
history, trajectory export, replay and isolated branch inspection. The
`trajectory-demo` command is explicitly synthetic development hot-seat play.
It is separate from interactive play and never runs implicitly.

Required compatibility checks: native document round-trip without loss; Commons
state equality after replay; lifecycle distinction; actor-bound submission;
branch isolation; event identity/order/provenance retention; and all original Hube
tests. See [07-terminal-architecture.md](07-terminal-architecture.md) and the
checkpoint validation report for actual results and remaining work.


## Complementarity to collective action — implemented checkpoint

O/N/W share one bounded arithmetic projection, with explicit partial observations.
The reported 4/5 discrepancy also exposed two distinct people sharing the first
name Nathalie: presentation collision labels now retain first-name privacy while
distinguishing their identities. Every cell of the pinned empirical prefix agrees
across arithmetic, heatmap and inspector.

Contact invitations now use existing authoritative relationship records and atomic
commits, with drafts, send, accept/decline, withdrawal and explicit-clock expiry.
Accepted contact creates an acknowledged connection, never a contract. Direct
contract proposals remain independent; versioned acceptance, institutional approval
and outcome verification gates are unchanged. Both paths are demonstrated in PTY
and ttyd with restart and native trajectory replay.

Implemented presentation: O/N/W explorer, compact contextual profiles/inspectors,
canonical inbox rows and filters, direct valid contract decisions, graph scope,
layer controls, visible rendering coverage and stable Back navigation.
**Experimental:** optional genuine 3D layout and yaw/pitch camera; no social or
physical meaning is assigned to layout geometry. Production identity, real delivery
and institutional/legal enforcement remain outside this milestone.

See [13-complementarity-to-collective-action.md](13-complementarity-to-collective-action.md)
for the source audit, API additions, migration boundary, file list and validation.
