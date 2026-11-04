"""Terminal-first laboratory. Forms produce commands; the engine owns decisions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import shutil
import textwrap
from uuid import uuid4

from .player import ActorSession
from .presentation import display_label, display_world

ACTION_NAMES = {
    'draft_contact': 'Save invitation draft', 'send_contact': 'Invite to connect',
    'publish_contact': 'Send drafted invitation', 'respond_contact': 'Respond to invitation',
    'withdraw_contact': 'Withdraw invitation',
    'publish_proposal': 'Publish a drafted contract',
    'propose': 'Propose a contract', 'amend': 'Negotiate revised terms',
    'accept': 'Accept this exact version', 'authorize': 'Record institutional authorisation',
    'activate': 'Activate and reserve resources', 'initiate': 'Record a concrete action',
    'fulfill': 'Report fulfilment with evidence', 'verify': 'Independently verify the outcome',
    'reject': 'Reject the proposal', 'withdraw': 'Withdraw before activation',
    'suspend': 'Suspend the active contract', 'resume': 'Resume the contract',
    'terminate': 'Terminate and release reservations', 'dispute': 'Record a dispute',
}
EVENT_NAMES = {
    'invitation.drafted': 'Invitation drafted', 'invitation.sent': 'Invitation sent',
    'invitation.accepted': 'Invitation accepted; connection acknowledged',
    'invitation.declined': 'Invitation declined', 'invitation.withdrawn': 'Invitation withdrawn',
    'draft_contact': 'Invitation drafted', 'send_contact': 'Invitation sent',
    'publish_contact': 'Draft invitation sent', 'respond_contact': 'Invitation response recorded',
    'withdraw_contact': 'Invitation withdrawn',
    'ecosystem.imported': 'Source ecosystem captured and imported',
    'publish_proposal': 'Draft published as a proposal',
    'initialize': 'World initialised', 'draft': 'Contract drafted',
    'propose': 'Contract proposed', 'amend': 'Conditions negotiated',
    'accept': 'Party acceptance recorded', 'authorize': 'Institutional authorisation recorded',
    'activate': 'Resources reserved; obligations active', 'initiate': 'Execution recorded',
    'fulfill': 'Fulfilment reported', 'verify': 'Outcome independently verified',
    'reject': 'Proposal rejected', 'withdraw': 'Contract withdrawn',
    'suspend': 'Contract suspended', 'resume': 'Contract resumed',
    'terminate': 'Contract terminated', 'dispute': 'Dispute recorded',
}


class Cancelled(Exception):
    pass


def display(value):
    """Player-authored text is text, never terminal control or executable code."""
    return ''.join(char for char in str(value) if char.isprintable() or char in '\n\t')


def status_label(value):
    return {'authorized': 'authorised'}.get(value, value)


def render_trajectory(document, output, *, branch_id=None):
    from .trajectory import frames
    envelope = document['plan']['commons_trajectory']
    output.write('SADDLE PATHWAYS / TRAJECTORY\n')
    output.write(f"World: {envelope['provenance']['scenario']}\n")
    output.write(f"Context: {envelope['provenance']['world_kind']} / "
                 f"{'HYPOTHETICAL BRANCH ' + branch_id if branch_id else 'RECORDED HISTORY'}\n")
    last = 0
    for frame in frames(document, branch_id=branch_id):
        last = frame['sequence']
        label = EVENT_NAMES.get(frame['kind'], frame['kind'])
        output.write(f"STATE {last:03} [{frame['history_kind']}] {display(label)}\n")
        output.write(f"  actor={display(frame['actor_id'])} event={frame['event_id']} commit={frame['commit_id']}\n")
        for agreement in frame['agreements']:
            output.write(f"  {display(agreement['id'])} v{agreement['current_version']}: "
                         f"{status_label(agreement['status'])} / outcome={agreement['outcome_status']}\n")
    output.write(f'CURRENT STATE: {last:03}\nNo geometric coordinates or physical quantities inferred.\n')


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
                self.write('0 / b: cancel this form. Invalid input repeats this question. No partial writes.')
                continue
            value = default if not raw and default is not None else raw
            try:
                if parse:
                    return parse(value)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError
                return value.strip()
            except (ValueError, TypeError):
                self.write('Invalid input; please try again.')

    def choose(self, prompt, items, label=str):
        if not items:
            self.write('No available choices.')
            raise Cancelled
        self.write(prompt)
        for index, item in enumerate(items, 1):
            self.write(f'[{index}] {label(item)}')
        def selected(value):
            number = int(value)
            if not 1 <= number <= len(items):
                raise ValueError
            return items[number - 1]
        return self.ask('Choice? 0 cancels.', parse=selected)

    def confirm(self, prompt):
        def yes_no(value):
            if value.lower() not in {'y', 'yes', 'n', 'no'}:
                raise ValueError
            return value.lower() in {'y', 'yes'}
        return self.ask(prompt + ' y/N', default='n', parse=yes_no)

    def select_actor(self):
        actors = [a for a in self.current().project('actors') if a['status'] == 'active']
        selected = self.choose('Select your local actor identity:', actors, lambda a: display_label(a))
        if self.session:
            self.session.switch(selected['id'])
        else:
            self.session = ActorSession(self.game, selected['id'], store=self.store, hot_seat=self.hot_seat)
        self.write(f"ACTOR: {display_label(selected)} ({selected['id']})")

    def inspect_contract(self, agreement):
        version = agreement['versions'][agreement['current_version'] - 1]
        self.write(f"CONTRACT {agreement['id']} / VERSION {version['number']} / {status_label(agreement['status'])}")
        self.write(f"Outcome: {agreement['outcome_status']} / content digest: {version['content_digest']}")
        self.write('Parties: ' + ', '.join(agreement['parties']))
        self.write('Purpose: ' + version['terms']['purpose'])
        for obligation in version['terms']['responsibilities']:
            self.write(f"  Obligation / {obligation['actor_id']}: {obligation['description']}")
        for condition in version['terms']['conditions']:
            self.write('  Condition: ' + condition)
        self.write('Accepted by: ' + (', '.join(version['acceptances']) or 'nobody'))
        self.write('Authorised by: ' + (', '.join(version['authorizations']) or 'nobody'))
        self.write('Designated independent verifier(s): ' + ', '.join(version['verification']['verifier_ids']))
        self.write('Requested resources: ' + json.dumps(version['resources']))
        self.write('Valid until: ' + version['valid_until'])
        world = self.current().get_world()
        policy = world['governance'][version['policy_id']]
        self.write('Authorisation policy: ' + policy['label'])
        self.write('Required approvers: ' + (', '.join(policy['required_actors']) or 'none')
                   + f" / threshold: {policy['threshold']} / categories: {', '.join(policy['required_categories']) or 'none'}")
        for eid in agreement['evidence_ids']:
            self.write('EVIDENCE ' + json.dumps(world['evidence'][eid], ensure_ascii=False))
        if self.session:
            _, actions = self.session.available_actions()
            names = [ACTION_NAMES[a['kind']] for a in actions if a.get('agreement_id') == agreement['id']]
            self.write('Your available actions: ' + ('; '.join(names) or 'none'))

    def inspect_node(self, node_id, *, at=None):
        from .projections import neighbourhood
        game = self.current()
        graph = neighbourhood(game.project('network', at=at), node_id)
        node = next(n for n in graph['nodes'] if n['id'] == node_id)
        self.write(f"NODE {node_id} / {node['kind']} / {display_label(node)}")
        if node['kind'] == 'agreement' and at is None:
            self.inspect_contract(node)
        else:
            self.write(json.dumps({**node, 'label': display_label(node)}, ensure_ascii=False, indent=2))
        self.write('NEIGHBOURHOOD' + (f' / HISTORICAL STATE {at}' if at else ' / CURRENT WORLD'))
        for edge in graph['edges']:
            arrow = '-->'
            if 'directed' in edge:
                arrow = '-->' if edge['directed'] is True else '--' if edge['directed'] is False else '-- [direction unknown] '
            self.write(f"{edge['source_id']} --{edge['kind']}{arrow} {edge['target_id']}")
        self.write('Linked nodes: ' + ', '.join(n['id'] for n in graph['nodes'] if n['id'] != node_id))

    def node_history(self, node_id):
        game = self.current()
        events = [e for e in game.project('log') if any(m['entity_id'] == node_id for m in e['mutations'])]
        for event in events:
            self.write(f"{event['sequence']:03} {event['id']} / {event['commit']['id']} / {event['kind']} / {event['actor_id']}")
        if events:
            self.write('CREATION / HISTORICAL GRAPH')
            self.inspect_node(node_id, at=events[0]['sequence'])
        self.write('Return to the current world with: open ' + node_id)

    def reference(self, value='', *, contracts_only=False):
        from .commands import resolve
        world=self.current().get_world()
        found=resolve(world,value)
        if found and (not contracts_only or found in world['agreements']):
            return found
        nodes=self.current().project('network')['nodes']
        if contracts_only:nodes=[n for n in nodes if n['kind']=='agreement']
        return self.choose('Choose an object:',nodes,display_label)['id']

    def graph(self, focus=None):
        from collections import Counter
        while True:
            graph = self.current().project('network')
            self.write('\nWORLD GRAPH / ' + self.current().get_world()['configuration']['world']['title'])
            self.write(' / '.join(f'{kind}: {count}' for kind, count in Counter(n['kind'] for n in graph['nodes']).items()))
            if focus:
                self.inspect_node(focus)
            else:
                for node in graph['nodes']:
                    self.write(f"{node['id']} / {node['kind']} / {display_label(node)} / {status_label(node.get('status', 'unknown'))}"
                               + (f" / outcome={node['outcome_status']}" if 'outcome_status' in node else ''))
            self.write('open ID | history ID | past SEQUENCE ID | contracts [actor=ID status=STATE objective=ID resource=ID] | act ID | list | b Back')
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
                        entry=self.choose('Choose a historical state:',entries,lambda e:f"State {e['sequence']} / {e['kind']}")
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
                        self.write(f"{agreement['id']} / {agreement['label']} / {status_label(agreement['status'])} / outcome={agreement['outcome_status']}")
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
                    self.write('Choose a listed command. Exploration does not grant authority.')
            except (ValueError, Cancelled) as error:
                self.write('Unavailable: ' + str(error))

    def inbox(self):
        if not self.session:
            self.write('Choose a simulated player with an explicit actor binding to open an inbox.'); return
        while True:
            self.write('\nCONTRACT INBOX / SIMULATION / ' + self.session.actor)
            items = self.session.inbox()
            for item in items:
                self.write(f"{item['contract_id']} / {item['label']} / " + '; '.join(item['reasons']))
            if not items:
                self.write('No contracts currently require your response.')
            raw = self.read('open ID | act ID | b Back')
            verb, _, target = raw.partition(' ')
            if verb in {'b', 'q', '0'}:
                return
            try:
                if verb == 'open':
                    self.inspect_node(target)
                elif verb == 'act' and any(item['contract_id'] == target for item in items):
                    self.act(contract_id=target)
                else:
                    self.write('Choose an inbox contract and a listed command.')
            except (ValueError, Cancelled) as error:
                self.write('Unavailable: ' + str(error))

    def bind_identity(self, subject):
        self.identity = self.provider.sign_in(subject)
        bindings = [b for b in self.provider.bindings(self.identity)
                    if self.current().get_world()['actors'].get(b.actor_id, {}).get('status') == 'active']
        if not bindings:
            self.write('No verified simulation binding. Exploration and pending claims remain available.')
            return False
        binding = bindings[0] if len(bindings) == 1 else self.choose('Choose an explicitly granted simulation role:', bindings, lambda b: b.actor_id)
        self.session = ActorSession(self.game, binding.actor_id, store=self.store,
                                   identity=self.identity, binding=binding, provider=self.provider)
        self.profile()
        return True

    def profile(self):
        if self.identity is None:
            self.write('Local simulated role; no authenticated player identity.'); return
        self.write(f'IDENTITY / SIMULATION ONLY\nMock player: {self.identity.label} / subject: {self.identity.subject}')
        self.write('Authenticated: no. Binding status: ' + ('VERIFIED IN MOCK ONLY' if self.session else 'UNVERIFIED'))
        if self.session:
            self.inspect_node(self.session.actor)

    def claim(self):
        from .identity import request_binding
        if self.identity is None:
            self.write('Select a mock player before requesting a binding.'); return
        actor_id = self.ask('Existing actor ID? Enter new to request a new profile.')
        profile_label = self.ask('Proposed profile label?') if actor_id == 'new' else None
        operation = lambda game: request_binding(game, self.identity,
                                  actor_id=None if actor_id == 'new' else actor_id, profile_label=profile_label)
        result = self.store.transact(operation) if self.store else operation(self.game)
        self.write('PENDING CLAIM ' + result['request']['id'] + '. No acceptance or organisational authority granted.')

    def onboarding(self):
        while True:
            self.write('\nWelcome to SADDLE PATHWAYS.\n[1] Explore the ecosystem\n[2] Enter simulation mode\n[4] Help\n[c] Request an actor binding\n[q] Quit')
            choice = self.read().lower()
            try:
                if choice == '1':
                    self.graph()
                elif choice == '2':
                    if not self.provider:
                        self.write('Local role selection / SIMULATION ONLY.'); self.select_actor(); return True
                    subject = self.choose('Simulate sign-in (no real authentication):', list(self.provider.players) + ['+new'],
                                          lambda key: 'New unbound mock player' if key == '+new' else self.provider.players[key]['label'] + ' / ' + key)
                    if subject == '+new':
                        self.identity = self.provider.register_guest(self.ask('New mock subject ID?'), self.ask('Mock player label?'))
                        self.write('Unbound mock player. Request an existing actor or a new profile with c.'); continue
                    if self.bind_identity(subject):
                        return True
                elif choice == '3':
                    self.write('Real play requires a production identity provider and verified authority. All current actions are simulated.')
                elif choice == 'c':
                    self.claim()
                elif choice in {'q', '0'}:
                    return False
                else:
                    self.write('Being represented is not authentication, authorisation or consent. Claims remain pending until independently reviewed.')
            except (ValueError, Cancelled) as error:
                self.write('Unavailable: ' + str(error))

    def inspect_mode(self, mode):
        game = self.current()
        world = game.get_world()
        self.write('\nSADDLE PATHWAYS / ' + mode.upper())
        if mode == 'ecosystem':
            for actor in world['actors'].values():
                self.write(f"ACTOR {actor['id']}: {display_label(actor)} / {actor['kind']}")
            for table in ('relationships', 'capacities', 'needs'):
                self.write(table.upper())
                for record in world[table].values():
                    self.write(json.dumps(record, ensure_ascii=False))
            for possibility in game.derive_possibilities():
                self.write('INFERRED POSSIBILITY (not an agreement): ' + json.dumps(possibility))
            self.write('CONTRACT NODES')
            for node in game.project('network')['nodes']:
                if node['kind'] == 'agreement':
                    self.write(f"{node['id']} / {display_label(node)} / {status_label(node['status'])} / outcome={node['outcome_status']}")
        elif mode == 'gathering':
            self.write('UNRESOLVED CONDITIONS / DECLARED OBJECTIVES')
            for objective in world['objectives'].values():
                self.write(f"{objective['label']}: {objective['status']} / supports={objective['support_ids']}")
            for resource in world['resources'].values():
                held = sum(r['quantity'] for r in world['reservations'].values()
                           if r['resource_id'] == resource['id'] and r['status'] == 'held')
                self.write(f"RESOURCE {resource['label']}: {held}/{resource['quantity']} {resource['unit']} reserved")
            for commitment in world['commitments'].values():
                self.write(f"COMMITMENT {commitment['actor_id']}: {commitment['responsibility']} / {commitment['status']}")
            for invitation in world['relationships'].values():
                if invitation['kind'] == 'invited':
                    self.write(f"INVITATION {invitation['id']}: {invitation['source_id']} → {invitation['target_id']} / {invitation['status']}")
            self.write('Contract-backed Hube feasibility remains an M4 gate; this is the existing synthetic world.')
        else:
            agreements = list(world['agreements'].values())
            if not agreements:
                self.write('No contracts yet. An inferred possibility has not become an agreement.')
            for agreement in agreements:
                self.inspect_contract(agreement)
                for eid in agreement['evidence_ids']:
                    item = world['evidence'][eid]
                    self.write(f"EVIDENCE {eid}: {item['kind']} / {item['submitted_by']} / {item['reference']}")
        self.write('[a] Available actions  [g] World graph  [o] Open latest contract  [h] Latest contract history  [n] Inbox  [w] Full world  [b] Back')
        if mode == 'ecosystem':
            self.write('[d] Declare a capacity, need or relationship')
        if mode == 'gathering':
            self.write('[i] Invite  [r] Respond to an invitation')

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
                target = self.choose('Choose another actor representation (simulation only):',
                    [a for a in world['actors'].values() if a['id'] != self.session.actor and a['status'] == 'active'],
                    lambda a: display_label(a) + ' / ' + a['id'])
                objective = self.choose('Choose an objective:', list(world['objectives'].values()), lambda o: o['label'])
                parties = [self.session.actor, target['id']]
                proposal = {'id': f'contract-{len(world["agreements"]) + 1:04}',
                    'label': self.ask('Contract title?', default='Simulated Montréal Commons collaboration'),
                    'parties': parties, 'objective_id': objective['id'],
                    'terms': {'purpose': objective['label'], 'conditions': ['Simulation only; no real-world consent or obligation.'],
                        'responsibilities': [{'actor_id': p, 'description': self.ask('Proposed responsibility for ' + display_label(world['actors'][p]) + '?')}
                                             for p in parties]},
                    'resources': [], 'valid_until': self.ask('Valid until (ISO timestamp)?', default='2026-12-01T00:00:00+00:00'),
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
            terms['purpose'] = self.ask('Purpose?', default=terms['purpose'])
            raw = self.ask('Conditions, separated by |?', default=' | '.join(terms['conditions']))
            terms['conditions'] = [item.strip() for item in raw.split('|') if item.strip()]
            payload['terms'] = terms
            payload['resources'] = deepcopy(version['resources'])
            for resource in payload['resources']:
                resource['quantity'] = self.ask(f"Quantity for {resource['resource_id']}?", default=str(resource['quantity']), parse=self.positive)
            self.write(json.dumps(payload, indent=2, ensure_ascii=False))
        if kind in {'initiate', 'fulfill', 'verify'}:
            if kind == 'fulfill':
                for criterion in version['verification']['criteria']:
                    if not self.confirm('Does your report address: ' + criterion + '?'):
                        raise Cancelled
                payload['criteria'] = deepcopy(version['verification']['criteria'])
            payload['reference'] = self.ask('Evidence reference or concrete action note?')
        if kind in {'reject', 'withdraw', 'suspend', 'terminate', 'dispute'}:
            payload['reason'] = self.ask('Reason?')
        self.write(f"Acting as {self.session.actor}. "
                   'Acceptance, authorisation, execution and verification are different transitions.')
        if not self.confirm('Submit this action?'):
            raise Cancelled
        return payload

    def submit(self, payload, version):
        result = self.session.submit(payload, expected_version=version)
        if result['ok']:
            self.write(f"COMMITTED {result['commit_id']} / state {result['state_version']:03}")
            self.write('SIMULATED ACTION. No real-world consent or commitment recorded.')
            contract_id = payload.get('agreement_id') or (payload.get('id') if payload['kind'] in {'propose', 'draft'} else None)
            if contract_id:
                self.last_contract = contract_id
                self.write(f'CONTRACT {contract_id} / [o] Open contract / [g] View graph / [h] View history')
        else:
            self.write('REJECTED: ' + ', '.join(result['errors']) + '. No state changed.')
        return result

    def act(self, contract_id=None):
        version, candidates = self.session.available_actions()
        if contract_id:
            candidates = [c for c in candidates if c.get('agreement_id') == contract_id]
        if not candidates:
            self.write('No actions are permitted for this actor on the current contract state. Check parties, acceptance, authorisation and lifecycle conditions.');return
        candidate = self.choose('Available actions for ' + self.session.actor + ':', candidates,
                                lambda c: ACTION_NAMES[c['kind']] + (' / ' + c['agreement_id'] if c.get('agreement_id') else ''))
        payload = self.collect_action(candidate, self.current())
        self.submit(payload, version)

    def declare(self):
        game = self.current()
        version = len(game.project('log'))
        table = self.choose('What do you want to declare?', ['capacities', 'needs', 'relationships'])
        if table == 'relationships':
            world = game.get_world()
            target = self.choose('Whom do you know?', list(world['actors'].values()), lambda a: display_label(a))
            record = {'source_id': self.session.actor, 'target_id': target['id'], 'kind': 'knows',
                      'note': self.ask('Source or note for your report?')}
        else:
            record = {'domain': self.ask('Domain?'), 'quantity': self.ask('Quantity?', parse=self.positive),
                      'unit': self.ask('Unit?')}
        if self.confirm('Record this as a declaration, not a verified fact?'):
            self.submit({'kind': 'declare', 'table': table, 'record': record}, version)

    def invitation(self, respond=False):
        game = self.current()
        world = game.get_world()
        version = len(game.project('log'))
        if not self.session:
            self.write('Select a simulated actor before inviting or responding.');return
        if respond:
            pending = [r for r in world['relationships'].values() if r['kind'] == 'invited'
                       and r['target_id'] == self.session.actor and r['status'] == 'proposed']
            if not pending:
                self.write('RESPOND: No pending invitations require your response. Use the contract inbox for proposals.');return
            item = self.choose('Your pending invitations:', pending, lambda r: r['id'] + ' from ' + r['source_id'])
            response = self.choose('Response?', ['accept', 'decline'])
            payload = {'kind': 'respond_invitation', 'invitation_id': item['id'], 'response': response}
        else:
            if not any(o['mode']=='gathering' for o in world['objectives'].values()):
                self.write('INVITE: Not available in this scenario. The registered invitation action requires a gathering objective.');return
            objective = self.choose('Gathering objective?', [o for o in world['objectives'].values() if o['mode'] == 'gathering'], lambda o: o['label'])
            recipient = self.choose('Invite whom?', [a for a in world['actors'].values() if a['id'] != self.session.actor], lambda a: display_label(a))
            payload = {'kind': 'invite', 'recipient_id': recipient['id'], 'objective_id': objective['id']}
        if self.confirm('Submit this invitation action?'):
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
                    self.write('a: engine-permitted actions; g: graph; o: latest contract; h: latest contract history; n: inbox; invite/respond: gathering invitations when applicable; b: back.')
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
                    self.write('Choose one of the listed actions.')
            except Cancelled:
                self.write('Cancelled; no incomplete action was submitted.')

    def history(self):
        from .trajectory import project_trajectory, simulate_branch, trajectory_yaml
        while True:
            game = self.current()
            self.write('\nHISTORY & TRAJECTORIES')
            self.write('[h] History  [t] Current trajectory  [p] Past state  [s] Simulate branch')
            self.write('[v] Inspect branches  [e] Export package YAML  [r] Replay  [b] Back')
            choice = self.read().lower()
            if choice in {'b', '0', 'q'}:
                return
            try:
                if choice == 'h':
                    for entry in game.project('log'):
                        self.write(f"{entry['sequence']:03} {entry['id']} {entry['kind']} / {entry['actor_id']} / {entry['occurred_at']}")
                elif choice == 'r':
                    self.write('REPLAY CONSISTENT: ' + str(game.replay().get_world() == game.get_world()))
                elif choice == 'p':
                    seq = self.ask('State transaction number?', parse=self.positive)
                    self.write(json.dumps(display_world(game.world_at(event=seq)), indent=2, ensure_ascii=False))
                elif choice == 's':
                    seq = self.ask('Branch from which transaction?', parse=self.positive)
                    fork = type(game).from_log(game.project('log')[:seq]) if seq <= len(game.project('log')) else None
                    if fork is None:
                        raise ValueError('invalid_event')
                    temporary = ActorSession(fork, self.session.actor)
                    _, candidates = temporary.available_actions()
                    candidate = self.choose('Hypothetical action for your current actor:', candidates, lambda c: ACTION_NAMES[c['kind']])
                    payload = self.collect_action(candidate, fork)
                    payload.update(actor=self.session.actor, key='hypothetical-' + uuid4().hex)
                    branch = simulate_branch(game, parent_sequence=seq, commands=[payload],
                                             branch_id=f'branch-{len(self.branches) + 1:03}')
                    self.branches.append(branch)
                    self.write('HYPOTHETICAL ONLY. Authoritative history unchanged.')
                    render_trajectory(project_trajectory(game, branches=self.branches), self.output, branch_id=branch['id'])
                elif choice == 'v':
                    branch = self.choose('Hypothetical branches:', self.branches, lambda b: b['id'] + ' from ' + b['parent_commit_id'])
                    render_trajectory(project_trajectory(game, branches=self.branches), self.output, branch_id=branch['id'])
                elif choice == 'e':
                    path = Path(self.ask('Export path? Existing files are preserved.')).expanduser()
                    data = trajectory_yaml(project_trajectory(game, branches=self.branches))
                    with path.open('x') as target:
                        target.write(data)
                    self.write('Exported read-only trajectory: ' + str(path))
                elif choice == 't':
                    render_trajectory(project_trajectory(game, branches=self.branches), self.output)
                else:
                    self.write('Choose one of the listed actions.')
            except Cancelled:
                self.write('Cancelled.')
            except (ValueError, RuntimeError, OSError) as error:
                self.write('Inspection unavailable: ' + str(error))

    def run(self):
        self.write('╔══════════════════════════════════════════════╗')
        self.write('║               SADDLE PATHWAYS                ║')
        self.write('║               THE COMMONS GAME               ║')
        self.write('║' + 'I hereby declare the right of the commons.'.center(46) + '║')
        self.write('╚══════════════════════════════════════════════╝')
        self.write('A central authoritative engine enforcing decentralised decision rules.')
        self.write('Local simulation: selecting an identity is not authentication.')
        if self.hot_seat:
            self.write('EXPLICIT DEVELOPMENT HOT-SEAT ENABLED.')
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
                context = 'synthetic simulation' if config.get('synthetic') else 'empirical ecosystem / SIMULATION ONLY'
                self.write(f"\nWorld: {config['title']} / {context} / Actor: {self.session.actor} / State {len(game.project('log')):03}")
                self.write('[1] ECOSYSTEM — We can act together.')
                self.write('[2] GATHERING — We make it happen.')
                self.write('[3] SCENARIOS — What can we accomplish together?')
                self.write('[4] HISTORY & TRAJECTORIES  [5] HELP  [Q] QUIT')
                self.write('[g] World graph  [n] Contract inbox  [p] My profile  [c] Request binding  [x] Sign out')
                if self.hot_seat:
                    self.write('[s] Switch local actor — explicit hot-seat')
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
                        self.write('Signed out. The authoritative world is preserved.')
                        if not self.onboarding():
                            break
                    elif choice == 's' and self.hot_seat:
                        self.select_actor()
                    elif choice in {'5', '?'}:
                        self.write('Inspect → choose a valid action → review version → explicitly submit.')
                        self.write('b: back; 0: cancel a form; q: quit. Invalid fields repeat locally.')
                        self.write('Commitment ≠ commit. Acceptance ≠ institutional authorisation ≠ verified outcome.')
                        self.write('Normal play stays bound to your actor. Hypothetical branches never change saved history.')
                    else:
                        self.write('Choose one of the listed actions. Identity switching requires --hot-seat.')
                except Cancelled:
                    self.write('Cancelled; no incomplete action was submitted.')
                except ValueError as error:
                    self.write('Action unavailable: ' + str(error))
        except (EOFError, Cancelled):
            pass
        self.write('Session closed. Accepted history is preserved.')
        return self.current()


def run_play(game, **options):
    return Terminal(game, **options).run()
