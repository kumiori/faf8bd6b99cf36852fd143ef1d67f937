# Governance

The host supplies a trusted simulation binding after selecting a role. The
engine compares actor and scope against that binding. Organisations require
explicit organisation simulation authority. A binding grants the ability to
act as that simulated actor, subject to the world's decision rules.

`Collective.evaluate` provides an inspectable decision against one committed
prefix. It returns `allowed`, `rejected` or `requires_authorisation`, with
machine-readable reasons. Every submission rechecks its rules under the store's
write authority. An earlier evaluation carries no approval.

Every party accepts the same terms independently. Institutional approval then
evaluates eligible actors, a threshold, any required actors and categories.
`evaluate_authorisation(world, version)` exposes the same approval calculation
used by activation. The version includes its `policy_id` and recorded approvals.
The activation rule also checks attendance for gathering objectives and available
resources. Verification requires a designated actor outside the agreement parties.

A simulation binding and resulting event carry in-world authority. The execution
policy admits simulation as its only mode. Identity verification, delivery and
real-world consent would require a separate host and a new supported policy.
