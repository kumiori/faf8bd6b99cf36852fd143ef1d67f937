# State transitions

The public `ActionSubmission` contains an idempotency `action_id`, `actor_id`,
`scope_id`, `target_id`, `expected_revision`, `action_type` and JSON-compatible
`payload`. The host supplies the independently selected `SimulationBinding`.
The target agrees with the corresponding payload identifier. Use `None` for
actions without a target identifier, such as advancing the clock.

`expected_revision` is the committed world revision. Agreement actions also
carry `agreement_id` and the exact integer `version` of their terms. The store
checks the world revision within the write transaction. The engine validates
actor status, the active terms, transition preconditions and decision rights.
An exact retry returns the original action and commit even after other
actions advance the world. A changed command with the same ID conflicts.

| Actions | Authoritative change |
| --- | --- |
| `send_contact`, `draft_contact`, `publish_contact`, `respond_contact`, `withdraw_contact` | Manage invitations and record an acknowledged connection on acceptance |
| `invite`, `respond_invitation` | Record gathering attendance intent |
| `draft`, `propose`, `publish_proposal`, `amend` | Create or revise exact terms. Amendments preserve superseded receipts and start fresh |
| `accept`, `authorize`, `activate` | Record exact-version party receipts and governance approval. Activation creates commitments and holds resources atomically |
| `initiate`, `fulfill`, `verify` | Record execution, reported delivery and independent verification. Verification releases held resources and updates objectives |
| `reject`, `withdraw`, `suspend`, `resume`, `dispute`, `terminate` | Apply lifecycle transitions according to authority and current status |
| `declare`, `reconcile_resource`, `advance_time` | Record declarations, external resource evidence or explicit clock and expiry changes |

An accepted event contains the command, acting actor, ordered mutations and
commit metadata. Mutations contain detached before/after records. Commit
metadata carries the previous/resulting revision and state digests, together
with the recorded authorisation. Rejected actions leave the history intact.
