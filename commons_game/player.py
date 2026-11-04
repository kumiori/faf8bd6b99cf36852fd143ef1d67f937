"""Fixed-actor application boundary, compatible with Hube's local session rule."""
from copy import deepcopy
from uuid import uuid4


class ActorSession:
    def __init__(self, game, actor, *, store=None, hot_seat=False, identity=None, binding=None, provider=None):
        self._game = game
        self.store = store
        self.hot_seat = hot_seat
        self.identity, self.binding, self.provider = identity, binding, provider
        self._check_actor(actor)
        self._actor = actor
        self._check_binding()

    def _check_binding(self):
        if self.identity is None:
            return  # Existing explicitly simulated local sessions remain compatible.
        actor = self.current().get_world()['actors'][self.actor]
        if (self.identity.mode != 'simulation' or self.identity.authenticated or self.provider is None
                or not self.provider.permits(self.identity, self.binding, actor)):
            raise ValueError('verified_simulation_binding_required')

    def current(self):
        return self.store.load() if self.store is not None else self._game

    @property
    def actor(self):
        return self._actor

    def _check_actor(self, actor):
        if self.current().get_world()['actors'].get(actor, {}).get('status') != 'active':
            raise ValueError('unknown_actor')

    def switch(self, actor):
        if self.identity is not None:
            raise ValueError('sign_out_before_changing_player')
        if not self.hot_seat:
            raise ValueError('hot_seat_required')
        self._check_actor(actor)
        self._actor = actor

    def submit(self, command, *, expected_version=None):
        self._check_binding()
        if not isinstance(command, dict):
            return {'ok': False, 'errors': ['invalid_command'], 'mutations': []}
        if command.get('actor', self.actor) != self.actor:
            return {'ok': False, 'errors': ['actor_mismatch'], 'mutations': []}
        payload = {**deepcopy(command), 'actor': self.actor}
        if self.identity is not None:
            payload['session'] = {'mode': 'simulation', 'provider': self.identity.provider,
                                  'subject': self.identity.subject, 'binding_actor': self.binding.actor_id,
                                  'authority': self.binding.authority, 'authenticated': False}
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
        self._check_binding()
        world = game.get_world()
        candidates = []
        proposal = world['configuration']['world']['proposal']
        if proposal and proposal['id'] not in world['agreements']:
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
        from .invitations import records
        for invitation in records(world):
            base = {'invitation_id': invitation['id']}
            candidates.extend([{'kind': 'publish_contact', **base}, {'kind': 'withdraw_contact', **base},
                               {'kind': 'respond_contact', 'response': 'accept', **base},
                               {'kind': 'respond_contact', 'response': 'decline', **base}])
        result = []
        for candidate in candidates:
            command = {**candidate, 'actor': self.actor, 'key': 'probe-' + uuid4().hex}
            if not game.validate(command):
                result.append({key: value for key, value in candidate.items()
                               if key in {'kind', 'agreement_id', 'version', 'invitation_id', 'response'}})
        if proposal is None:
            result.insert(0, {'kind': 'propose'})
        return len(game.project('log')), result

    def inbox(self):
        """Attention is derived from state and the engine's current permissions."""
        game = self.current()
        # Compute against one consistent history prefix, including action checks.
        snapshot = ActorSession(game, self.actor, identity=self.identity, binding=self.binding, provider=self.provider)
        _, candidates = snapshot.available_actions()
        world = game.get_world(); items = []
        for agreement in world['agreements'].values():
            actions = [c for c in candidates if c.get('agreement_id') == agreement['id']]
            kinds = {c['kind'] for c in actions}; reasons = []
            if 'accept' in kinds:
                reasons.append('Amendment awaiting your response' if agreement['current_version'] > 1 else
                               'Your proposal awaiting your acceptance' if agreement['created_by'] == self.actor else
                               'Proposal awaiting your response')
            if 'authorize' in kinds:
                reasons.append('Awaiting your authorisation')
            if kinds & {'initiate', 'fulfill'}:
                reasons.append('Outstanding obligations')
            if 'verify' in kinds:
                reasons.append('Independent verification requested')
            if reasons:
                items.append({'contract_id': agreement['id'], 'label': agreement['label'],
                              'reasons': reasons, 'actions': actions})
        return items

    def inbox_groups(self):
        """Perspective-specific navigation, derived without changing permissions."""
        world = self.current().get_world()
        actionable = {item['contract_id']: item for item in self.inbox()}
        groups = {name: [] for name in ('Proposals received', 'My proposals', 'Awaiting my acceptance',
                                      'Awaiting other parties', 'Other actionable requests')}
        for agreement in world['agreements'].values():
            item = {'contract_id': agreement['id'], 'label': agreement['label']}
            version = agreement['versions'][agreement['current_version'] - 1]
            involved = self.actor in agreement['parties']
            open_proposal = agreement['status'] in {'proposed', 'negotiating', 'accepted', 'authorized'}
            if agreement['created_by'] == self.actor:
                groups['My proposals'].append(item)
            elif involved and open_proposal:
                groups['Proposals received'].append(item)
            actions = actionable.get(agreement['id'], {}).get('actions', [])
            if any(action['kind'] == 'accept' for action in actions):
                groups['Awaiting my acceptance'].append(item)
            if involved and open_proposal and any(p not in version['acceptances'] for p in agreement['parties'] if p != self.actor):
                groups['Awaiting other parties'].append(item)
            if any(action['kind'] in {'publish_proposal','authorize','activate','initiate','fulfill','verify'} for action in actions):
                groups['Other actionable requests'].append(item)
        return groups

    def inbox_records(self, category=None):
        """One canonical row per object; overlapping filters become badges.

        Read and permission checks use one immutable event prefix. Existing
        contract-only attention APIs remain available to older clients.
        """
        game = self.current()
        snapshot = ActorSession(game, self.actor, identity=self.identity, binding=self.binding, provider=self.provider)
        _, actions = snapshot.available_actions()
        world = game.get_world(); output = []
        for agreement in world['agreements'].values():
            own_actions = [a for a in actions if a.get('agreement_id') == agreement['id']]
            if self.actor not in agreement['parties'] and not own_actions:
                continue
            tags = ['History']; badges = []
            version = agreement['versions'][agreement['current_version'] - 1]
            kinds = {a['kind'] for a in own_actions}
            if agreement['created_by'] == self.actor:
                badges.append('Proposed by you')
            else:
                badges.append('Proposal received')
            if agreement['status'] in {'draft', 'proposed', 'negotiating'}:
                tags.append('Contract proposals')
            if 'accept' in kinds:
                tags.append('Awaiting my decision'); badges.append('Your acceptance pending')
            pending = [p for p in agreement['parties'] if p != self.actor and p not in version['acceptances']]
            if pending and agreement['status'] in {'proposed', 'negotiating', 'accepted', 'authorized'}:
                tags.append('Awaiting other parties')
                from .presentation import actor_label
                badges.extend(actor_label(world,p)+"'s acceptance pending" for p in pending)
            if agreement['status'] in {'accepted', 'authorized', 'active', 'fulfilled', 'suspended', 'disputed'}:
                tags.append('Agreements in progress')
            if 'verify' in kinds:
                tags += ['Verification requests', 'Awaiting my decision']
            elif kinds & {'authorize', 'activate', 'publish_proposal'}:
                tags.append('Awaiting my decision')
            from .presentation import status
            badges += [status(agreement['status']).lower(), 'Outcome '+status(agreement['outcome_status']).lower()]
            output.append({'id': agreement['id'], 'kind': 'agreement', 'label': agreement['label'],
                           'status': agreement['status'], 'outcome_status': agreement['outcome_status'],
                           'badges': badges, 'categories': list(dict.fromkeys(tags)), 'actions': own_actions})
        from .invitations import records
        for invitation in records(world):
            sender = invitation['source_id'] == self.actor
            if not sender and (invitation['target_id'] != self.actor or invitation['status'] == 'draft'):
                continue
            own_actions = [a for a in actions if a.get('invitation_id') == invitation['id']]
            tags = ['History', 'Outgoing invitations' if sender else 'Incoming invitations']
            if invitation['status'] == 'accepted': tags.append('Accepted connections')
            if not sender and invitation['status'] == 'sent': tags.append('Awaiting my decision')
            if sender and invitation['status'] == 'sent': tags.append('Awaiting other parties')
            from .presentation import actor_label
            other = world['actors'][invitation['target_id'] if sender else invitation['source_id']]
            output.append({'id': invitation['id'], 'kind': 'invitation',
                'status': invitation['status'],
                'label': ('To ' if sender else 'From ')+actor_label(world,other['id']),
                'badges': [invitation['status'], 'Simulation contact only'], 'categories': tags, 'actions': own_actions})
        return [item for item in output if category is None or category in item['categories']]
