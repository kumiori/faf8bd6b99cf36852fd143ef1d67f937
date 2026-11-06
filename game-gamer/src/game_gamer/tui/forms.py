"""World-driven action forms for the standalone terminal."""
from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

from .screen import Cancelled
from .text import label


class ActionForms:
    def __init__(self, app):
        self.app = app

    def ask(self, title, default=None):
        prompt = title if default is None else f'{title} [{default}]'
        value = self.app.viewport.prompt(prompt, [], self.app.context())
        if value is None:
            raise Cancelled
        return value.strip() or default or ''

    def pick(self, title, choices, name=label):
        if not choices:
            raise ValueError('No eligible choices for ' + title.lower())
        return self.app.viewport.choose(title, choices, name, self.app.context())

    def confirm(self, title):
        return self.pick(title, [True, False], lambda yes: 'Yes' if yes else 'No')

    def collect(self, candidate, world):
        payload = deepcopy(candidate)
        kind = payload['kind']
        if kind == 'send_contact':
            payload.setdefault('id', 'contact-' + uuid4().hex)
            payload['message'] = self.ask('Invitation message', 'Discuss a possible collaboration?')
            if self.pick('INVITATION DELIVERY', ['Send now', 'Save shared draft'], str) == 'Save shared draft':
                payload['kind'] = 'draft_contact'
        elif kind == 'respond_contact':
            payload['response_message'] = self.ask('Optional response message')
        elif kind == 'propose':
            self.proposal(payload, world)
        elif kind == 'amend':
            agreement = world['agreements'][payload['agreement_id']]
            version = agreement['versions'][payload['version'] - 1]
            terms = deepcopy(version['terms'])
            terms['purpose'] = self.ask('Revised purpose', terms['purpose'])
            for item in terms['responsibilities']:
                item['description'] = self.ask('Contribution by ' + label(world['actors'][item['actor_id']]),
                                               item['description'])
            condition = self.ask('Additional condition')
            if condition:
                terms['conditions'].append(condition)
            payload['terms'] = terms
        elif kind in {'initiate', 'fulfill', 'verify'}:
            if kind == 'fulfill':
                version = world['agreements'][payload['agreement_id']]['versions'][payload['version'] - 1]
                payload['criteria'] = version['verification']['criteria']
                if not self.confirm('Confirm the report addresses ' + ', '.join(payload['criteria'])):
                    raise Cancelled
            payload['reference'] = self.ask('Evidence reference')
        elif kind in {'reject', 'withdraw', 'suspend', 'terminate', 'dispute'}:
            payload['reason'] = self.ask('Reason')
        return payload

    def proposal(self, payload, world):
        actor = self.app.binding.actor_id
        recipient = payload.pop('recipient_id')
        parties = [actor, recipient]
        objective_id = payload.pop('objective_id', None)
        objective = (world['objectives'][objective_id] if objective_id else
                     self.pick('LINK OBJECTIVE', list(world['objectives'].values())))
        while len(parties) < objective['success']['minimum_parties']:
            eligible = [a for a in world['actors'].values() if a['status'] == 'active' and a['id'] not in parties]
            parties.append(self.pick('ADDITIONAL REQUIRED PARTY', eligible)['id'])
        policy = self.pick('GOVERNANCE POLICY', [p for p in world['governance'].values() if p['status'] == 'active'])
        verifier = self.pick('INDEPENDENT VERIFIER', [a for a in world['actors'].values()
                                                     if a['id'] not in parties and a['status'] == 'active'])
        title = self.ask('Agreement title', 'A collective agreement')
        purpose = self.ask('Shared purpose', title)
        responsibilities = [{'actor_id': p, 'description': self.ask('Contribution by ' + label(world['actors'][p]),
                                                                   'Carry out the agreed work')}
                            for p in parties]
        condition = self.ask('Optional condition')
        resources = [r for r in world['resources'].values() if r['owner_id'] in parties]
        allocations = []
        if resources and self.confirm('Reserve a resource on activation?'):
            resource = self.pick('RESOURCE', resources)
            quantity = int(self.ask('Quantity in ' + resource['unit'], '1'))
            allocations.append({'resource_id': resource['id'], 'quantity': quantity})
        deadline = datetime.fromisoformat(world['configuration']['clock']['now']) + timedelta(days=14)
        payload.update(id='agreement-' + uuid4().hex, label=title, parties=parties, objective_id=objective['id'],
                       terms={'purpose': purpose, 'responsibilities': responsibilities,
                              'conditions': [condition] if condition else []},
                       resources=allocations, valid_until=self.ask('Expiry (ISO 8601)', deadline.isoformat()),
                       policy_id=policy['id'], verification={'verifier_ids': [verifier['id']], 'independent': True,
                                                            'criteria': [self.ask('Verification criterion', 'Agreed work completed')]})
