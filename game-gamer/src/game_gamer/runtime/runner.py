"""One scoped, simulated collective over an atomic store."""
from copy import deepcopy
from types import MappingProxyType

from ..history.replay import HISTORY_SCHEMA, branch_scope, restore, scope_of
from ..model import DomainError, require
from ..persistence.memory import MemoryStore
from ..persistence.protocol import CollectiveStore
from ..projections.inbox import action_options, inbox
from ..schema.definitions import initialise
from .actions import ActionSubmission, SimulationBinding
from .engine import FIELDS, CollectiveEngine, digest, text
from .governance import PolicyDecision
from ..extensions import EngineFactory


class Collective:
    def __init__(self, store: CollectiveStore):
        self._store = store
        self._scope = scope_of(store.load())
        self._fork = None
        self.extension = store.load().extension
        self._engine_factory = EngineFactory(self.extension)

    @classmethod
    def start(cls, definition, *, path=None, extension=None):
        game = initialise(definition, extension=extension)
        if path is None:
            return cls(MemoryStore(game))
        from ..persistence.sqlite import SQLiteStore

        store = SQLiteStore(path, EngineFactory(game.extension))
        store.initialise(game)
        return cls(store)

    @classmethod
    def open(cls, path, *, scope_id, extension=None):
        from ..persistence.sqlite import SQLiteStore

        collective = cls(SQLiteStore(path, EngineFactory(extension)))
        require(collective._scope == scope_id, 'scope_mismatch')
        return collective

    @classmethod
    def from_history(cls, document, *, extension=None):
        collective = cls(MemoryStore(restore(document, extension=extension)))
        collective._fork = deepcopy(document['fork'])
        return collective

    @property
    def revision(self):
        revision = getattr(self._store, 'revision', None)
        return revision() if callable(revision) else self._store.load().revision

    @property
    def scope_id(self):
        return branch_scope(self._scope, self._fork) if self._fork else self._scope

    def _command(self, submission, binding):
        require(isinstance(submission, ActionSubmission) and isinstance(binding, SimulationBinding),
                'invalid_submission')
        return binding.bind(submission, self.scope_id, counterfactual=self._fork is not None,
                            registry=self.command_registry)

    @property
    def command_registry(self):
        """The immutable active command schemas accepted by this collective."""
        registry = {name: (frozenset(required), frozenset(optional))
                    for name, (required, optional) in FIELDS.items()}
        if self.extension:
            registry.update(self.extension.commands)
        return MappingProxyType(registry)

    def evaluate(self, submission, *, binding):
        """Inspect a decision against one history prefix without accepting it."""
        try:
            command = self._command(submission, binding)
        except DomainError as error:
            return PolicyDecision('rejected', (str(error),))
        game = self._store.load()
        if submission.expected_revision != len(game.project('log')) and game._prior(command) is None:
            return PolicyDecision('rejected', ('stale_version',))
        errors = tuple(game.validate(command))
        if errors == ('missing_authorization',):
            return PolicyDecision('requires_authorisation', errors)
        return PolicyDecision('rejected', errors) if errors else PolicyDecision('allowed')

    def submit(self, submission, *, binding):
        try:
            command = self._command(submission, binding)
        except DomainError as error:
            return {'ok': False, 'errors': [str(error)], 'mutations': []}
        return self._store.submit(command, expected_version=submission.expected_revision)

    def project(self, view='now', *, at=None):
        return self._store.load().project(view, at=at)

    def _bound_snapshot(self, binding, at):
        require(isinstance(binding, SimulationBinding) and binding.scope_id == self.scope_id, 'scope_mismatch')
        require(binding.authority in {'personal', 'organisation'}, 'invalid_binding_authority')
        game = self._store.load()
        if at is not None:
            game = self._engine_factory.from_log(game.project('log', at=at))
        actor = game.get_world()['actors'].get(binding.actor_id, {})
        require(actor.get('status') == 'active', 'unknown_actor')
        require(actor['kind'] != 'organisation' or binding.authority == 'organisation',
                'organisation_binding_required')
        return game

    def inbox(self, *, binding, at=None):
        return inbox(self._bound_snapshot(binding, at), binding.actor_id)

    def action_options(self, *, binding, at=None):
        """Inspect allowed and disabled decisions against one detached world revision."""
        game = self._bound_snapshot(binding, at)
        return {'revision': len(game.project('log')), 'options': action_options(game, binding.actor_id)}

    def history(self):
        events = self.project('log')
        return {'schema': HISTORY_SCHEMA, 'scope_id': self._scope, 'events': events,
                'history_digest': digest(events), 'fork': deepcopy(self._fork)}

    def fork(self, *, at, branch_id):
        """Run counterfactuals in isolated memory with an explicit parent prefix."""
        require(self._fork is None, 'nested_fork_unsupported')
        branch_id = text(branch_id, 'branch_id_required')
        require(type(at) is int and at >= 1, 'invalid_event')
        events = self.project('log', at=at)
        branch = type(self)(MemoryStore(self._engine_factory.from_log(events)))
        branch._fork = {'id': branch_id, 'revision': at, 'prefix_digest': digest(events)}
        return branch
