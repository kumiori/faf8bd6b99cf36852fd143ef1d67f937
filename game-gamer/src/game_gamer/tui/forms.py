"""World-driven action forms for the standalone terminal."""

from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

from .i18n import t
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
            raise ValueError(t('forms.no_eligible_choices_for') + title.lower())
        return self.app.viewport.choose(title, choices, name, self.app.context())

    def confirm(self, title):
        return self.pick(title, [True, False], lambda yes: t('controls.yes') if yes else t('controls.no'))

    def collect(self, candidate, world):
        payload = deepcopy(candidate)
        kind = payload['kind']
        if kind == 'send_contact':
            payload.setdefault('id', 'contact-' + uuid4().hex)
            payload['message'] = self.ask(t('contact.message'), t('forms.discuss_a_possible_collaboration'))
            choices = {'send_contact': t('contact.send_now'), 'draft_contact': t('contact.save_shared_draft')}
            payload['kind'] = self.pick(t('contact.delivery_title'), list(choices), choices.__getitem__)
        elif kind == 'respond_contact':
            payload['response_message'] = self.ask(t('forms.optional_response_message'))
        elif kind == 'propose':
            self.proposal(payload, world)
        elif kind == 'amend':
            agreement = world['agreements'][payload['agreement_id']]
            version = agreement['versions'][payload['version'] - 1]
            terms = deepcopy(version['terms'])
            terms['purpose'] = self.ask(t('forms.revised_purpose'), terms['purpose'])
            for item in terms['responsibilities']:
                item['description'] = self.ask(t('forms.contribution_by') + label(world['actors'][item['actor_id']]),
                                               item['description'])
            condition = self.ask(t('forms.additional_condition'))
            if condition:
                terms['conditions'].append(condition)
            payload['terms'] = terms
        elif kind in {'initiate', 'fulfill', 'verify'}:
            if kind == 'fulfill':
                version = world['agreements'][payload['agreement_id']]['versions'][payload['version'] - 1]
                payload['criteria'] = version['verification']['criteria']
                if not self.confirm(t('forms.confirm_the_report_addresses') + ', '.join(payload['criteria'])):
                    raise Cancelled
            payload['reference'] = self.ask(t('forms.evidence_reference'))
        elif kind in {'reject', 'withdraw', 'suspend', 'terminate', 'dispute'}:
            payload['reason'] = self.ask(t('forms.reason'))
        return payload

    def proposal(self, payload, world):
        actor = self.app.binding.actor_id
        recipient = payload.pop('recipient_id')
        parties = [actor, recipient]
        objective_id = payload.pop('objective_id', None)
        objective = (world['objectives'][objective_id] if objective_id else
                     self.pick(t('forms.link_objective'), list(world['objectives'].values())))
        while len(parties) < objective['success']['minimum_parties']:
            eligible = [a for a in world['actors'].values() if a['status'] == 'active' and a['id'] not in parties]
            parties.append(self.pick(t('forms.additional_required_party'), eligible)['id'])
        policy = self.pick(t('forms.governance_policy'), [p for p in world['governance'].values() if p['status'] == 'active'])
        verifier = self.pick(t('forms.independent_verifier'), [a for a in world['actors'].values()
                                                     if a['id'] not in parties and a['status'] == 'active'])
        title = self.ask(t('forms.agreement_title'), t('forms.a_collective_agreement'))
        purpose = self.ask(t('forms.shared_purpose'), title)
        responsibilities = [{'actor_id': p, 'description': self.ask(t('forms.contribution_by') + label(world['actors'][p]),
                                                                   t('forms.carry_out_the_agreed_work'))}
                            for p in parties]
        condition = self.ask(t('forms.optional_condition'))
        resources = [r for r in world['resources'].values() if r['owner_id'] in parties]
        allocations = []
        if resources and self.confirm(t('forms.reserve_a_resource_on_activation')):
            resource = self.pick(t('objects.resource.title'), resources)
            quantity = int(self.ask(t('forms.quantity_in') + resource['unit'], '1'))
            allocations.append({'resource_id': resource['id'], 'quantity': quantity})
        deadline = datetime.fromisoformat(world['configuration']['clock']['now']) + timedelta(days=14)
        payload.update(id='agreement-' + uuid4().hex, label=title, parties=parties, objective_id=objective['id'],
                       terms={'purpose': purpose, 'responsibilities': responsibilities,
                              'conditions': [condition] if condition else []},
                       resources=allocations, valid_until=self.ask(t('forms.expiry_iso_8601'), deadline.isoformat()),
                       policy_id=policy['id'], verification={'verifier_ids': [verifier['id']], 'independent': True,
                                                            'criteria': [self.ask(t('forms.verification_criterion'), t('forms.agreed_work_completed'))]})
