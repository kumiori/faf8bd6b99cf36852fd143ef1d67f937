"""Typed Commons domain records. Commitments are never transaction commits."""
from dataclasses import dataclass, field
from typing import Any

TABLES = ('actors', 'relationships', 'capacities', 'needs', 'resources',
          'agreements', 'commitments', 'reservations', 'governance', 'evidence',
          'objectives', 'configuration', 'actions')
ENTITY_TABLES = dict(zip(('actor', 'relationship', 'capacity', 'need', 'resource',
                         'agreement', 'commitment', 'reservation', 'policy', 'evidence',
                         'objective', 'configuration', 'action'), TABLES))


@dataclass(kw_only=True)
class Actor:
    id: str
    label: str
    kind: str = 'person'
    roles: list[str] = field(default_factory=list)
    category: str = 'participant'
    status: str = 'active'
    provenance: dict = field(default_factory=lambda: {'kind': 'fictional_fixture'})


@dataclass(kw_only=True)
class Approval:
    actor_id: str
    agreement_id: str
    version: int
    content_digest: str
    action_id: str
    recorded_at: str
    method: str = 'local_simulated_identity'


@dataclass(kw_only=True)
class AgreementVersion:
    number: int
    terms: dict[str, Any]
    resources: list[dict]
    valid_until: str
    policy_id: str
    verification: dict
    proposed_by: str
    created_at: str
    content_digest: str
    status: str = 'current'
    acceptances: dict[str, dict] = field(default_factory=dict)
    authorizations: dict[str, dict] = field(default_factory=dict)


@dataclass(kw_only=True)
class Agreement:
    id: str
    label: str
    parties: list[str]
    objective_id: str
    versions: list[dict]
    created_by: str
    created_at: str
    current_version: int = 1
    status: str = 'proposed'
    outcome_status: str = 'unverified'
    initiated_actions: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=lambda: {'kind': 'synthetic_gameplay'})


@dataclass(kw_only=True)
class Commitment:
    id: str
    agreement_id: str
    agreement_version: int
    actor_id: str
    responsibility: str
    created_by: str
    created_at: str
    status: str = 'active'
    evidence_ids: list[str] = field(default_factory=list)
    execution_action_id: str | None = None


@dataclass(kw_only=True)
class Resource:
    id: str
    label: str
    owner_id: str
    quantity: int
    unit: str
    control: str = 'internal'
    status: str = 'available'
    evidence_ids: list[str] = field(default_factory=list)
    provenance: dict = field(default_factory=lambda: {'kind': 'fictional_fixture'})


@dataclass(kw_only=True)
class GovernancePolicy:
    id: str
    label: str
    eligible_actors: list[str]
    threshold: int
    required_actors: list[str] = field(default_factory=list)
    required_categories: list[str] = field(default_factory=list)
    status: str = 'active'


class DomainError(ValueError):
    """Expected, reviewable rule failure; storage/programming failures propagate."""


def require(condition, code):
    if not condition:
        raise DomainError(code)
