# Playability and reconstruction consolidation

The working tree based on `ffaf0ab` implements the six consolidation phases.
The three principal worlds remain Ecosystem, Gathering and Scenarios.
**Exercises** is a separate Workshop entry. The shared Montréal reconstruction
and the three fictional practice tutorials have explicit, separate destinations.

## Defects and repairs

| Finding | Cause | Implemented repair |
| --- | --- | --- |
| Navigation accumulated visible delays | Every display frame loaded and replayed SQLite history, deep-copied state and rebuilt the full inferred network | A cheap revision read gates frame invalidation. Participant projections and portraits are cached. The optional standalone TUI also caches its world snapshot by revision. |
| Large histories made local submission slower than the target | Repeated complete prefix replay during transactional reads and subsequent refresh | SQLite reads compare the complete stored event prefix before reusing a validated detached snapshot, then validate new events. Memory reads return detached snapshots. A changed stored prefix triggers full validation. |
| Repeated arrows could queue many slow frames | Each queued key required another expensive frame | Fast navigation frames and bounded coalescing of identical queued direction keys. The first different command is preserved. |
| Confirmation accepted unclear input | Free-text yes/no parsing restarted the prompt and left its state uncertain | A selected Confirm/Cancel dialog supports arrows, Enter, y/n and Escape. Other input keeps the dialog intact. A queued trailing Enter is consumed. |
| A successful recollection lacked a persistent consequence screen | A short notice disappeared at the next refresh | A dedicated result screen shows the actors, outcome and before/after claim count, with View Connection and Continue. Other action notices persist through idle refresh. |
| Reconstruction mixed people with institutions | The roster included organisation actors | Reconstruction discovery uses people only. Organisations remain separate actors in Ecosystem. |
| Filters required prior vocabulary knowledge | Each selected field requested free text | Available facet values show counts. OR applies inside a field and AND across fields. Matching counts update in the panel. Search, selection anchors and directory scroll are retained. |
| Potential collaborators were hard to find | Discovery only searched independent attributes | A Connections facet offers people whose recorded offers intersect the current player's needs. |
| Observation types were difficult to compare | One small neighbourhood combined several types without a graph-level selector | Neighbourhood, collective and full graph views share the renderer. Independently enabled groups distinguish Montréal reconstruction, existing relationships, invitations/accepted contacts, contracts and potential complementarities. Provenance inspection exposes source, claim and event references. |
| An identity merge allowed a second equivalent recollection | Duplicate checks compared original IDs while the display resolved aliases | Claim ownership, disputes and duplicate checks resolve canonical identities. Existing declarations retain their original IDs. A merge cannot create corroboration from previously non-reciprocal accounts. |
| Identity corrections had no audited control surface | Source records supplied identity metadata without curator commands | Engine-enforced curator commands provide corrections, hide/archive/restore, merge preview and reversal. The header indicator follows the actor's actual permission. |
| An inspector could lose its node after a concurrent correction | A hidden or merged actor disappeared from the current discovery projection | The inspector explains the discovery update, offers the canonical profile when available and retains access to history. Curator actions appear in affected profiles' histories. |
| The introduction obscured its primary action | Static narrative relied on a footer instruction | A deterministic, short, interruptible opening ends with a selected Begin Reconstruction control. Reduced motion and automated playthroughs show the static version. |

## Interaction and exercise configuration

The opening is rendered by the ordinary event loop, with an 80 ms polling
interval and a configurable 2.5 second default duration. Any key skips it.
`COMMONS_REDUCED_MOTION=1` requests the static version. Ordinary navigation has
no animation. Montréal wording is explicitly marked
`COPY_REVIEW_REQUIRED: Natalie` and the opening displays its pending review.

The three tutorials are ordinary JSON configurations in
[the tutorial catalogue](../game-gamer/src/game_gamer/exercises/tutorials.json).
The runtime binds each step to an explicitly confirmed practice role and submits
existing invitation, declaration and agreement commands through the public
Collective API. It includes expected permission failures. Each practice session
has its own in-memory world and scope. Restarting a tutorial replaces that
practice session. The main player binding and collective history are preserved.

Reconstruction keeps its selected person across directory, graph, filter and
inbox navigation. In that exercise, `c` opens Connect and `C` opens Contracts.
`f` opens facets, `v` switches neighbourhood/collective view, `G` opens the full
graph and `d` inspects connection provenance. Curators additionally have `u`.
A hidden or archived identity remains available to authorised curation and
historical inspection.

## Schema and authority

SQLite still stores the ordered event history. Existing worlds require no
database migration. A `configuration.curation` record is created on the first
accepted curator operation and identifies `game-gamer/curation/v1`. It holds
profile overlays, visibility decisions, canonical aliases and merge decisions
with their audit references.

The new curator commands are `correct_profile`, `set_profile_visibility`,
`merge_profiles` and `reverse_profile_merge`. They require the acting actor's
engine role `curator`. Profile correction permits label, motivation and a
professional-role display field. It cannot grant engine roles. Roles are
provisioned by the trusted host, as in a world definition. This task assigned no
curator to the saved Montréal participants.

