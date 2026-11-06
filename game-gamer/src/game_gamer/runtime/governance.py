"""Inspect the approvals required by a versioned agreement."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyDecision:
    status: str
    reasons: tuple[str, ...] = ()


def evaluate_authorisation(world, version):
    policy = world['governance'][version['policy_id']]
    approved = set(version['authorizations']) & set(policy['eligible_actors'])
    categories = {world['actors'][actor]['category'] for actor in approved}
    reasons = []
    if len(approved) < policy['threshold']:
        reasons.append('approval_threshold')
    if not set(policy['required_actors']) <= approved:
        reasons.append('required_approvers')
    if not set(policy['required_categories']) <= categories:
        reasons.append('required_categories')
    return PolicyDecision('requires_authorisation', tuple(reasons)) if reasons else PolicyDecision('allowed')
