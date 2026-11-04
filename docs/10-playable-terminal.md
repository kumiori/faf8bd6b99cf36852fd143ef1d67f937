# SADDLE PATHWAYS — playable terminal, complete Montréal scope and command repair

4 November 2026. All ordinary play is **simulation only**. This sprint repairs
presentation, navigation and source coverage over the existing authoritative
engine. Contracts, acceptance rules, resource constraints and verification remain
the same institutional operations.

## A. Architecture assessment

| Component | Packaging and authority |
|---|---|
| Commons | The `commons-game` distribution includes `commons_engine` and `commons_game`; the core has no runtime dependencies. `saddle-pathways` launches ordinary play without a subcommand. Existing CLI/schema aliases remain compatible. |
| Shared engine | `commons_engine.WorldEngine` owns atomic mutations, history, reconstruction and SQLite storage. `CommonsGame` supplies Commons rules. The player UI reads projections and submits normal actor-bound commands. |
| Hube | The separate `hube-game` distribution depends on `commons-game>=0.1.0` and imports the shared engine. Commons does not depend on Hube. The sibling checkout supplies optional compatibility tests and the frozen regression world. |
| Trajectory | Optional `trajectory-engine 0.2.0`, pinned to `757c2baeb17e9864eeff0900b5ad9ea3cec23d9d`. The adapter is read-only, checks source hashes, and retains `trajectory-plan/v2` plus `subtle-trajectory/v1`. Core play works without it. |
| Notion | Optional capture input, using the sibling's supported read-only transport and existing secret configuration. No identity or game-state authority is delegated to Notion. Offline snapshot import has no SDK dependency. |

`play.py` is the ordinary player surface. `tui.py` retains the entered laboratory
fixtures behind explicit developer entry points. Both use the same engine,
projections and persistence. A screen-frame cache avoids repeated SQLite replay
for every rendered row; it is refreshed at screen/command boundaries and after
submissions. Every write still reloads and validates under the existing store lock.

Default private data lives under `~/.local/share/saddle-pathways/`; override with
`SADDLE_DATA_DIR`. The prior private sample was copied, verified and migrated there.
Its five-event world and existing contract were preserved before appending the
full import. Changing a simulated actor does not create or reset a world.
Choosing another world is explicit and uses its own saved simulation.

An actual wheel was installed in an isolated environment with neither `game`
(Hube) nor `trajectory_engine`. Core replay and the installed player executable
launched successfully. Hube is therefore not a prerequisite for Commons play.

## B. Notion coverage report

The approved source mapping is versioned in `config/montreal-scope.json`.
Capture version: `saddle-montreal-capture/v1`; Notion client API version:
`2025-09-03`. Mapping/taxonomy digest:
`b35a99805379fd4c38c8d5e726b63d1bf5b2b8b80639c3b39eb4fefaf40237f1`.
This is a mapping version, not a claim of an immutable Notion database revision.
Individual source creation/edit times remain separate from capture time.

The complete read-only capture started at **15:46:55 Europe/Paris on
4 November 2026**. Each page retains its source timestamps. Private evidence is
under `~/.local/share/saddle-pathways/captures/2026-11-04-full/`.

| Source | Supported mapping |
|---|---|
| `protohack_Players`, data source `d3932ca7-289a-40f1-b30e-1ed839c40f8b` | Source person pages; only name, institution mention, source status and stable reconciliation identifiers are read for the mapping. Reconciliation identifiers do not enter ordinary screens. |
| `protohack_Responses`, data source `9eee785d-3b00-4dba-a6ce-2b2279dd02ac` | Scoped submitted inventories and their explicit `player` relation. Only authored structured knowledge-offer/need codes are projected into the world. |
| `institution` | Free-text source-local organisation mention and reported affiliation. The approved schema provides no canonical organisation relation. No unsupported name join is performed. |
| Other connected tables | The inspected schemas link sessions, questions, events and decisions. These do not establish additional person identities, institutional authority, approvals or accepted collaboration. The sibling's local documentary relation matrix has no supported crosswalk to these person IDs and is not silently merged. |

All source query pages and truncated selected properties are paginated. The
independent connector check also enumerated the 41 person rows in pages of
20, 20 and 1. The full SDK capture used query/property pagination over both sources.
The canonical current inventory scope is `montreal_communs_data_ai_short_2026`
in event `montreal_communs_2026`, with `probe_submission` and `state=submitted`.

