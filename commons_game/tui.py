"""Terminal-first laboratory. Forms produce commands; the engine owns decisions."""

import json
import shutil
import sys
import textwrap
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from game_gamer.tui.errors import error_list, error_message
from game_gamer.tui.i18n import message_key
from game_gamer.tui.screen import Cancelled as Cancelled

from .i18n import t
from .player import ActorSession
from .presentation import display_label, display_world

ACTION_NAMES = {
    'draft_contact': message_key('contracts.actions.draft_contact'), 'send_contact': message_key('contact.invite'),
    'publish_contact': message_key('contracts.actions.publish_contact'), 'respond_contact': message_key('contracts.actions.respond_contact'),
    'withdraw_contact': message_key('contracts.actions.withdraw_contact'),
    'publish_proposal': message_key('contracts.actions.publish_proposal'),
    'propose': message_key('contracts.actions.propose'), 'amend': message_key('contracts.actions.amend'),
    'accept': message_key('contracts.actions.accept'), 'authorize': message_key('contracts.actions.authorize'),
    'activate': message_key('contracts.actions.activate'), 'initiate': message_key('contracts.record_action'),
    'fulfill': message_key('contracts.actions.fulfill'), 'verify': message_key('contracts.actions.verify'),
    'reject': message_key('contracts.actions.reject'), 'withdraw': message_key('contracts.actions.withdraw'),
    'suspend': message_key('contracts.actions.suspend'), 'resume': message_key('contracts.actions.resume'),
    'terminate': message_key('contracts.actions.terminate'), 'dispute': message_key('contracts.actions.dispute'),
}
EVENT_NAMES = {
    'invitation.drafted': message_key('history.events.invitation_drafted'), 'invitation.sent': message_key('history.events.invitation_sent'),
    'invitation.accepted': message_key('history.events.invitation_accepted'),
    'invitation.declined': message_key('history.events.invitation_declined'), 'invitation.withdrawn': message_key('history.events.invitation_withdrawn'),
    'draft_contact': message_key('history.events.invitation_drafted'), 'send_contact': message_key('history.events.invitation_sent'),
    'publish_contact': message_key('history.events.publish_contact'), 'respond_contact': message_key('history.events.respond_contact'),
    'withdraw_contact': message_key('history.events.invitation_withdrawn'),
    'ecosystem.imported': message_key('history.events.ecosystem_imported'),
    'publish_proposal': message_key('history.events.publish_proposal'),
    'initialize': message_key('history.events.initialize'), 'draft': message_key('history.events.draft'),
    'propose': message_key('history.events.propose'), 'amend': message_key('history.events.amend'),
    'accept': message_key('history.events.accept'), 'authorize': message_key('history.events.authorize'),
    'activate': message_key('history.events.activate'), 'initiate': message_key('history.events.initiate'),
    'fulfill': message_key('history.events.fulfill'), 'verify': message_key('history.events.verify'),
    'reject': message_key('history.events.reject'), 'withdraw': message_key('history.events.withdraw'),
    'suspend': message_key('history.events.suspend'), 'resume': message_key('history.events.resume'),
    'terminate': message_key('history.events.terminate'), 'dispute': message_key('history.events.dispute'),
}




def action_name(kind):
    return t(ACTION_NAMES[kind])


def event_name(kind, fallback=None):
    key = EVENT_NAMES.get(kind)
    return t(key) if key else (kind if fallback is None else fallback)


def display(value):
    """Player-authored text is text, never terminal control or executable code."""
    return ''.join(char for char in str(value) if char.isprintable() or char in '\n\t')


def status_label(value):
    return {'authorized': 'authorised'}.get(value, value)


def render_trajectory(document, output, *, branch_id=None):
    from .trajectory import frames
    envelope = document['plan']['commons_trajectory']
    output.write(t('laboratory.render_trajectory.saddle_pathways_trajectory'))
    output.write(t('laboratory.render_trajectory.world', scenario=envelope['provenance']['scenario']))
    history = (t('laboratory.render_trajectory.hypothetical_branch') + branch_id if branch_id else
               t('laboratory.render_trajectory.recorded_history'))
    output.write(t('laboratory.render_trajectory.context', world_kind=envelope['provenance']['world_kind'], history=history))
    last = 0
    for frame in frames(document, branch_id=branch_id):
        last = frame['sequence']
        label = event_name(frame['kind'])
        output.write(t('laboratory.render_trajectory.state', sequence=last, history_kind=frame['history_kind'], event=display(label)))
        output.write(t('laboratory.render_trajectory.actor_event_commit', value=display(frame['actor_id']), event_id=frame['event_id'], commit_id=frame['commit_id']))
        for agreement in frame['agreements']:
            output.write(t('laboratory.render_trajectory.v_outcome', value=display(agreement['id']), current_version=agreement['current_version'], status=status_label(agreement['status']), outcome_status=agreement['outcome_status']))
    output.write(t('laboratory.render_trajectory.current_state_no_geometric_coordinates', last=last))


