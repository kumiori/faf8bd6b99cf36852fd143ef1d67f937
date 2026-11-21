"""Versioned, trusted application extensions for the collective runtime."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .model import require

EXTENSION_CONTRACT = 'game-gamer/extension/v1'
EXTENSION_RECORD = 'game-gamer:extension'


@dataclass(frozen=True)
class CommandDefinition:
    """Additional declarative payload fields and a trusted transition handler."""
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    handler: Callable | None = None
    target_field: str | None = None

    def __post_init__(self):
        object.__setattr__(self, 'required', frozenset(self.required))
        object.__setattr__(self, 'optional', frozenset(self.optional))
        require(not self.required & self.optional, 'overlapping_command_fields')
        fields = self.required | self.optional
        require(all(isinstance(name, str) and name for name in fields), 'invalid_command_fields')
        require(not fields & {'kind', 'key', 'actor', 'session'}, 'reserved_command_field')
        require(self.target_field is None or self.target_field in fields, 'invalid_target_field')
        require(callable(self.handler), 'command_handler_required')


@dataclass(frozen=True)
class PolicyHook:
    """Before hooks inspect a detached world. After hooks extend the candidate world."""
    before: Callable | None = None
    after: Callable | None = None

    def __post_init__(self):
        require(self.before is not None or self.after is not None, 'empty_policy_hook')
        require(all(value is None or callable(value) for value in (self.before, self.after)), 'invalid_policy_hook')


@dataclass(frozen=True)
class Extension:
    id: str
    version: str
    commands: Mapping[str, CommandDefinition] = field(default_factory=dict)
    policies: tuple[PolicyHook, ...] = ()
    projections: Mapping[str, Callable] = field(default_factory=dict)
    initialise: Callable | None = None
    contract: str = EXTENSION_CONTRACT

    def __post_init__(self):
        require(self.contract == EXTENSION_CONTRACT, 'unsupported_extension_contract')
        require(all(isinstance(value, str) and value and value == value.strip() for value in (self.id, self.version)),
                'invalid_extension_identity')
        from .runtime.engine import FIELDS
        require(not self.commands.keys() & FIELDS.keys(), 'extension_command_collision')
        require(all(isinstance(name, str) and name and isinstance(spec, CommandDefinition)
                    for name, spec in self.commands.items()), 'invalid_extension_command')
        require(all(isinstance(policy, PolicyHook) for policy in self.policies), 'invalid_extension_policy')
        require(all(isinstance(name, str) and name and callable(handler) for name, handler in self.projections.items()),
                'invalid_extension_projection')
        require(not self.projections.keys() & {'world', 'log', 'timeline', 'now'}, 'reserved_projection')
        require(self.initialise is None or callable(self.initialise), 'invalid_extension_initialiser')
        object.__setattr__(self, 'commands', MappingProxyType(dict(self.commands)))
        object.__setattr__(self, 'projections', MappingProxyType(dict(self.projections)))
        object.__setattr__(self, 'policies', tuple(self.policies))

    def descriptor(self):
        return {'id': self.id, 'version': self.version, 'contract': self.contract}


_REGISTRY = {}


def register_extension(extension):
    """Register installed trusted code. Saved data never imports executable code."""
    require(isinstance(extension, Extension), 'invalid_extension')
    key = (extension.id, extension.version)
    require(key not in _REGISTRY or _REGISTRY[key] is extension, 'extension_registration_conflict')
    _REGISTRY[key] = extension
    return extension


def resolve_extension(extension=None, *, required=None):
    if isinstance(extension, dict):
        require(set(extension) == {'id', 'version', 'contract'}, 'invalid_extension_descriptor')
        require(all(isinstance(value, str) and value for value in extension.values()), 'invalid_extension_descriptor')
        require(extension['contract'] == EXTENSION_CONTRACT, 'unsupported_extension_contract')
        required = extension if required is None else required
        extension = _REGISTRY.get((extension['id'], extension['version']))
        require(extension is not None, 'extension_unavailable')
    require(extension is None or isinstance(extension, Extension), 'invalid_extension')
    if required is not None:
        require(isinstance(required, dict) and set(required) == {'id', 'version', 'contract'},
                'invalid_extension_descriptor')
        require(all(isinstance(value, str) and value for value in required.values()), 'invalid_extension_descriptor')
        require(required['contract'] == EXTENSION_CONTRACT, 'unsupported_extension_contract')
        if extension is None:
            extension = _REGISTRY.get((required['id'], required['version']))
        require(extension is not None, 'extension_unavailable')
        require(extension.descriptor() == required, 'extension_version_mismatch')
    return extension


def extension_record(extension):
    return {'id': EXTENSION_RECORD, 'status': 'active', 'schema': EXTENSION_CONTRACT,
            'required': extension.descriptor()}


def extension_from_events(events, extension=None):
    required = None
    for event in events:
        for mutation in event['mutations']:
            if mutation['entity_type'] == 'configuration' and mutation['entity_id'] == EXTENSION_RECORD:
                record = mutation['after']
                require(record.get('schema') == EXTENSION_CONTRACT, 'unsupported_extension_contract')
                descriptor = record['required']
                require(required is None or descriptor == required, 'extension_changed_in_history')
                required = descriptor
    return resolve_extension(extension, required=required)


@dataclass(frozen=True)
class EngineFactory:
    """Construction/reconstruction dependency consumed by the existing stores."""
    extension: Extension | dict | None = None

    def __call__(self):
        from .runtime.engine import CollectiveEngine
        return CollectiveEngine(extension=self.extension)

    def from_log(self, entries):
        from .runtime.engine import CollectiveEngine
        return CollectiveEngine.from_log(entries, extension=self.extension)