| Coverage item | Count / interpretation |
|---|---|
| Source records inspected | **99**: 41 person records and 58 response records |
| Response records in current questionnaire/event scope | **49** |
| Submitted current inventories | **45** |
| Repeated submitted inventories | **3**; reconciled by explicit source identity/revision, not names |
| Submitted inventory without resolvable person | **1**; retained in the private reconciliation report, no actor invented |
| Eligible named people | **41** |
| Imported people / selector people | **41 / 41**; no eligible named person excluded |
| Source-local organisation mentions / affiliations | **28 / 28** |
| Canonical organisation records imported | **0**; no canonical relation in the approved source schema |
| Distinct organisation labels | **26**, with **2** unresolved same-label groups; mentions remain distinct |
| Declared capacities / needs | **211 / 290** |
| Profiles with missing affiliation | **13**; shown as unknown |
| Latest skipped need field | **1**; not treated as a negative declaration |
| Duplicate person-name groups / duplicate source page IDs | **0 / 0** in this capture; duplicate-name fixtures are tested |

The remaining four in-scope records are unsubmitted legacy trajectories. Of the
nine records outside the current inventory scope, eight belong to the older
full Montréal questionnaire and one to the initial-conditions questionnaire;
all are legacy trajectories without a submitted inventory state. They do not
create additional people or overwrite current declarations. The complete
accessible person catalogue is already represented by the 41 current people.
The extra submitted identity without a resolvable source person is the outstanding
coverage discrepancy; it is not concealed as a successful import.

The world also has **two explicitly synthetic support roles**, a playground
objective and its simulation policy. These are supplements, not source participants
or real authority. The interface displays source versus world coverage separately.

Capture keeps names, source-local affiliation assertions and permitted authored
knowledge choices. It drops credentials, contact information, raw envelopes,
unrelated questionnaire fields and free-text Other answers before writing output.
Declared knowledge is not resource availability, a promise or a commitment.
Potential matches remain inferred. There is **no Notion write-back**.
Snapshots, detailed reconciliation candidates and empirical transcripts remain
outside the public repository; public fixtures use fictional identities.

## C. Terminal design system and opening flow

`presentation.OBJECTS` is the shared immutable dictionary. It supplies labels,
symbols, ASCII alternatives and colours for lists, actor selection, inspectors,
relationship neighbourhoods, contract registries and trajectory summaries.
`presentation.dictionary()` exposes the same serialisable vocabulary for future
renderers. Status is separate from object type and always has a text label.

People appear by first name throughout player-facing labels, search and contract
party lists. Unstructured names use the first whitespace-separated token,
retaining accents and hyphens. Organisation labels remain complete. People with
the same first name remain separate numbered choices; source names, actor IDs,
provenance, saved history and exports remain unchanged.

| Object | Symbol | Colour |
|---|---|---|
| Person | ● | Cyan `#71d7e5` |
| Organisation | ◆ | Lavender `#c4a7e7` |
| Resource | ■ | Amber `#e8b65e` |
| Contract | ⬡ | Burnt orange `#d88356` |
| Objective | ◎ | Ivory `#eee8d5` |
| Governance policy | ◇ | Mauve `#bc91af` |
| Capacity | ▲ | Sage `#a3bd95` |
| Need | ▽ | Steel blue `#8caac4` |

Colour is optional. `NO_COLOR`, non-interactive streams, unsupported encodings,
`TERM=dumb` and `--plain` have readable fallbacks. Source spelling is preserved
in authoritative data; unsupported output encodings use a display-only fallback.
Pages and inspectors wrap to the available width and show a limited set of entries.

The opening sequence is splash → Commons/world selection when needed →
who will you play? → alphabetical person catalogue → shared world explorer.
The default catalogue contains every eligible imported person, with name search,
organisation filtering, preview and numbered/cursor selection. `p` changes the
simulated person during play. A separately labelled development-role choice can
exercise synthetic or organisational roles; organisational simulation requires an
explicit confirmation. It creates no genuine representation authority.

The player never needs a mock manifest. Explicit role selection issues an
unauthenticated `development_simulation` session. Every action records simulation
context and remains actor-bound. Imported existence and affiliation do not issue
that session or confer real authority. Production authentication is absent from
the ordinary menus. Previous mock manifests remain developer test utilities.

Each screen orders title, world/player/state context, primary content, actions and
help. Ordinary play omits source IDs, content digests and JSON. `metadata` shows
selected provenance on demand. Historical views carry an explicit historical-state
banner and cannot submit into the past. Current state resumes after returning.

The existing exact-domain complementarity generator is now also projected as an
inferred graph layer, so a discovered peer can be selected by number. It does not
write a relationship or become a contract. Contract aliases `K-001`, `K-002`, etc.
follow authoritative creation order and survive replay; underlying IDs are unchanged.

### Toolkit decision

