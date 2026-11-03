# Commons development milestones

Roadmap adopted on 3 November 2026. M0 is the current acceptance gate. No new
gameplay is introduced by this roadmap checkpoint.

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

## M0 — Audit and freeze Hube

Objective: establish and preserve the actual functioning baseline. Deliverables:
`04-M0-freeze.md`, source inventory, checkpoint refs, frozen fixture hashes and
the existing 58 regression tests. Preserve interactive play, deterministic
simulation, provider consent, independent verification, quantity allocation,
six-condition feasibility, history, persistence, replay and locale equivalence.

No new gameplay. A test failure or unexplained canonical-state drift blocks M1.

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

## M3 — Ecosystem

Import the existing Montréal ecosystem read-only with source IDs, source kinds,
capture times, epistemic status and missingness. Documented relations, participant
declarations and `W = O Nᵀ` potential complementarity stay separate layers. Preserve
the raw diagonal in analysis while excluding self-potential edges in gameplay.

Deliver discovery → explicit contact → proposed contract. An inferred match must
never itself create accepted collaboration or a verified fact. Keep local
empirical material separate from synthetic public demonstrations.

Existing scaffold: synthetic ecosystem projections and strict missingness-aware
matrix derivation. Actual empirical import and match-to-contract navigation are
not implemented. Candidate source package: sibling `app_protocol_hack`, including
`protocol/ecosystem.py`, `protocol/multiplex_v2.py`, and its temporal capture/export
boundary. Inspect that package's contracts before choosing an import format.

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

## M5 — Scenarios

Begin with the Montréal-to-Geneva mentoring network and a limited action vocabulary.
Make objectives, strategies, coalitions, responsibilities and outcome criteria
declarative. Permit different trajectories and genuinely distinct outcomes,
including unmet objectives and partial progress.

Existing scaffold: a synthetic mentoring fixture with one prescribed objective.
It is not evidence of open-ended strategy/outcome support. Freeze alternative
strategies and their constraints before implementing outcome rules.

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
