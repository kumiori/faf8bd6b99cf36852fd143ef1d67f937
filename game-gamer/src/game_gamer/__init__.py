"""Game-Gamer's simulation, authorisation and projection API."""
from .history.provenance import EpistemicStatus, epistemic_status
from .history.replay import HISTORY_SCHEMA
from .model import DomainError
from .persistence.protocol import CollectiveStore
from .runtime.actions import ActionSubmission, SimulationBinding
from .runtime.governance import PolicyDecision, evaluate_authorisation
from .runtime.runner import Collective
from .schema.definitions import WORLD_SCHEMA
from .extensions import CommandDefinition, EngineFactory, Extension, PolicyHook, register_extension
from .runtime.engine import CollectiveEngine
from .capabilities import get_capabilities

__version__ = '0.3.1'
__all__ = [
    'ActionSubmission', 'Collective', 'CollectiveStore', 'DomainError', 'EpistemicStatus',
    'HISTORY_SCHEMA', 'PolicyDecision', 'SimulationBinding', 'WORLD_SCHEMA',
    'epistemic_status', 'evaluate_authorisation',
    'CommandDefinition', 'EngineFactory', 'Extension', 'PolicyHook', 'register_extension', 'CollectiveEngine',
    'get_capabilities',
]