Investigated [Textual OptionList](https://textual.textualize.io/widgets/option_list/)
and its [keyboard/focus model](https://textual.textualize.io/guide/input/), and
[Rich Console](https://rich.readthedocs.io/en/stable/console.html), including its
colour and non-terminal handling. Textual is a suitable future full-screen client;
Rich is suitable for richer output. This sprint adds **no new TUI dependency**:
the small presentation boundary and POSIX keyboard adapter preserve deterministic
line-script playtests, the standard-library core and standalone/offline play.
Other platforms can use numbered and line-command fallback navigation.
Any future renderer can consume the same dictionary and projections without
changing domain state. This is a presentation decision, not a new engine design.

## D. Interaction repair report

| Reported command | Original classification | Repair and verified behaviour |
|---|---|---|
| `invite` | Working engine operation, accessible only through Gathering's `i`; correctly unavailable without a gathering objective | Registered by name across player screens. The gathering fixture creates a pending invitation; other worlds explain the missing objective. `i` consistently means inbox in ordinary play. |
| `respond` | Existing invitation handler reachable only through Gathering's `r`; empty pending list had poor feedback | Registered response command chooses pending invitations or the contract inbox. Empty state explains that no response is required. Invitation acceptance and contract acceptance remain different actions. |
| `open latest contract` | Defective parsing: literal `latest contract` became an unknown node ID | Deterministically resolves the newest authoritative contract, including after restart; `K-001`, exact IDs and unique names remain supported. |
| `contract history` / bare `history` | Missing alias and missing-argument navigation; empty ID produced no useful history | Registered alias and transition selector. Each chosen event opens its historical projection with a visible state banner. |
| `available actions` | Existing action checks, but text alias absent and graph dispatch screen-specific | Registry resolves `a`, `actions`, `act` and `available actions`. A selector describes the affected people and effect before confirmation; empty permission/state results are explained. |
| `act ID` | Implemented but opaque and poorly explained | `a` acts on the selected object; missing arguments use selection, and readable contract aliases are supported. |
| `list` | Implemented but undiscoverable | Registry help explains the current-world explorer and clearing filters. |
| `history ID` | Implemented but developer-oriented | `h` uses the selected object; names/numbers and event selectors avoid memorising IDs. |
| `past SEQUENCE ID` | Implemented but insufficiently explained | `past` without arguments opens history selection; explicit state/reference syntax remains a documented power-user path. |

The initial red-capable reproductions returned `unknown_node` for latest-contract
opening, no history for a bare history request, and an unrecognised-action message
for available actions. Their exact call paths now pass regression tests.

`commands.COMMANDS` declares names, aliases, argument grammar, applicable screens,
description, availability method, handler and help. Ordinary menus/help derive from
it. Tests invoke every advertised command with a valid fixture or verify an
explicit contextual explanation. Unsupported, unauthorised and empty-state
conditions are not all labelled parser failures.

## E. Playable demonstration

```sh
saddle-pathways
```

Choose a person; search or inspect another person; select a potential peer from
their numbered neighbourhood; press `a` to propose. The form explains who is
affected and what a successful proposal changes. The result shows a contract,
lifecycle and separate outcome, with inspect/graph/return choices. Change perspective
with `p`, open `i`, inspect the proposal, and use `a` to accept or negotiate.
Use `h` for transitions, `t` for the recorded trajectory, and `replay` to check
reconstruction. Changing perspective never resets shared state.

`tools/playtest_playable.py` executes this ordinary UI using **names and numbers
only**, without mock manifests, source IDs or API commands. The full empirical
demonstration used all 41 imported people, discovered an inferred peer, proposed,
switched participants, recorded both exact-version acceptances, inspected history,
restarted and round-tripped the native trajectory. It ended **accepted / unverified**.
No fulfilment or independent outcome verification was fabricated.

Private entered input, transcript, restart transcript, world and trajectory are at
`~/.local/share/saddle-pathways/playtests/2026-11-04-player-final/`.
The default world preserves the previous checkpoint; this reproducible demonstration
uses its own explicitly created simulation database. The same tool without
`--snapshot` produces public fictional evidence in a new output directory.

## F. Regression report and limits

* **108 tests passed** in the complete suite, including HTTP tests with loopback
  access and the compatibility check running all **58 original Hube tests**.
* Complete source and property pagination, malformed/repeated cursors, source
  reconciliation, all-person selection, duplicate names/organisation mentions,
  searches, fallbacks, registry dispatch, state restrictions, invitations,
  latest-contract opening, histories, inboxes, simulated switching, persistence,
  graph reconstruction and trajectories are covered.
* Actual isolated wheel installation passed without Hube, trajectory-engine or
  other neighbouring projects. Developer checks requiring a missing sibling skip
  explicitly; they are not runtime dependencies.
* Public fictional and full empirical player-facing demonstrations passed
  independently. A real pseudo-terminal check exercised arrow selection, Enter,
  Esc/back and quit, separately from scripted line-input tests.
* Raw terminal-control input is implemented for POSIX terminals. Other environments
  retain numbered/search/typed-command fallback. No external novice usability
  study or Windows native-keyboard test was performed.

The unresolved submitted identity and canonical organisation reconciliation remain
explicit data limits. Production authentication, verified identity claims,
institutional delegation, complete contract-backed Hube gameplay and broader
M1–M5 gates remain outside this interaction sprint. None is presented as an inert
ordinary-play option or as completed real-world collective action.
