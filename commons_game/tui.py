"""Terminal-first laboratory. Forms produce commands; the engine owns decisions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from uuid import uuid4

from .player import ActorSession

ACTION_NAMES = {
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


def render_trajectory(document, output, *, branch_id=None):
    from .trajectory import frames
    envelope = document['plan']['commons_trajectory']
    output.write('SUBTLE PATHWAYS / TRAJECTORY\n')
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
                         f"{agreement['status']} / outcome={agreement['outcome_status']}\n")
    output.write(f'CURRENT STATE: {last:03}\nNo geometric coordinates or physical quantities inferred.\n')


class Terminal:
    def __init__(self, game, *, actor=None, store=None, hot_seat=False, source=None, output=None):
        self.game, self.store, self.hot_seat = game, store, hot_seat
        self.source = source if source is not None else sys.stdin
        self.output = output if output is not None else sys.stdout
        self.session = ActorSession(game, actor, store=store, hot_seat=hot_seat) if actor else None
        self.branches = []

    def write(self, value=''):
        self.output.write(display(value) + '\n')
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
        selected = self.choose('Select your local actor identity:', actors, lambda a: a['label'])
        if self.session:
            self.session.switch(selected['id'])
        else:
            self.session = ActorSession(self.game, selected['id'], store=self.store, hot_seat=self.hot_seat)
        self.write(f"ACTOR: {selected['label']} ({selected['id']})")

    def inspect_contract(self, agreement):
        version = agreement['versions'][agreement['current_version'] - 1]
        self.write(f"CONTRACT {agreement['id']} / VERSION {version['number']} / {agreement['status']}")
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

    def inspect_mode(self, mode):
        game = self.current()
        world = game.get_world()
        self.write('\nSUBTLE PATHWAYS / ' + mode.upper())
        if mode == 'ecosystem':
            for actor in world['actors'].values():
                self.write(f"ACTOR {actor['id']}: {actor['label']} / {actor['kind']}")
            for table in ('relationships', 'capacities', 'needs'):
                self.write(table.upper())
                for record in world[table].values():
                    self.write(json.dumps(record, ensure_ascii=False))
            for possibility in game.derive_possibilities():
                self.write('INFERRED POSSIBILITY (not an agreement): ' + json.dumps(possibility))
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
        self.write('[a] Available actions  [w] Full world  [b] Back')
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
            payload = {'kind': kind, **deepcopy(world['configuration']['world']['proposal'])}
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
        else:
            self.write('REJECTED: ' + ', '.join(result['errors']) + '. No state changed.')
        return result

    def act(self):
        version, candidates = self.session.available_actions()
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
            target = self.choose('Whom do you know?', list(world['actors'].values()), lambda a: a['label'])
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
        if respond:
            pending = [r for r in world['relationships'].values() if r['kind'] == 'invited'
                       and r['target_id'] == self.session.actor and r['status'] == 'proposed']
            item = self.choose('Your pending invitations:', pending, lambda r: r['id'] + ' from ' + r['source_id'])
            response = self.choose('Response?', ['accept', 'decline'])
            payload = {'kind': 'respond_invitation', 'invitation_id': item['id'], 'response': response}
        else:
            objective = self.choose('Gathering objective?', [o for o in world['objectives'].values() if o['mode'] == 'gathering'], lambda o: o['label'])
            recipient = self.choose('Invite whom?', [a for a in world['actors'].values() if a['id'] != self.session.actor], lambda a: a['label'])
            payload = {'kind': 'invite', 'recipient_id': recipient['id'], 'objective_id': objective['id']}
        if self.confirm('Submit this invitation action?'):
            self.submit(payload, version)

    def mode(self, name):
        while True:
            self.inspect_mode(name)
            choice = self.read().lower()
            if choice in {'b', '0', 'q'}:
                return
            try:
                if choice == 'a':
                    self.act()
                elif choice == 'w':
                    self.write(json.dumps(self.current().get_world(), indent=2, ensure_ascii=False))
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
                    self.write(json.dumps(game.world_at(event=seq), indent=2, ensure_ascii=False))
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
        self.write('║               SUBTLE PATHWAYS                ║')
        self.write('║               THE COMMONS GAME               ║')
        self.write('║ We hereby declare the right of the commons   ║')
        self.write('╚══════════════════════════════════════════════╝')
        self.write('A central authoritative engine enforcing decentralised decision rules.')
        self.write('Local simulation: selecting an identity is not authentication.')
        if self.hot_seat:
            self.write('EXPLICIT DEVELOPMENT HOT-SEAT ENABLED.')
        try:
            if self.session is None:
                self.select_actor()
            while True:
                game = self.current()
                config = game.get_world()['configuration']['world']
                self.write(f"\nWorld: {config['title']} / synthetic simulation / Actor: {self.session.actor} / State {len(game.project('log')):03}")
                self.write('[1] ECOSYSTEM — Who can act together?')
                self.write('[2] GATHERING — Can we make it happen?')
                self.write('[3] SCENARIOS — What can we accomplish together?')
                self.write('[4] HISTORY & TRAJECTORIES  [5] HELP  [Q] QUIT')
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
