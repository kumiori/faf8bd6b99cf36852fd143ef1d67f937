"""Game-Gamer's simulation, authorisation and projection API."""
from .history.provenance import EpistemicStatus, epistemic_status
from .history.replay import HISTORY_SCHEMA
from .model import DomainError
from .persistence.protocol import CollectiveStore
from .runtime.actions import ActionSubmission, SimulationBinding
from .runtime.governance import PolicyDecision, evaluate_authorisation
from .runtime.runner import Collective
from .schema.definitions import WORLD_SCHEMA

__version__ = '0.2.0'
__all__ = [
    'ActionSubmission', 'Collective', 'CollectiveStore', 'DomainError', 'EpistemicStatus',
    'HISTORY_SCHEMA', 'PolicyDecision', 'SimulationBinding', 'WORLD_SCHEMA',
    'epistemic_status', 'evaluate_authorisation',
]