class Terminal:
    def __init__(self, game, *, actor=None, store=None, hot_seat=False, source=None, output=None,
                 provider=None, identity=None, plain=False, explore=False):
        self.game, self.store, self.hot_seat = game, store, hot_seat
        self.source = source if source is not None else sys.stdin
        self.output = output if output is not None else sys.stdout
        self.session = ActorSession(game, actor, store=store, hot_seat=hot_seat) if actor else None
        self.branches = []
        self.provider, self.identity = provider, identity
        self.plain, self.explore = plain, explore
        self.last_contract = None

    def write(self, value=''):
        value = display(value)
        if self.plain:
            value = value.translate(str.maketrans({'╔': '+', '╗': '+', '╚': '+', '╝': '+', '═': '-',
                      '║': '|', '→': '->', '≠': '!=', '—': '-', '✓': '*'}))
        if self.output is sys.stdout and self.output.isatty():
            width = max(20, shutil.get_terminal_size().columns)
            value = '\n'.join('\n'.join(textwrap.wrap(line, width=width, replace_whitespace=False,
                                     drop_whitespace=False)) for line in value.split('\n'))
        self.output.write(value + '\n')
        self.output.flush()

    def read(self, prompt='>'):
        self.write(prompt)
        line = self.source.readline()
        if not line:
            raise EOFError
        return line.strip()

    def current(self):
        return self.session.current() if self.session else self.store.load() if self.store else self.game

    def ask(self, prompt, *, default=None, parse=None):
        while True:
            raw = self.read(prompt + (f' [{default}]' if default is not None else ''))
            if raw.lower() in {'0', 'b', 'q'}:
                raise Cancelled
            if raw == '?':
                self.write(t('laboratory.ask.shortcut_0_b_cancel_this_form'))
                continue
            value = default if not raw and default is not None else raw
            try:
                if parse:
                    return parse(value)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError
                return value.strip()
            except (ValueError, TypeError):
                self.write(t('laboratory.ask.invalid_input_please_try_again'))

    def choose(self, prompt, items, label=str):
        if not items:
            self.write(t('laboratory.choose.no_available_choices'))
            raise Cancelled
        self.write(prompt)
        for index, item in enumerate(items, 1):
            self.write(f'[{index}] {label(item)}')
        def selected(value):
            number = int(value)
            if not 1 <= number <= len(items):
                raise ValueError
            return items[number - 1]
        return self.ask(t('laboratory.choose.choice_0_cancels'), parse=selected)

    def confirm(self, prompt):
        def yes_no(value):
            if value.casefold() not in {'y', 'yes', t('controls.yes').casefold(), 'n', 'no', t('controls.no').casefold()}:
                raise ValueError
            return value.casefold() in {'y', 'yes', t('controls.yes').casefold()}
        return self.ask(prompt + ' y/N', default='n', parse=yes_no)

    def select_actor(self):
        actors = [a for a in self.current().project('actors') if a['status'] == 'active']
        selected = self.choose(t('laboratory.select_actor.select_your_local_actor_identity'), actors, lambda a: display_label(a))
        if self.session:
            self.session.switch(selected['id'])
        else:
            self.session = ActorSession(self.game, selected['id'], store=self.store, hot_seat=self.hot_seat)
        self.write(t('laboratory.select_actor.selected_actor', actor=display_label(selected), id=selected['id']))

    def inspect_contract(self, agreement):
        version = agreement['versions'][agreement['current_version'] - 1]
        self.write(t('laboratory.inspect_contract.contract_version', id=agreement['id'], number=version['number'], status=status_label(agreement['status'])))
        self.write(t('laboratory.inspect_contract.outcome_content_digest', outcome_status=agreement['outcome_status'], content_digest=version['content_digest']))
        self.write(t('contracts.parties_prefix') + ', '.join(agreement['parties']))
        self.write(t('contracts.purpose_prefix') + version['terms']['purpose'])
        for obligation in version['terms']['responsibilities']:
            self.write(t('laboratory.inspect_contract.obligation', actor_id=obligation['actor_id'], description=obligation['description']))
        for condition in version['terms']['conditions']:
            self.write(t('laboratory.inspect_contract.condition') + condition)
        self.write(t('laboratory.inspect_contract.accepted_by') + (', '.join(version['acceptances']) or 'nobody'))
        self.write(t('laboratory.inspect_contract.authorised_by') + (', '.join(version['authorizations']) or 'nobody'))
        self.write(t('laboratory.inspect_contract.designated_independent_verifier_s') + ', '.join(version['verification']['verifier_ids']))
        self.write(t('laboratory.inspect_contract.requested_resources') + json.dumps(version['resources']))
        self.write(t('laboratory.inspect_contract.valid_until') + version['valid_until'])
        world = self.current().get_world()
        policy = world['governance'][version['policy_id']]
        self.write(t('laboratory.inspect_contract.authorisation_policy') + policy['label'])
        self.write(t('laboratory.inspect_contract.required_approvers') + (', '.join(policy['required_actors']) or 'none')
                   + t('laboratory.inspect_contract.threshold_categories', threshold=policy['threshold'], value=', '.join(policy['required_categories']) or 'none'))
        for eid in agreement['evidence_ids']:
            self.write(t('laboratory.inspect_contract.evidence') + json.dumps(world['evidence'][eid], ensure_ascii=False))
        if self.session:
            _, actions = self.session.available_actions()
            names = [action_name(a['kind']) for a in actions if a.get('agreement_id') == agreement['id']]
            self.write(t('laboratory.inspect_contract.your_available_actions') + ('; '.join(names) or 'none'))

    def inspect_node(self, node_id, *, at=None):
        from .projections import neighbourhood
        game = self.current()
        graph = neighbourhood(game.project('network', at=at), node_id)
        node = next(n for n in graph['nodes'] if n['id'] == node_id)
        self.write(t('laboratory.inspect_node.node', id=node_id, kind=node['kind'], label=display_label(node)))
        if node['kind'] == 'agreement' and at is None:
            self.inspect_contract(node)
        else:
            self.write(json.dumps({**node, 'label': display_label(node)}, ensure_ascii=False, indent=2))
        self.write(t('laboratory.inspect_node.neighbourhood') + (t('laboratory.inspect_node.historical_state', at=at) if at else t('laboratory.inspect_node.current_world')))
        for edge in graph['edges']:
            arrow = '-->'
            if 'directed' in edge:
                arrow = '-->' if edge['directed'] is True else '--' if edge['directed'] is False else t('laboratory.inspect_node.direction_unknown')
            self.write(f"{edge['source_id']} --{edge['kind']}{arrow} {edge['target_id']}")
        self.write(t('laboratory.inspect_node.linked_nodes') + ', '.join(n['id'] for n in graph['nodes'] if n['id'] != node_id))

    def node_history(self, node_id):
        game = self.current()
        events = [e for e in game.project('log') if any(m['entity_id'] == node_id for m in e['mutations'])]
        for event in events:
            self.write(f"{event['sequence']:03} {event['id']} / {event['commit']['id']} / {event['kind']} / {event['actor_id']}")
        if events:
            self.write(t('laboratory.node_history.creation_historical_graph'))
            self.inspect_node(node_id, at=events[0]['sequence'])
        self.write(t('laboratory.node_history.return_to_the_current_world') + node_id)

    def reference(self, value='', *, contracts_only=False):
        from .commands import resolve
        world=self.current().get_world()
        found=resolve(world,value)
        if found and (not contracts_only or found in world['agreements']):
            return found
        nodes=self.current().project('network')['nodes']
        if contracts_only:nodes=[n for n in nodes if n['kind']=='agreement']
        return self.choose(t('laboratory.reference.choose_an_object'),nodes,display_label)['id']

    def graph(self, focus=None):
        from collections import Counter
        while True:
            graph = self.current().project('network')
            self.write(t('laboratory.graph.world_graph') + self.current().get_world()['configuration']['world']['title'])
            self.write(' / '.join(f'{kind}: {count}' for kind, count in Counter(n['kind'] for n in graph['nodes']).items()))
            if focus:
                self.inspect_node(focus)
            else:
                for node in graph['nodes']:
                    self.write(f"{node['id']} / {node['kind']} / {display_label(node)} / {status_label(node.get('status', 'unknown'))}"
                               + (t('laboratory.graph.outcome_suffix', status=node['outcome_status']) if 'outcome_status' in node else ''))
            self.write(t('laboratory.graph.open_id_history_id_past'))
            raw = self.read()
            from .commands import parse
            command,value=parse(raw)
            verb=command.name if command else raw
            if verb.lower() in {'b', 'q', '0'}:
                return
            try:
                if verb == 'open':
                    value=self.reference(value); self.inspect_node(value); focus=value
                elif verb == 'history':
                    self.node_history(self.reference(value,contracts_only=not bool(value)))
                elif verb == 'past':
                    if not value:
                        target=self.reference(contracts_only=True)
                        entries=[e for e in self.current().project('log') if any(m['entity_id']==target for m in e['mutations'])]
                        entry=self.choose(t('laboratory.graph.choose_a_historical_state'),entries,lambda e:t('laboratory.graph.state', sequence=e['sequence'], kind=e['kind']))
                        self.inspect_node(target,at=entry['sequence']);continue
                    sequence, target = value.split(' ', 1)
                    target=self.reference(target)
                    self.inspect_node(target, at=int(sequence))
                elif verb == 'contracts':
                    from .projections import contract_registry
                    filters = dict(item.split('=', 1) for item in value.split())
                    if filters.keys() - {'actor', 'status', 'objective', 'resource'}:
                        raise ValueError('unknown_contract_filter')
                    for agreement in contract_registry(self.current().get_world(), **filters):
                        self.write(t('laboratory.graph.contract_summary', id=agreement['id'], label=agreement['label'],
                                     status=status_label(agreement['status']), outcome=agreement['outcome_status']))
                elif verb == 'actions' and self.session:
                    target=self.reference(value) if value else focus
                    self.act(contract_id=target if target in self.current().get_world()['agreements'] else None)
                elif verb == 'list':
                    focus = None
                elif verb == 'inbox':
                    self.inbox()
                elif verb == 'help':
                    from .commands import menu
                    for item in menu('explorer'):
                        if item.name in {'open','history','past','actions','contracts','list','inbox','back'}:
                            self.write(item.name+' '+item.grammar+' / '+item.help)
                elif verb in {'back','quit'}:
                    return
                else:
                    self.write(t('laboratory.graph.choose_a_listed_command_exploration'))
            except (ValueError, Cancelled) as error:
                self.write(t('feedback.unavailable_prefix') + error_message(error))

    def inbox(self):
        if not self.session:
            self.write(t('laboratory.inbox.choose_a_simulated_player_with')); return
        while True:
            self.write(t('laboratory.inbox.contract_inbox_simulation') + self.session.actor)
            items = self.session.inbox(localized=True)
            for item in items:
                self.write(f"{item['contract_id']} / {item['label']} / " + '; '.join(item['reasons']))
            if not items:
                self.write(t('laboratory.inbox.no_contracts_currently_require_your'))
            raw = self.read(t('laboratory.inbox.open_id_act_id_b'))
            verb, _, target = raw.partition(' ')
            if verb in {'b', 'q', '0'}:
                return
            try:
                if verb == 'open':
                    self.inspect_node(target)
                elif verb == 'act' and any(item['contract_id'] == target for item in items):
                    self.act(contract_id=target)
                else:
                    self.write(t('laboratory.inbox.choose_an_inbox_contract_and'))
            except (ValueError, Cancelled) as error:
                self.write(t('feedback.unavailable_prefix') + error_message(error))

    def bind_identity(self, subject):
        self.identity = self.provider.sign_in(subject)
        bindings = [b for b in self.provider.bindings(self.identity)
                    if self.current().get_world()['actors'].get(b.actor_id, {}).get('status') == 'active']
        if not bindings:
            self.write(t('laboratory.bind_identity.no_verified_simulation_binding_exploration'))
            return False
        binding = bindings[0] if len(bindings) == 1 else self.choose(t('laboratory.bind_identity.choose_an_explicitly_granted_simulation'), bindings, lambda b: b.actor_id)
        self.session = ActorSession(self.game, binding.actor_id, store=self.store,
                                   identity=self.identity, binding=binding, provider=self.provider)
        self.profile()
        return True

    def profile(self):
        if self.identity is None:
            self.write(t('laboratory.profile.local_simulated_role_no_authenticated')); return
        self.write(t('laboratory.profile.identity_simulation_only_mock_player', label=self.identity.label, subject=self.identity.subject))
        self.write(t('laboratory.profile.authenticated_no_binding_status') + (t('laboratory.profile.verified_in_mock_only') if self.session else t('status.unverified')))
        if self.session:
            self.inspect_node(self.session.actor)

    def claim(self):
        from .identity import request_binding
        if self.identity is None:
            self.write(t('laboratory.claim.select_a_mock_player_before')); return
        actor_id = self.ask(t('laboratory.claim.existing_actor_id_enter_new'))
        profile_label = self.ask(t('laboratory.claim.proposed_profile_label')) if actor_id == 'new' else None
        operation = lambda game: request_binding(game, self.identity,
                                  actor_id=None if actor_id == 'new' else actor_id, profile_label=profile_label)
        result = self.store.transact(operation) if self.store else operation(self.game)
        self.write(t('laboratory.claim.pending_claim') + result['request']['id'] + t('laboratory.claim.no_acceptance_or_organisational_authority'))

    def onboarding(self):
        while True:
            self.write(t('laboratory.onboarding.welcome_to_saddle_pathways_1'))
            choice = self.read().lower()
            try:
                if choice == '1':
                    self.graph()
                elif choice == '2':
                    if not self.provider:
                        self.write(t('laboratory.onboarding.local_role_selection_simulation_only')); self.select_actor(); return True
                    subject = self.choose(t('laboratory.onboarding.simulate_sign_in_no_real'), list(self.provider.players) + ['+new'],
                                          lambda key: t('laboratory.onboarding.new_unbound_mock_player') if key == '+new' else self.provider.players[key]['label'] + ' / ' + key)
                    if subject == '+new':
                        self.identity = self.provider.register_guest(self.ask(t('laboratory.onboarding.new_mock_subject_id')), self.ask(t('laboratory.onboarding.mock_player_label')))
                        self.write(t('laboratory.onboarding.unbound_mock_player_request_an')); continue
                    if self.bind_identity(subject):
                        return True
                elif choice == '3':
                    self.write(t('laboratory.onboarding.real_play_requires_a_production'))
                elif choice == 'c':
                    self.claim()
                elif choice in {'q', '0'}:
                    return False
                else:
                    self.write(t('laboratory.onboarding.being_represented_is_not_authentication'))
            except (ValueError, Cancelled) as error:
                self.write(t('feedback.unavailable_prefix') + error_message(error))

    def inspect_mode(self, mode):
        game = self.current()
        world = game.get_world()
        self.write(t('laboratory.inspect_mode.saddle_pathways') + mode.upper())
        if mode == 'ecosystem':
            for actor in world['actors'].values():
                self.write(t('laboratory.inspect_mode.actor', id=actor['id'], label=display_label(actor), kind=actor['kind']))
            for table in ('relationships', 'capacities', 'needs'):
                self.write(table.upper())
                for record in world[table].values():
                    self.write(json.dumps(record, ensure_ascii=False))
            for possibility in game.derive_possibilities():
                self.write(t('laboratory.inspect_mode.inferred_possibility_not_an_agreement') + json.dumps(possibility))
            self.write(t('laboratory.inspect_mode.contract_nodes'))
            for node in game.project('network')['nodes']:
                if node['kind'] == 'agreement':
                    self.write(t('laboratory.graph.contract_summary', id=node['id'], label=display_label(node), status=status_label(node['status']), outcome=node['outcome_status']))
        elif mode == 'gathering':
            self.write(t('laboratory.inspect_mode.unresolved_conditions_declared_objectives'))
            for objective in world['objectives'].values():
                self.write(t('laboratory.inspect_mode.objective', label=objective['label'], status=objective['status'], supports=objective['support_ids']))
            for resource in world['resources'].values():
                held = sum(r['quantity'] for r in world['reservations'].values()
                           if r['resource_id'] == resource['id'] and r['status'] == 'held')
                self.write(t('laboratory.inspect_mode.resource_reserved', label=resource['label'], held=held, quantity=resource['quantity'], unit=resource['unit']))
            for commitment in world['commitments'].values():
                self.write(t('laboratory.inspect_mode.commitment', actor=commitment['actor_id'], responsibility=commitment['responsibility'], status=commitment['status']))
            for invitation in world['relationships'].values():
                if invitation['kind'] == 'invited':
                    self.write(t('laboratory.inspect_mode.invitation', id=invitation['id'], sender=invitation['source_id'], recipient=invitation['target_id'], status=invitation['status']))
            self.write(t('laboratory.inspect_mode.contract_backed_hube_feasibility_remains'))
        else:
            agreements = list(world['agreements'].values())
            if not agreements:
                self.write(t('laboratory.inspect_mode.no_contracts_yet_an_inferred'))
            for agreement in agreements:
                self.inspect_contract(agreement)
                for eid in agreement['evidence_ids']:
                    item = world['evidence'][eid]
                    self.write(t('laboratory.inspect_mode.evidence', id=eid, kind=item['kind'], actor=item['submitted_by'], reference=item['reference']))
        self.write(t('laboratory.inspect_mode.a_available_actions_g_world'))
        if mode == 'ecosystem':
            self.write(t('laboratory.inspect_mode.d_declare_a_capacity_need'))
        if mode == 'gathering':
            self.write(t('laboratory.inspect_mode.i_invite_r_respond_to'))

    def positive(self, value):
        number = int(value)
        if number < 1:
            raise ValueError
        return number

    def collect_action(self, candidate, game):
        kind = candidate['kind']
        world = game.get_world()
        if kind == 'propose':
            proposal = world['configuration']['world']['proposal']
            if proposal is None:
                target = self.choose(t('laboratory.collect_action.choose_another_actor_representation_simulation'),
                    [a for a in world['actors'].values() if a['id'] != self.session.actor and a['status'] == 'active'],
                    lambda a: display_label(a) + ' / ' + a['id'])
                objective = self.choose(t('laboratory.collect_action.choose_an_objective'), list(world['objectives'].values()), lambda o: o['label'])
                parties = [self.session.actor, target['id']]
                proposal = {'id': f'contract-{len(world["agreements"]) + 1:04}',
                    'label': self.ask(t('laboratory.collect_action.contract_title'), default='Simulated Montréal Commons collaboration'),
                    'parties': parties, 'objective_id': objective['id'],
                    'terms': {'purpose': objective['label'], 'conditions': ['Simulation only; no real-world consent or obligation.'],
                        'responsibilities': [{'actor_id': p, 'description': self.ask('Proposed responsibility for ' + display_label(world['actors'][p]) + '?')}
                                             for p in parties]},
                    'resources': [], 'valid_until': self.ask(t('laboratory.collect_action.valid_until_iso_timestamp'), default='2026-12-01T00:00:00+00:00'),
                    'policy_id': 'simulation-personal',
                    'verification': {'verifier_ids': ['simulation-verifier'], 'independent': True,
                                     'criteria': ['Agreed responsibilities independently reviewed against supplied evidence']}}
            payload = {'kind': kind, **deepcopy(proposal)}
            version = payload
        else:
            payload = deepcopy(candidate)
            agreement = world['agreements'][payload['agreement_id']]
            self.inspect_contract(agreement)
            version = agreement['versions'][agreement['current_version'] - 1]
        if kind in {'propose', 'amend'}:
            terms = deepcopy(version['terms'])
            terms['purpose'] = self.ask(t('laboratory.collect_action.purpose'), default=terms['purpose'])
            raw = self.ask(t('laboratory.collect_action.conditions_separated_by'), default=' | '.join(terms['conditions']))
            terms['conditions'] = [item.strip() for item in raw.split('|') if item.strip()]
            payload['terms'] = terms
            payload['resources'] = deepcopy(version['resources'])
            for resource in payload['resources']:
                resource['quantity'] = self.ask(t('laboratory.collect_action.quantity_for', resource_id=resource['resource_id']), default=str(resource['quantity']), parse=self.positive)
            self.write(json.dumps(payload, indent=2, ensure_ascii=False))
        if kind in {'initiate', 'fulfill', 'verify'}:
            if kind == 'fulfill':
                for criterion in version['verification']['criteria']:
                    if not self.confirm(t('laboratory.collect_action.does_your_report_address') + criterion + '?'):
                        raise Cancelled
                payload['criteria'] = deepcopy(version['verification']['criteria'])
            payload['reference'] = self.ask(t('laboratory.collect_action.evidence_reference_or_concrete_action'))
        if kind in {'reject', 'withdraw', 'suspend', 'terminate', 'dispute'}:
            payload['reason'] = self.ask(t('forms.reason_question'))
        self.write(t('laboratory.collect_action.acting_as_acceptance_authorisation_execution', actor=self.session.actor))
        if not self.confirm(t('laboratory.collect_action.submit_this_action')):
            raise Cancelled
        return payload

    def submit(self, payload, version):
        result = self.session.submit(payload, expected_version=version)
        if result['ok']:
            self.write(t('laboratory.submit.committed_state', commit_id=result['commit_id'], state_version=result['state_version']))
            self.write(t('laboratory.submit.simulated_action_no_real_world'))
            contract_id = payload.get('agreement_id') or (payload.get('id') if payload['kind'] in {'propose', 'draft'} else None)
            if contract_id:
                self.last_contract = contract_id
                self.write(t('laboratory.submit.contract_o_open_contract_g', contract_id=contract_id))
        else:
            self.write(t('feedback.rejected', errors=error_list(result['errors'])))
        return result

    def act(self, contract_id=None):
        version, candidates = self.session.available_actions()
        if contract_id:
            candidates = [c for c in candidates if c.get('agreement_id') == contract_id]
        if not candidates:
            self.write(t('laboratory.act.no_actions_are_permitted_for'));return
        candidate = self.choose(t('laboratory.act.available_actions_for') + self.session.actor + ':', candidates,
                                lambda c: action_name(c['kind']) + (' / ' + c['agreement_id'] if c.get('agreement_id') else ''))
        payload = self.collect_action(candidate, self.current())
        self.submit(payload, version)

    def declare(self):
        game = self.current()
        version = len(game.project('log'))
        table = self.choose(t('laboratory.declare.what_do_you_want_to'), ['capacities', 'needs', 'relationships'])
        if table == 'relationships':
            world = game.get_world()
            target = self.choose(t('laboratory.declare.whom_do_you_know'), list(world['actors'].values()), lambda a: display_label(a))
            record = {'source_id': self.session.actor, 'target_id': target['id'], 'kind': 'knows',
                      'note': self.ask(t('laboratory.declare.source_or_note_for_your'))}
        else:
            record = {'domain': self.ask(t('laboratory.declare.domain')), 'quantity': self.ask(t('laboratory.declare.quantity'), parse=self.positive),
                      'unit': self.ask(t('laboratory.declare.unit'))}
        if self.confirm(t('laboratory.declare.record_this_as_a_declaration')):
            self.submit({'kind': 'declare', 'table': table, 'record': record}, version)

    def invitation(self, respond=False):
        game = self.current()
        world = game.get_world()
        version = len(game.project('log'))
        if not self.session:
            self.write(t('laboratory.invitation.select_a_simulated_actor_before'));return
        if respond:
            pending = [r for r in world['relationships'].values() if r['kind'] == 'invited'
                       and r['target_id'] == self.session.actor and r['status'] == 'proposed']
            if not pending:
                self.write(t('laboratory.invitation.respond_no_pending_invitations_require'));return
            item = self.choose(t('laboratory.invitation.your_pending_invitations'), pending, lambda r: r['id'] + ' from ' + r['source_id'])
            response = self.choose(t('laboratory.invitation.response'), ['accept', 'decline'])
            payload = {'kind': 'respond_invitation', 'invitation_id': item['id'], 'response': response}
        else:
            if not any(o['mode']=='gathering' for o in world['objectives'].values()):
                self.write(t('laboratory.invitation.invite_not_available_in_this'));return
            objective = self.choose(t('laboratory.invitation.gathering_objective'), [o for o in world['objectives'].values() if o['mode'] == 'gathering'], lambda o: o['label'])
            recipient = self.choose(t('laboratory.invitation.invite_whom'), [a for a in world['actors'].values() if a['id'] != self.session.actor], lambda a: display_label(a))
            payload = {'kind': 'invite', 'recipient_id': recipient['id'], 'objective_id': objective['id']}
        if self.confirm(t('laboratory.invitation.submit_this_invitation_action')):
            self.submit(payload, version)

    def mode(self, name):
        while True:
            self.inspect_mode(name)
            choice = self.read().lower()
            aliases={'available actions':'a','actions':'a','invite':'invite','respond':'respond',
                     'open latest contract':'latest','contract history':'contract-history','?':'help'}
            choice=aliases.get(choice,choice)
            if choice in {'b', '0', 'q'}:
                return
            try:
                if choice == 'a':
                    self.act()
                elif choice=='invite':
                    self.invitation()
                elif choice=='respond':
                    self.invitation(respond=True)
                elif choice=='latest':
                    self.inspect_node(self.reference('latest contract',contracts_only=True))
                elif choice=='contract-history':
                    self.node_history(self.reference(contracts_only=True))
                elif choice=='help':
                    self.write(t('laboratory.mode.a_engine_permitted_actions_g'))
                elif choice == 'g':
                    self.graph(self.last_contract)
                elif choice == 'o' and self.last_contract:
                    self.inspect_node(self.last_contract)
                elif choice == 'h' and self.last_contract:
                    self.node_history(self.last_contract)
                elif choice == 'n':
                    self.inbox()
                elif choice == 'w':
                    self.write(json.dumps(display_world(self.current().get_world()), indent=2, ensure_ascii=False))
                elif choice == 'd' and name == 'ecosystem':
                    self.declare()
                elif choice in {'i', 'r'} and name == 'gathering':
                    self.invitation(respond=choice == 'r')
                else:
                    self.write(t('laboratory.mode.choose_one_of_the_listed'))
            except Cancelled:
                self.write(t('laboratory.mode.cancelled_no_incomplete_action_was'))

    def history(self):
        from .trajectory import project_trajectory, simulate_branch, trajectory_yaml
        while True:
            game = self.current()
            self.write(t('laboratory.history.history_trajectories'))
            self.write(t('laboratory.history.h_history_t_current_trajectory'))
            self.write(t('laboratory.history.v_inspect_branches_e_export'))
            choice = self.read().lower()
            if choice in {'b', '0', 'q'}:
                return
            try:
                if choice == 'h':
                    for entry in game.project('log'):
                        self.write(f"{entry['sequence']:03} {entry['id']} {entry['kind']} / {entry['actor_id']} / {entry['occurred_at']}")
                elif choice == 'r':
                    self.write(t('laboratory.history.replay_consistent') + str(game.replay().get_world() == game.get_world()))
                elif choice == 'p':
                    seq = self.ask(t('laboratory.history.state_transaction_number'), parse=self.positive)
                    self.write(json.dumps(display_world(game.world_at(event=seq)), indent=2, ensure_ascii=False))
                elif choice == 's':
                    seq = self.ask(t('laboratory.history.branch_from_which_transaction'), parse=self.positive)
                    fork = type(game).from_log(game.project('log')[:seq]) if seq <= len(game.project('log')) else None
                    if fork is None:
                        raise ValueError('invalid_event')
                    temporary = ActorSession(fork, self.session.actor)
                    _, candidates = temporary.available_actions()
                    candidate = self.choose(t('laboratory.history.hypothetical_action_for_your_current'), candidates, lambda c: action_name(c['kind']))
                    payload = self.collect_action(candidate, fork)
                    payload.update(actor=self.session.actor, key='hypothetical-' + uuid4().hex)
                    branch = simulate_branch(game, parent_sequence=seq, commands=[payload],
                                             branch_id=f'branch-{len(self.branches) + 1:03}')
                    self.branches.append(branch)
                    self.write(t('laboratory.history.hypothetical_only_authoritative_history_unchanged'))
                    render_trajectory(project_trajectory(game, branches=self.branches), self.output, branch_id=branch['id'])
                elif choice == 'v':
                    branch = self.choose(t('laboratory.history.hypothetical_branches'), self.branches, lambda b: b['id'] + ' from ' + b['parent_commit_id'])
                    render_trajectory(project_trajectory(game, branches=self.branches), self.output, branch_id=branch['id'])
                elif choice == 'e':
                    path = Path(self.ask(t('laboratory.history.export_path_existing_files_are'))).expanduser()
                    data = trajectory_yaml(project_trajectory(game, branches=self.branches))
                    with path.open('x') as target:
                        target.write(data)
                    self.write(t('laboratory.history.exported_read_only_trajectory') + str(path))
                elif choice == 't':
                    render_trajectory(project_trajectory(game, branches=self.branches), self.output)
                else:
                    self.write(t('laboratory.mode.choose_one_of_the_listed'))
            except Cancelled:
                self.write(t('laboratory.history.cancelled'))
            except (ValueError, RuntimeError, OSError) as error:
                self.write(t('laboratory.history.inspection_unavailable') + error_message(error))

    def run(self):
        self.write('╔══════════════════════════════════════════════╗')
        self.write('║'+t('branding.title').center(46)+'║')
        self.write('║'+t('branding.game_name').center(46)+'║')
        self.write('║' + t('branding.declaration').center(46) + '║')
        self.write('╚══════════════════════════════════════════════╝')
        self.write(t('laboratory.run.a_central_authoritative_engine_enforcing'))
        self.write(t('laboratory.run.local_simulation_selecting_an_identity'))
        if self.hot_seat:
            self.write(t('laboratory.run.explicit_development_hot_seat_enabled'))
        try:
            if self.explore:
                self.graph(); return self.current()
            if self.identity is not None:
                if not self.bind_identity(self.identity.subject) and not self.onboarding():
                    return self.current()
            elif self.session is None:
                if not self.onboarding():
                    return self.current()
            while True:
                game = self.current()
                config = game.get_world()['configuration']['world']
                context = t('laboratory.run.synthetic_simulation') if config.get('synthetic') else t('laboratory.run.empirical_ecosystem_simulation_only')
                self.write(t('laboratory.run.world_actor_state', title=config['title'], context=context, actor=self.session.actor, value_count=len(game.project('log'))))
                self.write(t('laboratory.run.shortcut_1_ecosystem_we_can_act'))
                self.write(t('laboratory.run.shortcut_2_gathering_we_make_it'))
                self.write(t('laboratory.run.shortcut_3_scenarios_what_can_we'))
                self.write(t('laboratory.run.shortcut_4_history_trajectories_5_help'))
                self.write(t('laboratory.run.g_world_graph_n_contract'))
                if self.hot_seat:
                    self.write(t('laboratory.run.s_switch_local_actor_explicit'))
                choice = self.read().lower()
                try:
                    if choice in {'q', '0'}:
                        break
                    if choice in {'1', '2', '3'}:
                        self.mode({'1': 'ecosystem', '2': 'gathering', '3': 'scenarios'}[choice])
                    elif choice == '4':
                        self.history()
                    elif choice == 'g':
                        self.graph()
                    elif choice == 'n':
                        self.inbox()
                    elif choice == 'p':
                        self.profile()
                    elif choice == 'c':
                        self.claim()
                    elif choice == 'x':
                        self.session = None; self.identity = None; self.last_contract = None
                        self.write(t('laboratory.run.signed_out_the_authoritative_world'))
                        if not self.onboarding():
                            break
                    elif choice == 's' and self.hot_seat:
                        self.select_actor()
                    elif choice in {'5', '?'}:
                        self.write(t('laboratory.run.inspect_choose_a_valid_action'))
                        self.write(t('laboratory.run.b_back_0_cancel_a'))
                        self.write(t('laboratory.run.commitment_commit_acceptance_institutional_authorisation'))
                        self.write(t('laboratory.run.normal_play_stays_bound_to'))
                    else:
                        self.write(t('laboratory.run.choose_one_of_the_listed'))
                except Cancelled:
                    self.write(t('laboratory.mode.cancelled_no_incomplete_action_was'))
                except ValueError as error:
                    self.write(t('laboratory.run.action_unavailable') + error_message(error))
        except (EOFError, Cancelled):
            pass
        self.write(t('session.closed'))
        return self.current()


def run_play(game, **options):
    return Terminal(game, **options).run()
