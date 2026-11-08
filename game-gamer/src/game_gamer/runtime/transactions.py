"""Shared transaction machinery; domain rules live in subclasses."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from threading import RLock
from ..history.events import Mutation
from ..transitions import observe_submission


class WorldEngine:
    tables = ('nodes', 'relations', 'actions', 'evidence', 'requirements')
    entity_tables = dict(zip(('node', 'relation', 'action', 'evidence', 'requirement'), tables))
    epoch = datetime.fromisoformat('2026-10-06T00:00:00+00:00')

    def __init__(self):
        self._world = {table: {} for table in self.tables}
        self._log = []
        self._lock = RLock()

    def _decorate_event(self, event, before, after):
        """Optional domain audit fields; legacy events stay byte-compatible."""

    def _validate_event(self, entry, before):
        """Optional domain replay checks, before applying an event's mutations."""

    @property
    def revision(self):
        return len(self._log)

    def get_world(self):
        return deepcopy(self._world)


    def _timestamp(self):
        return (self.epoch + timedelta(seconds=len(self._log))).isoformat()


    def _commit(self, before, after, summary, actor='system', action_id=None, command=None):
        seq = len(self._log) + 1
        mutations = []
        for entity_type, table in self.entity_tables.items():
            for id, record in after[table].items():
                old = before[table].get(id)
                if old != record:
                    mutations.append(asdict(Mutation(
                        id=f'mutation_{seq:06}_{len(mutations)+1:03}', action_id=action_id,
                        kind='create' if old is None else 'transition' if old.get('status') != record.get('status') or (entity_type == 'node' and old.get('metadata') != record.get('metadata')) else 'update', entity_type=entity_type,
                        entity_id=id, before=deepcopy(old), after=deepcopy(record),
                        occurred_at=self._timestamp(), caused_by=actor)))
        event = {'id': f'log_{seq:06}', 'sequence': seq, 'occurred_at': self._timestamp(),
                 'kind': summary, 'actor_id': actor, 'action_id': action_id,
                 'mutations': mutations, 'command': deepcopy(command)}
        self._decorate_event(event, before, after)
        self._log.append(event)
        self._world = deepcopy(after)
        return deepcopy(event)


    @staticmethod
    def _result(event):
        return {'ok': True, 'command_id': event['command']['key'],
                'action_id': event['action_id'], 'mutations': deepcopy(event['mutations']),
                'errors': [], 'warnings': [],
                'affected_entities': [m['entity_id'] for m in event['mutations']]}


    def _prior(self, command):
        return next((e for e in self._log if e['command'] and
                     e['command']['key'] == command.get('key')), None)


    @observe_submission
    def submit(self, command, *, expected_version=None):
        with self._lock:
            if expected_version is not None and expected_version != len(self._log):
                if not isinstance(command, dict) or self._prior(command) is None:
                    return {'ok': False, 'errors': ['stale_version'], 'mutations': []}
            errors = self.validate(command)
            if errors:
                return {'ok': False, 'errors': errors, 'mutations': []}
            prior = self._prior(command)
            if prior:
                return self._result(prior)
            world, action_id, summary = self._prepare(command)
            event = self._commit(self._world, world, summary, command['actor'], action_id, command)
            return self._result(event)


    def apply(self, command):
        # No public validation bypass.
        return self.submit(command)


    def world_at(self, *, event=None, time=None):
        if event is not None and time is not None:
            raise ValueError('choose_event_or_time')
        if event is not None and (type(event) is not int or not 0 <= event <= len(self._log)):
            raise ValueError('invalid_event')
        cutoff = datetime.fromisoformat(time) if time is not None else None
        if cutoff is not None and cutoff.tzinfo is None:
            raise ValueError('timezone_required')
        world = {k: {} for k in self.tables}
        for entry in self._log:
            if event is not None and entry['sequence'] > event:
                break
            if cutoff is not None and datetime.fromisoformat(entry['occurred_at']) > cutoff:
                break
            for mutation in entry['mutations']:
                world[self.entity_tables[mutation['entity_type']]][mutation['entity_id']] = deepcopy(mutation['after'])
        return world


    def save(self, path):
        from ..persistence.log import save_log
        save_log(path, self._log)


    @classmethod
    def load(cls, path):
        from ..persistence.log import load_log
        return cls.from_log(load_log(path))


    def replay(self):
        with self._lock:
            return self.from_log(self._log)


    def snapshot(self):
        """Return a detached copy of an already validated history prefix."""
        with self._lock:
            game = type(self)()
            game._world = deepcopy(self._world)
            game._log = deepcopy(self._log)
            return game

    def _replay_events(self, entries):
        previous_time = datetime.fromisoformat(self._log[-1]['occurred_at']) if self._log else None
        for seq, entry in enumerate(entries, len(self._log)+1):
            timestamp = datetime.fromisoformat(entry['occurred_at'])
            if entry['sequence'] != seq or timestamp.tzinfo is None or (previous_time and timestamp <= previous_time):
                raise ValueError('invalid_log_sequence')
            self._validate_event(entry, self._world)
            previous_time = timestamp
            for mutation in entry['mutations']:
                table = self.entity_tables[mutation['entity_type']]
                eid = mutation['entity_id']
                if self._world[table].get(eid) != mutation['before'] or mutation['after']['id'] != eid:
                    raise ValueError('invalid_mutation_chain')
                self._world[table][eid] = deepcopy(mutation['after'])
            self._log.append(deepcopy(entry))

    @classmethod
    def from_log(cls, entries):
        game = cls()
        game._replay_events(entries)
        return game
