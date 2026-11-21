"""Public action envelope and trusted simulation binding."""
from copy import deepcopy
from dataclasses import dataclass
import json

from ..model import DomainError, require
from .engine import FIELDS, text

_TARGET_FIELDS = ('mission_id', 'agreement_id', 'invitation_id', 'resource_id', 'id', 'objective_id', 'claim_id', 'target_id', 'merge_id', 'request_id')


@dataclass(frozen=True, kw_only=True)
class ActionSubmission:
    action_id: str
    actor_id: str
    scope_id: str
    target_id: str | None
    expected_revision: int
    action_type: str
    payload: dict

    def command(self):
        text(self.action_id, 'key_required')
        text(self.actor_id, 'actor_required')
        require(type(self.expected_revision) is int and self.expected_revision >= 1, 'invalid_expected_revision')
        require(isinstance(self.action_type, str) and self.action_type in FIELDS, 'unknown_command')
        require(isinstance(self.payload, dict) and not
                self.payload.keys() & {'key', 'actor', 'kind', 'session'}, 'invalid_action_payload')
        try:
            serialised = json.dumps(self.payload, sort_keys=True, allow_nan=False)
            require(json.loads(serialised) == self.payload, 'invalid_action_payload')
        except (TypeError, ValueError) as error:
            raise DomainError('invalid_action_payload') from error
        target = next((self.payload[key] for key in _TARGET_FIELDS if key in self.payload), None)
        require(target == self.target_id, 'target_mismatch')
        return {**deepcopy(self.payload), 'key': self.action_id, 'actor': self.actor_id, 'kind': self.action_type}


@dataclass(frozen=True, kw_only=True)
class SimulationBinding:
    """Set by the calling host after selecting an explicit simulated role."""
    scope_id: str
    actor_id: str
    authority: str = 'personal'

    def bind(self, action, scope, *, counterfactual=False):
        require(self.scope_id == action.scope_id == scope, 'scope_mismatch')
        require(self.actor_id == action.actor_id, 'actor_mismatch')
        require(self.authority in {'personal', 'organisation'}, 'invalid_binding_authority')
        return {**action.command(), 'session': {
            'mode': 'simulation',
            'provider': 'counterfactual_simulation' if counterfactual else 'development_simulation',
            'subject': scope, 'binding_actor': self.actor_id,
            'authority': self.authority, 'authenticated': False,
        }}
