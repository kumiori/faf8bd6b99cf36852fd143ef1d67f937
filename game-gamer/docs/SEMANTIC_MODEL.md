# Semantic model

A collective owns one append-only event history. A snapshot derives from its
genesis and a prefix of ordered mutations. An action belongs to a scope and
actor. Accepted actions have an immutable history entry. The world includes
actors, capacities, needs, relationships, resources, agreements, commitments,
reservations, governance policies, evidence, objectives and configuration.

## World definition

`game-gamer/world/v1` is a JSON object. Required fields are `schema`, `scope_id`,
positive integer `revision`, `execution_mode` with value `simulation`, `title`
and offset-aware ISO 8601 `world_time`. Stable IDs are unique across the seed
tables. Optional tables default to empty arrays.

| Seed table | Record |
| --- | --- |
| `actors` | `id`, `label` and optional `kind` (person or organisation), `category`, `roles`, `status` and `provenance` |
| `resources` | `id`, `label`, `owner_id`, integer `quantity`, `unit` and optional `control`, `status`, `evidence_ids` and `provenance` |
| `governance` | `id`, `label`, `eligible_actors`, `threshold` and optional `required_actors`, `required_categories` and `status` |
| `capacities`, `needs` | `id`, `actor_id`, `domain`, `unit` (nullable), `status` and `provenance.kind` |
| `relationships` | `id`, `source_id`, `target_id`, `kind`, `status` and `provenance.kind` |
| `objectives` | `id`, `mode`, open `status`, empty `support_ids`, `provenance.kind` and `success` with integer `minimum_parties`, `minimum_attendees` and `verified_agreements` |

See the [rehearsal fixture](../examples/minimal_collective/world.json) for a
complete definition. Runtime records such as contact invitations, acceptance
receipts, held reservations and verification evidence originate in actions.

## Projections and provenance

`project("world")` returns detached tables keyed by stable ID.
`project("network")` returns nodes and typed edges. Table names such as
`agreements` return record lists. `project("timeline")` returns the ordered
event prefix. `project()` combines version, world, possibilities and network
from one prefix. Pass `at` to inspect a historical revision. Use
`inbox(binding=..., at=...)` for actor-specific pending decisions.

An exact-domain complementarity carries its source record IDs, generator and
inferred status. Only a recipient's accepted contact action creates an
acknowledged connection. Party acceptance carries the actor, agreement version,
content digest and recording action. Independent verification links evidence to
the executed agreement version. The `EpistemicStatus` enum and
`epistemic_status` helper distinguish recorded facts, declarations, inference,
proposals, acknowledged relationships, verified outcomes and unknown status.
The engine preserves the original record and provenance alongside any projection.
