"""Fixed-actor application boundary, compatible with Hube's local session rule."""
from copy import deepcopy
from uuid import uuid4


class ActorSession:
    def __init__(self, game, actor, *, store=None, hot_seat=False):
        self._game = game
        self.store = store
        self.hot_seat = hot_seat
        self._check_actor(actor)
        self._actor = actor

    def current(self):
        return self.store.load() if self.store is not None else self._game

    @property
    def actor(self):
        return self._actor

    def _check_actor(self, actor):
        if self.current().get_world()['actors'].get(actor, {}).get('status') != 'active':
            raise ValueError('unknown_actor')

    def switch(self, actor):
        if not self.hot_seat:
            raise ValueError('hot_seat_required')
        self._check_actor(actor)
        self._actor = actor

    def submit(self, command, *, expected_version=None):
        if not isinstance(command, dict):
            return {'ok': False, 'errors': ['invalid_command'], 'mutations': []}
        if command.get('actor', self.actor) != self.actor:
            return {'ok': False, 'errors': ['actor_mismatch'], 'mutations': []}
        payload = {**deepcopy(command), 'actor': self.actor}
        payload.setdefault('key', 'play-' + uuid4().hex)
        if self.store is not None:
            return self.store.submit(payload, expected_version=expected_version)
        if expected_version is not None and expected_version != len(self._game.project('log')):
            prior = self._game._prior(payload)
            if prior is None:
                return {'ok': False, 'errors': ['stale_version'], 'mutations': []}
        return self._game.submit(payload)

    def available_actions(self):
        """Pure engine checks; probe evidence is never returned or submitted."""
        game = self.current()
        world = game.get_world()
        candidates = []
        proposal = world['configuration']['world']['proposal']
        if proposal['id'] not in world['agreements']:
            candidates.append({'kind': 'propose', **deepcopy(proposal)})
        for agreement in world['agreements'].values():
            version = agreement['versions'][agreement['current_version'] - 1]
            base = {'agreement_id': agreement['id'], 'version': version['number']}
            for kind in ('publish_proposal', 'accept', 'authorize', 'activate', 'initiate', 'fulfill', 'verify',
                         'reject', 'withdraw', 'suspend', 'resume', 'terminate', 'dispute', 'amend'):
                command = {'kind': kind, **base}
                if kind in {'initiate', 'fulfill', 'verify'}:
                    command['reference'] = 'Pure availability probe; never submitted.'
                if kind in {'reject', 'withdraw', 'suspend', 'terminate', 'dispute'}:
                    command['reason'] = 'Pure availability probe; never submitted.'
                if kind == 'fulfill':
                    command['criteria'] = deepcopy(version['verification']['criteria'])
                if kind == 'amend':
                    command['terms'] = deepcopy(version['terms'])
                candidates.append(command)
        result = []
        for candidate in candidates:
            command = {**candidate, 'actor': self.actor, 'key': 'probe-' + uuid4().hex}
            if not game.validate(command):
                result.append({key: value for key, value in candidate.items()
                               if key in {'kind', 'agreement_id', 'version'}})
        return len(game.project('log')), result