Merge submission requires a matching preview digest, expected world revision,
an explicit identity-check attestation and a source reference. Historical
records retain their original endpoints. Projections resolve aliases and
suppress resulting self-links, preserving those observations for audit.
Reversal records another event and restores the mapping. Pending invitations,
open agreements and resource ownership require resolution before merging.
Dependent merges must be reversed in reverse order.

The reconstruction commands and source import remain as documented in
[Extension 01](16-network-reconstruction.md). Existing histories and frozen
trajectories are readable. Histories containing the new domain commands require
the updated implementation to re-execute them. The event and mutation formats
retain their existing representations.

The existing local simulation identity boundary applies. Curator permission is
enforced during command validation even when an ordinary player submits the
command directly.

## Performance evidence

Measurements used Python 3.11.12 on macOS arm64, the same local Montréal save
with 71 actors and 12 events, and a 144×34 viewport. The final ordinary directory
contained 41 source participants. Before consolidation the reconstruction
directory also included organisations. The comparison therefore includes the
required directory restriction as well as the cache repairs.

Navigation measurements include a revision check, cursor move and two screen
builds after warming the initial projection. Before consolidation, 20 samples
gave a 231.241 ms median and 340.677 ms p95. Thirty final samples gave a
4.341 ms median and 4.823 ms p95. Profiling separately attributed most time to
deep-copying, full history replay and network projection construction.

| Final operation | Samples | Median | p95 | Target |
| --- | ---: | ---: | ---: | ---: |
| Arrow frame | 30 | 4.341 ms | 4.823 ms | 50 ms |
| Profile screen | 30 | 1.922 ms | 2.073 ms | 100 ms |
| Facet value counts | 30 | 0.122 ms | 0.132 ms | 100 ms |
| Neighbourhood screen | 30 | 1.983 ms | 2.094 ms | 150 ms |
| Collective graph screen | 30 | 3.578 ms | 6.294 ms | 500 ms |
| SQLite submission and refreshed state | 5 | 161.526 ms | 174.859 ms | 300 ms |

Submission measurements used disposable SQLite copies of the source history.
The earlier uncached measurement of that operation was 396.926 ms median.
The frame measurements exclude terminal emulator paint time and network latency.
The real PTY playthrough provides interaction evidence separately.

[Before navigation measurements](validation/playability/navigation-before.json)
and [final operation measurements](validation/playability/measurements-after.json)
contain aggregate timings only. Reproduce them with
`tools/benchmark_playability.py --db PATH` and
`tools/measure_playability.py --db PATH`.

## Tests and recorded interaction

The complete Commons suite passed 185 tests. The standalone Game-Gamer suite
passed 33 tests. The current sibling Hube suite passed 67 tests with one module
skipped because `cv2` is unavailable. Frozen Hube acceptance artifacts and the
Commons extraction baseline also passed. The Hube subprocess check now asserts
successful test completion instead of an obsolete literal test count.

New regression coverage includes invalid confirmation input, Escape and double
Enter, bounded key bursts, counted facet composition, metadata missingness,
isolated tutorials with exact retries, direct curator permission denials,
canonical author/target duplicate checks, claim ownership after merging,
self-link suppression, reversal, detached store reads, cached-prefix corruption
detection, and concurrent changes while an inspector is open.

The real PTY checks passed for reconstruction, contract negotiation, independent
invitation/direct-agreement paths and the full consolidation workflow.
The reconstruction check restarts the application as a new process and recovers
both directed claims and their corroborated projection.

All captured people, identity duplicates, claims and curator permissions are
fictional fixtures. Source IDs visible in curator captures belong to that fixture.
The recorded sequence demonstrates the menu, facets, cancellation, claim result,
graph, provenance, merge/reversal and all tutorials.

- [Timed terminal recording](validation/playability/session.cast)
- [Worlds and Workshop menu](validation/playability/01-worlds-and-workshop.txt)
- [Three regions and the curator indicator](validation/playability/04-three-regions-and-curator.txt)
- [Counted facet choices](validation/playability/05-counted-facets.txt)
- [Action result](validation/playability/07-action-result.txt)
- [Merge preview](validation/playability/12-merge-preview.txt)
- [Reconstruction after restarting the application](validation/playability/15-after-application-restart.txt)

The recording uses the asciinema v2 format at 144×34. The source playthrough
starts at 100×32 and then expands. The viewport text captures are directly
decoded terminal output. Fixture databases are excluded from these artifacts.

## Decisions for human review

- Natalie must review the Montréal exercise wording.
- The host needs named curator assignments and an agreed source for identity
  verification. Matching names alone do not establish duplicate identity.
- Professional role categories need a supplied taxonomy or verified metadata.
  Missing values remain explicit in the current facets.
- The group must decide whether future merges may migrate outstanding
  contractual or resource responsibilities. The current preview blocks those cases.
- Tutorial wording and completion explanations need an onboarding review with
  an unfamiliar participant. Scripted completion has passed, and a human
  first-use observation remains outstanding.

The earlier [release-discipline assessment](17-release-discipline.md) records a
prior working-tree snapshot. The canonical-duplicate and stale test-helper
findings described there are covered by the repairs and regression evidence
above. This report does not record a package publication or an observed novice
acceptance session.
