"""Full-screen player interface. Screen state is independent of curses and rules.

All mutations pass through ActorSession and the existing command forms. The
viewport owns keyboard/display concerns only; line-mode play remains available.
"""
from dataclasses import dataclass, field
from copy import deepcopy
from io import StringIO
import os
import textwrap
import unicodedata

from .catalogue import affiliations, people
from .commands import resolve
from .expertise import cell, matrix
from .heatmap import BANDS, band, mark
from .network_view import CATEGORIES, focus_graph, draw_graph
from .scenario_catalogue import catalogue, objectives_for, scenarios_for
from .play import ACTION_EFFECTS, PlayableTerminal
from .presentation import OBJECTS, Presentation, clean, display_label, folded, status
from .tui import ACTION_NAMES, EVENT_NAMES, Cancelled

MODES = {'ecosystem': 'Explore offers, needs and potential complementarities.',
         'gathering': 'Inspect gathering conditions and registered invitation actions.',
         'scenarios': 'Inspect source scenarios, linked objectives and recorded trajectories.'}
DECISION_KEYS = {'accept': ('y', 'Accept'), 'amend': ('j', 'Negotiate'),
                 'reject': ('R', 'Reject'), 'withdraw': ('X', 'Withdraw')}


def score_text(detail):
    if detail['value'] is not None: return str(detail['value'])
    if detail.get('upper') is None: return 'Unknown'
    return f"Unknown ({detail['lower']}–{detail['upper']}; lower bound {detail['lower']})"


@dataclass
class Route:
    kind: str
    target: str | None = None
    index: int = 0
    scroll: int = 0
    row: int = 0
    column: int = 0
    query: str = ''
    extra: dict = field(default_factory=dict)
    region: str = 'explore'
    decision_index: int = 0
    reveal: bool = False


@dataclass
class Screen:
    title: str
    lines: list[str] = field(default_factory=list)
    entries: list[tuple[str, object]] = field(default_factory=list)
    footer: str = ''
    selected: int = 0
    scroll: int = 0
    # Matrix row and column highlights supplement textual markers.
    highlights: set[int] = field(default_factory=set)
    navigation: bool = True
    styles: list = field(default_factory=list)
    show_entries: bool = True
    breadcrumb: str = ''
    wrap_entries: bool = False
    decisions: list[tuple[str, object]] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    region: str = 'explore'
    decision_index: int = 0
    reveal: bool = False
    split_regions: bool = False
    raster_start: int | None = None


class FullScreenTerminal(PlayableTerminal):
    """A screen stack over one shared saved world and one simulated perspective."""
    def __init__(self, game, *, viewport, **options):
        options.pop('output', None)
        super().__init__(game, output=StringIO(), **options)
        self.viewport = viewport
        self.stack = [Route('matrix')]
        self.mode_routes = {'ecosystem': self.stack[0], 'gathering': Route('gathering'), 'scenarios': Route('scenarios')}
        self.mode_stacks = {mode: [route] for mode, route in self.mode_routes.items()}
        self.notice = ''
        self.width, self.height = 80, 24

    @property
    def route(self):
        return self.stack[-1]

    @property
    def playing_actor(self):
        return self.session.actor if self.session else None

    @property
    def focused_actor(self):
        for route in reversed(self.stack):
            if route.kind in {'inspect','network'} and route.target in self.world()['actors']:
                return route.target
            if route.kind=='cell':
                return route.extra.get('relation',(None,None))[0]
        return None

    @property
    def focused_relation(self):
        for route in reversed(self.stack):
            if route.extra.get('relation'):
                return tuple(route.extra['relation'])
        return None

    def breadcrumbs(self):
        parts=[]
        for route in self.stack:
            if route.kind=='matrix':parts.append('Ecosystem')
            elif route.kind=='cell' and route.extra.get('relation'):
                parts.append(' → '.join(self.label(p) for p in route.extra['relation']))
            elif route.kind=='scenario':parts.append('Scenario')
            elif route.target:parts.append(self.label(route.target) if route.kind!='network' else 'Network: '+self.label(route.target))
            else:parts.append(route.kind.capitalize())
        return ' > '.join(parts)

    def reset_buffer(self):
        self.output.seek(0); self.output.truncate()

    def context(self, *, at=None):
        actor = self.label(self.session.actor) if self.session else 'Choose a person'
        focus = ' · Focus: '+self.label(self.focused_actor) if self.focused_actor else ''
        return f'Playing: {actor}'+focus+' · Simulation · '+self.world()['configuration']['world']['title']+f' · v{len(self.current().project("log"))}' + (' · Historical view' if at is not None else '')

    def capture(self, operation):
        self.reset_buffer(); operation()
        return [line for line in self.output.getvalue().strip().splitlines()
                if not line.startswith('Playing: ') and not (line.strip() and set(line.strip()) <= {'=','-','─'})]

    def read(self, prompt='>'):
        result = self.viewport.prompt(prompt, self.output.getvalue().splitlines(), self.context())
        self.reset_buffer()
        if result is None:
            raise Cancelled
        return result.strip()

    def picker(self, title, items, *, render=None, preview=None):
        if not items:
            self.notice = 'No matching choices are available.'
            raise Cancelled
        def label(item):
            if render:
                return render(item)
            return display_label(item)
        return self.viewport.choose(title, items, label, self.context(), preview=preview)

    def choose(self, prompt, items, label=str):
        return self.picker(prompt, items, render=label)

    def select_actor(self):
        self.refresh()
        roster = people(self.world())
        # Deliberate development-only roles remain reachable without polluting
        # the imported people catalogue or implying source authentication.
        choices = [*roster, {'id': '__development__', 'kind': 'role', 'label': 'Development simulation roles…'}]
        def label(actor):
            orgs = affiliations(self.world(), actor['id'])
            return display_label(actor) + (' · '+', '.join(orgs) if orgs else '')
        actor = self.picker('WHO WILL YOU PLAY? / search by first name', choices, render=label,
            preview=lambda a: self.capture(lambda: self.inspect_node(a['id'])) if a['id'] != '__development__' else
                ['Explicit development roles grant simulation authority only. They do not authenticate a real person.'])
        if actor['id'] == '__development__':
            actor = self.picker('DEVELOPMENT ROLES / simulation authority only', people(self.world(), development=True))
        self.assume_actor(actor)
        if not self.mode_routes['ecosystem'].extra.get('positioned'):
            ids = [a['id'] for a in matrix(self.world())['actors']]
            if actor['id'] in ids:
                self.mode_routes['ecosystem'].row = self.mode_routes['ecosystem'].column = ids.index(actor['id'])
            self.mode_routes['ecosystem'].extra['positioned'] = True
        self.notice = 'Now simulating '+display_label(actor)+'. The shared world is unchanged.'

    def choose_mode(self):
        mode = self.choose('CHOOSE YOUR PATH', list(MODES), lambda name: name.upper()+' · '+MODES[name])
        self.resume_mode(mode)

    def switch_mode(self, mode):
        """Explicitly reopen a mode root (for example x → Matrix)."""
        self.mode_stacks[self.mode_name] = self.stack
        self.mode_name = mode
        self.stack = [self.mode_routes[mode]]
        self.mode_stacks[mode] = self.stack
        self.selected = None

    def resume_mode(self, mode):
        self.mode_stacks[self.mode_name] = self.stack
        self.mode_name = mode
        self.stack = self.mode_stacks[mode]
        self.selected = None

    def push(self, kind, target=None, **extra):
        if kind == 'inspect' and not self.node(target,at=extra.get('at')):
            raise ValueError('object_not_present_at_this_state')
        if 'relation' not in extra and self.focused_relation:
            extra['relation']=self.focused_relation
        if kind=='inspect' and target in self.world()['relationships']:
            context=self.world()['relationships'][target].get('context',{})
            if context:extra['relation']=(context['provider_id'],context['requester_id'])
        self.stack.append(Route(kind, target, extra=extra, region='canvas' if kind == 'network' else 'explore'))

    def back(self):
        if len(self.stack) > 1:
            self.stack.pop()
        else:
            self.choose_mode()

    def run(self):
        try:
            self.viewport.message(Screen('SADDLE PATHWAYS', ['', 'I hereby declare the right of the commons.', '',
                'Simulation', '', 'Enter Begin · q Quit'], footer='Enter Begin · q Quit', navigation=False))
            if self.viewport.key() == 'q':
                return self.current()
            if not self.explore and not self.session:
                self.select_actor()
            self.choose_mode()
            while not self.finished:
                self.refresh()
                self.width, self.height = self.viewport.size()
                self.view.width = max(16, self.width-2)
                screen = self.build_screen()
                screen.breadcrumb = self.breadcrumbs()
                screen.region = 'explore' if self.route.kind == 'network' and screen.show_entries else self.route.region
                screen.reveal = self.route.reveal
                scroll = self.viewport.draw(screen, self.context(at=self.route.extra.get('at')), self.notice)
                self.route.reveal = False
                if isinstance(scroll, int) and screen.raster_start is None:
                    self.route.scroll = scroll
                self.notice = ''
                key = self.viewport.key()
                try:
                    self.handle(key, screen)
                except Cancelled:
                    self.notice = 'Cancelled. No incomplete form was submitted.'
                except (ValueError, RuntimeError) as error:
                    self.notice = 'Unavailable: '+str(error).replace('_', ' ')
        except (EOFError, KeyboardInterrupt, Cancelled):
            pass
        return self.current()

    def build_screen(self):
        route = self.route
        self.screen = 'inspector' if route.kind == 'inspect' else 'inbox' if route.kind == 'inbox' else 'explorer'
        if route.kind == 'matrix':
            return self.matrix_screen()
        if route.kind == 'cell':
            return self.cell_screen()
        if route.kind == 'expertise':
            actor = self.world()['actors'][route.target]; projection = matrix(self.world())
            i = next(i for i,a in enumerate(projection['actors']) if a['id']==actor['id'])
            lines = [self.label(actor['id']),'Complete declared expertise · unknown values remain ?']
            for side,kind in (('offer','O'),('need','N')):
                observation = projection['observations'][actor['id']][side]
                lines += [side.upper()+': '+observation['state']]
                lines += [projection['vocabulary'][code]+': '+('?' if value is None else 'Selected' if value else 'Not selected')
                          for code,value in zip(projection['domains'],projection[kind][i])]
            return Screen('OFFERS AND NEEDS',lines,scroll=route.scroll,footer='PgUp/PgDn Scroll  b Profile')
        if route.kind == 'incidence':
            projection=matrix(self.world()); i=next(i for i,a in enumerate(projection['actors']) if a['id']==route.target)
            k=projection['domains'].index(route.extra['domain']);kind=route.extra['matrix_kind'];value=projection[kind][i][k]
            observation=projection['observations'][route.target]['offer' if kind=='O' else 'need']
            return Screen('DECLARED '+('OFFER' if kind=='O' else 'NEED'),[
                self.label(route.target),projection['vocabulary'][route.extra['domain']],
                'Value: '+('Unknown' if value is None else str(value)), 'Answer state: '+observation['state'],
                'World state '+str(len(self.current().project('log')))+' · Source details remain optional.'],
                [('Explore '+self.label(route.target),route.target)],'Enter Profile  d Source details  b Matrix')
        if route.kind == 'inspect':
            return self.inspector_screen()
        if route.kind == 'contracts':
            nodes = [n for n in self.graph_projection()['nodes'] if n['kind'] == 'agreement']
            if route.extra.get('filters'):
                from .projections import contract_registry
                matches = {a['id'] for a in contract_registry(self.world(),**route.extra['filters'])}
                nodes = [n for n in nodes if n['id'] in matches]
            result=self.list_screen('CONTRACT REGISTRY / transversal layer', nodes)
            if self.playing_actor:
                result.entries += [('Propose a contract / choose a person',('choose_interaction','propose'))]
                if self.world()['actors'][self.playing_actor]['kind']=='person':
                    result.entries += [('Invite to connect / choose a person',('choose_interaction','invite'))]
            return result
        if route.kind == 'inbox':
            if not self.session:
                return Screen('INBOX', ['p Choose a simulated player first.'])
            category = route.extra.get('category')
            items = self.session.inbox_records(category)
            entries = [(self.aliases().get(item['id'], 'Invitation')+' · '+item['label']+' · '+' / '.join(item['badges']), item['id'])
                       for item in items if folded(route.query) in folded(item['label'])]
            route.index = min(route.index, max(0, len(entries)-1))
            lines = ['Filter: '+(category or 'All my records')+' · One entry per object',
                     'Badges describe pending decisions; filters do not create extra records.']
            if not entries: lines.append('No items in this view. F changes the filter; c opens all contracts.')
            return Screen('INBOX / INVITATIONS AND CONTRACTS', lines, entries,
                          'Enter Review  a Actions  F Filter', route.index, route.scroll, wrap_entries=True)
        if route.kind == 'history':
            entries = [(EVENT_NAMES.get(e.get('command', {}).get('kind') if e.get('command') else '',
                                       e['kind'].replace('.', ' ').replace('_', ' '))+' · '+self.label(e['actor_id'])
                        if e.get('actor_id') in self.world()['actors'] else e['kind'].replace('.', ' '), e['sequence'])
                       for e in self.current().project('log') if any(m['entity_id'] == route.target for m in e['mutations'])]
            return Screen('HISTORY / '+self.label(route.target), ['Recorded changes. Enter opens a clearly marked historical view.'],
                          entries, 'Enter Inspect historical state', route.index, route.scroll)
        if route.kind == 'trajectory':
            from .trajectory import frames, project_trajectory
            try:
                document = project_trajectory(self.current())
                records = frames(document)
                lines = ['RECORDED SIMULATION HISTORY / no invented real-world trajectory']
                for record in records:
                    lines.append(EVENT_NAMES.get(record['event_kind'],EVENT_NAMES.get(record['kind'], record['kind'].replace('_', ' '))))
                    lines += ['  '+self.aliases().get(item['id'],'Invitation')+' · '+status(item['status'])+' · contact only'
                              for item in record['invitations']]
                    for agreement in record['agreements']:
                        lines.append('  '+self.contract_title(agreement['id'])+' · '+status(agreement['status'])+' · Outcome: '+status(agreement['outcome_status']))
            except (ImportError, ValueError) as error:
                lines = ['Trajectory package unavailable. Install the pinned trajectory extra.', clean(error),
                         'h History and replay remain available without it.']
            return Screen('RECORDED TRAJECTORY', lines, footer='v Verify replay  PgUp/PgDn Scroll', scroll=route.scroll)
        if route.kind == 'gathering':
            from .gathering import conditions
            objectives = [n for n in self.graph_projection()['nodes'] if n['kind'] == 'objective' and n.get('mode') == 'gathering']
            if not objectives:
                return Screen('GATHERING / CONDITIONS', [
                    'No gathering objective is registered in this world.',
                    'Invitation and attendance actions are unavailable here.',
                    'This mode remains an inspectable view of this same saved world.',
                    'Contracts are available with c. No collective event planner is implemented.'])
            pending = [r for r in self.world()['relationships'].values() if r['kind'] == 'invited']
            lines = ['Registered gathering objectives and recorded invitations.']
            for objective in objectives:lines += conditions(self.world(),objective)
            lines += [self.label(r['source_id'])+' → '+self.label(r['target_id'])+' · '+status(r['status']) for r in pending]
            lines += ['Conditions and outcomes come from the existing engine, not inferred attendance.']
            return self.list_screen('GATHERING / CONDITIONS', objectives, lines, 'j Invite  r Respond')
        if route.kind == 'scenarios':
            records=[r for r in catalogue(self.world()) if folded(route.query) in folded(r['title'])]
            return Screen('SCENARIOS / CATALOGUE',[
                'Scenario = situation and possible transformation; objective = desired condition; contract = proposed or accepted agreement.',
                'Workshop source material is inspectable. Strategy and coalition gameplay are not implemented.',
                'Synthetic fixtures are labelled separately; selecting one never changes this world.'],
                [(r['title']+' · '+r['status'],('scenario',r['id'])) for r in records],
                'Enter Inspect scenario  t Trajectory',route.index,route.scroll)
        if route.kind == 'scenario':
            record=next(r for r in catalogue(self.world()) if r['id']==route.target)
            lines=[record['title'],record['status'],record['description'],record['context'],
                   'PROVENANCE: '+record['provenance']['kind'].replace('_',' ')+' · '+record['provenance']['source_path']]
            if record.get('source_review'):lines.append(record['source_review'])
            lines += ['POSSIBLE DESIRED CONDITIONS (source prompts, not achieved objectives)']
            lines += ['  '+o['title'] for o in record.get('possible_objectives',[])]
            lines += ['CONDITIONS / STEPS']+record.get('conditions',[])
            bound=objectives_for(record,self.world())
            lines += ['LINKED OBJECTIVES IN THIS WORLD']+[meaning for _,meaning in bound]
            if not bound:lines.append('No objective is registered for this scenario in the current world.')
            return Screen('SCENARIO / INSPECT',lines,[(self.node_label({**o,'kind':'objective'}),o['id']) for o,_ in bound],
                          'Enter Objective  t Recorded trajectory',route.index,route.scroll)
        if route.kind == 'network':
            return self.network_screen()
        if route.kind == 'help':
            return Screen('HELP / YOUR PATH THROUGH THE COMMONS', [
                'Arrows move the heatmap cell or list selection. Enter opens the highlighted item.',
                'A matrix row offers expertise; a column requests it. W = O N^T.',
                '* marks your row and column. [] marks the selected cell. ? means unknown; 0 means a known zero.',
                'z switches heatmap/numbers. Fixed count bands: 0, 1, 2–3, 4–6, 7–10, 11+. No normalisation.',
                'Uppercase O / N / W switch offers, needs and matches. / finds a person or expertise domain.',
                'A partially observed cell shows bounds. A complete empty vector can establish zero even with unknown inputs.',
                'w opens Hack Network. Tab/Up/Down select nodes; Enter inspects; f centres a node; [ ] page neighbours; r rotates; + - zoom.',
                'Network: S scope; L layer filter; 3 toggles experimental 3D; r yaw and { / } pitch in 3D. Coordinates carry no social meaning.',
                'Playing is your simulated agency. Focus and selected relationship never change your player.',
                'Diagonal self-pairings are excluded from actions. Nothing in the matrix implies consent.',
                'm chooses a path; e/g/s resume paths with their previous navigation context.',
                'b or Esc returns to the preceding screen with its selection and scroll position.',
                'Up/Down select or scroll; Enter opens or confirms the selection. Tab changes regions.',
                'Contract: Explore → Decisions → Details. Network: canvas ↔ object list.',
                'PgUp/PgDn scroll long content. / searches lists and matrix participants.',
                'a shows permitted actions for an inspected object. c contracts; i inbox; h object history.',
                'In a relationship: j invites to connect; k proposes directly. Neither pathway requires the other.',
                'In a contract: y accepts, j negotiates, R rejects and X withdraws, only where the engine permits.',
                'Inbox: F chooses a filter. Each canonical object appears once; badges show overlapping categories.',
                'p changes simulated perspective. It grants no real-world representation or consent.',
                'First names only. (1), (2), … distinguish different people with the same first name; these are stable creation-order labels.',
                ': opens typed commands, including open K-001, contract history and available actions.',
                'd opens optional source and technical details. t trajectory. v verifies replay.',
                'Network, People, Organisations and Resources: x alternative ecosystem views.',
                'Network: S changes scope, L filters layers, [ ] pages, +/− zooms, r rotates.',
                'Dark points are off-scope actors; rings are isolated in the full projection. 3D is experimental.',
                'q quits; completed actions are already saved.'], scroll=route.scroll)
        if route.kind == 'details':
            lines = [self.world()['configuration']['world']['title'],
                     'Current saved state version: '+str(len(self.current().project('log')))]
            if route.target:
                lines += self.capture(lambda: self.cmd_metadata(route.target))
            return Screen('OPTIONAL SOURCE / TECHNICAL DETAILS', lines, scroll=route.scroll)
        if route.kind == 'notice':
            return Screen(route.extra.get('title', 'NOTICE'), route.extra.get('lines', []), scroll=route.scroll)
        # Alternative ecosystem views remain projections over the same world.
        kinds = {'people': 'person', 'organisations': 'organisation', 'resources': 'resource'}
        nodes = self.graph_projection()['nodes']
        if route.kind in kinds:
            nodes = [n for n in nodes if n['kind'] == kinds[route.kind]]
        else:
            nodes = [n for n in nodes if n['kind'] not in {'capacity', 'need', 'evidence'}]
        return self.list_screen('ECOSYSTEM / '+route.kind.upper(), nodes)

    def node_label(self, node):
        style = OBJECTS.get(node['kind'], OBJECTS['evidence'])
        symbol = style.plain if self.plain else style.symbol
        return symbol+' '+(self.aliases().get(node['id'], '')+' ' if node['kind'] in {'agreement','invitation'} else '')+display_label(node)+(
            ' · '+status(node['status'])+' / Outcome: '+status(node['outcome_status']) if node['kind'] == 'agreement' else '')

    def object_actions(self, target):
        if not self.session or self.route.extra.get('at') is not None:
            return []
        _, candidates = self.session.available_actions()
        return [c for c in candidates if c.get('agreement_id') == target or c.get('invitation_id') == target]

    def inspector_screen(self):
        route = self.route; at = route.extra.get('at')
        world = self.current().world_at(event=at) if at is not None else self.world()
        node = self.node(route.target, at=at)
        historical = at is not None
        if historical:
            return Screen('HISTORICAL / '+self.label(route.target, world),
                self.capture(lambda:self.inspect_node(route.target,at=at)), footer='Read-only · b Current context', scroll=route.scroll)
        actions = self.object_actions(route.target)
        decision_entries = []
        for action in actions:
            title = ACTION_NAMES[action['kind']]
            if action['kind'] == 'respond_contact': title = 'Accept invitation' if action['response']=='accept' else 'Decline invitation'
            decision_entries.append((title, ('decision', action)))
        if node['kind'] == 'agreement':
            version = node['versions'][node['current_version']-1]
            def acceptance(party):
                role = 'Proposer' if party == node['created_by'] else 'Counterparty'
                receipt = 'accepted' if party in version['acceptances'] else 'no acceptance recorded'
                return f'{role}: {self.label(party)} · {receipt}'
            lines = [self.contract_title(node['id']), 'Purpose: '+version['terms']['purpose'],
                     'Proposed by: '+self.label(node['created_by']),
                     'Status: '+status(node['status'])+' · Outcome: '+status(node['outcome_status']),
                     'Terms version: '+str(version['number'])+' · Amendments require renewed acceptance.',
                     *(acceptance(p) for p in node['parties']),
                     'Proposing does not accept the terms. Each party decides independently.',
                     'Governing policy: '+self.label(version['policy_id'])]
            kinds = {a['kind'] for a in actions}
            details = [self.label(r['actor_id'])+': '+r['description'] for r in version['terms']['responsibilities']]
            details += ['Condition: '+c for c in version['terms']['conditions']]
            details += ['Resource: '+self.label(r['resource_id'])+f" × {r['quantity']}" for r in version['resources']]
            details += ['Valid until: '+version['valid_until'],
                        'Party acceptance and institutional authorisation are separate.',
                        'Reject declines a proposal; Withdraw closes it before activation under the current party rule.',
                        'Evidence: '+str(len(node['evidence_ids']))+' record(s) · d Source details / h History']
            # One readable link per participant, despite proposer/party relations.
            linked = [*node['parties'],node['objective_id'],version['policy_id'],
                      *(r['resource_id'] for r in version['resources']),*node['evidence_ids']]
            entries = [(self.node_label(self.node(key)),key) for key in dict.fromkeys(linked)]
            entries += [('Relevant scenario · '+r['title'],('scenario',r['id'])) for r in scenarios_for(node['objective_id'],world)]
            decision_entries = [
                (f'[{DECISION_KEYS[a["kind"]][0]}] {label}' if a['kind'] in DECISION_KEYS else label, ('decision', a))
                for label, (_, a) in decision_entries]
            route.index = min(route.index, max(0, len(entries)-1))
            route.decision_index = min(route.decision_index, max(0, len(decision_entries)-1))
            if route.region == 'decisions' and not decision_entries:
                route.region = 'explore'
            footer = '  '.join(' '.join(key) for kind, key in DECISION_KEYS.items() if kind in kinds)
            return Screen('CONTRACT INSPECTOR',lines,entries,
                          footer+'  Tab Regions  a Actions  h History',route.index,route.scroll,
                          decisions=decision_entries, details=details, region=route.region,
                          decision_index=route.decision_index, split_regions=True)
        if node['kind'] == 'invitation':
            lines = [self.aliases().get(node['id'],'Invitation')+' · Invitation to connect · '+status(node['status']),
                     'From '+self.label(node['source_id'])+' to '+self.label(node['target_id']),
                     node['message'], 'Purpose: '+(node['purpose'] or 'Explore a possible collaboration'),
                     'Simulation contact only. No contractual obligations or real-world contact are implied.']
            if node.get('response'): lines.append('Response: '+node['response']['decision']+' · '+node['response']['message'])
            if node['status']=='accepted': lines.append('Connection acknowledged. A contract remains an independent decision.')
            elif not actions: lines.append('No decision is available to your role in this invitation state.')
            entries = [(self.node_label(self.node(p)),p) for p in (node['source_id'],node['target_id'])]
            if self.playing_actor in (node['source_id'],node['target_id']):
                other = node['target_id'] if node['source_id']==self.playing_actor else node['source_id']
                entries += [('Propose a contract directly',('propose_to',other))]
                entries += [('Invite to connect again',('invite_to',other))]
            entries = decision_entries+entries
            return Screen('INVITATION / CONNECT',lines,entries,'Enter Choose  a Actions  h History  w Network  d Provenance',route.index,route.scroll)
        if node['id'] in world['actors']:
            lines = [display_label(node),'Affiliation: '+(', '.join(affiliations(world,node['id'])) or 'Unknown / not recorded')]
            for table, label in (('capacities','Offers'),('needs','Needs')):
                records = [r for r in world[table].values() if r['actor_id']==node['id']]
                lines.append(label+f' ({len(records)}): '+(', '.join(r['domain'] for r in records[:3]) or 'Not recorded')+(' …' if len(records)>3 else ''))
            connections = [r for r in world['relationships'].values() if r['kind']=='acknowledged_connection' and node['id'] in (r['source_id'],r['target_id'])]
            lines += [f'Acknowledged connections: {len(connections)}', 'Potential complementarities are declared possibilities. They imply no consent.']
            entries = []
            if self.playing_actor and self.playing_actor!=node['id'] and node['kind']=='person':
                if world['actors'][self.playing_actor]['kind']=='person':
                    entries += [('Invite to connect',('invite_to',node['id']))]
                if self.proposal_permitted(node['id']):
                    entries += [('Propose a contract directly',('propose_to',node['id']))]
                else:lines.append('Contract proposal unavailable for this role/counterparty and the registered scenario constraints.')
            entries += [('Complete offers and needs',('expertise',node['id']))]
            contracts = [a for a in world['agreements'].values() if node['id'] in a['parties']]
            entries += [('Contract · '+self.contract_title(a['id']),a['id']) for a in contracts]
            for r in connections:
                other = r['target_id'] if r['source_id']==node['id'] else r['source_id']
                entries.append(('Acknowledged connection · '+self.label(other), r['invitation_id']))
            potentials = self.current().derive_possibilities(world)
            relevant = []
            for p in potentials:
                if node['id'] in (p['source_id'],p['target_id']):
                    other=p['target_id'] if p['source_id']==node['id'] else p['source_id']
                    if other not in relevant: relevant.append(other)
            entries += [('Potential · '+self.label(p),('relation_to',(node['id'],p))) for p in relevant[:4]]
            lines += [f'{len(relevant)} potential counterparties · w opens the paged network.']
            return Screen('INSPECT / '+node['kind'].upper(),lines,entries,'Enter Choose  a Actions  w Network  d Source details',route.index,route.scroll)
        lines = self.capture(lambda:self.inspect_node(route.target))
        entries = [(self.node_label(n),n['id']) for n in self.neighbours(route.target)]
        if node['kind']=='objective': entries = [('Scenario · '+r['title'],('scenario',r['id'])) for r in scenarios_for(route.target,world)]+entries
        return Screen('INSPECT / '+node['kind'].upper(),lines,entries,'Enter Follow link  h History  d Details',route.index,route.scroll)

    def contract_title(self, target):
        return self.aliases().get(target, 'Contract')+' · '+self.label(target)

    def list_screen(self, title, nodes, lines=None, footer='Enter Inspect  / Search'):
        nodes = [n for n in nodes if folded(self.route.query) in folded(display_label(n))]
        nodes.sort(key=lambda n: (folded(display_label(n)), n['id']))
        self.route.index = min(self.route.index, max(0, len(nodes)-1))
        entries = [(self.node_label(n), n['id']) for n in nodes]
        context = list(lines or [])
        if self.route.query:
            context.append('Search: '+self.route.query)
        if not nodes:
            context.append('No matching objects. / changes the search; b returns.')
        return Screen(title, context, entries, footer, self.route.index, self.route.scroll)

    def matrix_screen(self):
        projection = matrix(self.world()); self._matrix = projection
        route = self.route; roster = projection['actors']; count = len(roster)
        kind = route.extra.get('matrix_kind', 'W'); numeric = route.extra.get('numeric', False)
        domains = projection['domains']; axis = roster if kind=='W' else [{'id':code,'label':projection['vocabulary'][code]} for code in domains]
        if not count or not axis:
            return Screen('ECOSYSTEM / MATRIX EXPLORER', ['No eligible matrix observations in this world.', 'x opens alternative ecosystem views.'])
        route.row = min(route.row,count-1); route.column = min(route.column,len(axis)-1)
        row_count = max(1,self.height-19); col_count = max(1,(self.width-23)//5)
        first_row = route.row//row_count*row_count; first_col = route.column//col_count*col_count
        columns = range(first_col,min(len(axis),first_col+col_count))
        own = next((i for i,a in enumerate(roster) if a['id']==self.playing_actor),None)
        value = projection[kind][route.row][route.column]
        meaning = 'W = O N^T · Rows OFFER → columns REQUEST' if kind=='W' else ('O / OFFERS' if kind=='O' else 'N / NEEDS')+' · People × expertise domains'
        exact = score_text(cell(projection,route.row,route.column)) if kind=='W' else ('Unknown' if value is None else str(value))
        lines = [meaning,
            'Selected: '+display_label(roster[route.row])+' → '+display_label(axis[route.column])+' · Exact matches: '+exact,
            '* Your row/column  [] Selection  ? Unknown  0 Known zero  - Self (excluded)' if kind=='W' else '* Current player  [] Selection  1 Selected  0 Not selected  ? Unknown',
            'Scale: '+' '.join((b.ascii if self.plain else b.glyph)+'='+b.label for b in BANDS)+' · z Heatmap/numbers' if kind=='W' else 'Fixed categories: 1 Selected / 0 Not selected / ? Unknown · z Numbers']
        styles=[]; highlights=set()
        if kind=='W' and not numeric:
            column=len('Scale: ')
            for item in BANDS:
                label=(item.ascii if self.plain else item.glyph)+'='+item.label
                styles.append((3,column,len(label),'#111111' if item.maximum is None or item.maximum>=10 else '#eee8d5',item.colour,False));column+=len(label)+1
        lines += [' '*20+''.join(f"{'*' if kind=='W' and j==own else ' '}{j+1:02}  " for j in columns),
                  ' '*20+''.join(display_label(axis[j])[:4].center(5) for j in columns)]
        for i in range(first_row,min(count,first_row+row_count)):
            row=f"{'*' if i==own else ' '}{i+1:02} "+display_label(roster[i])[:14].ljust(16)
            for j in columns:
                current=projection[kind][i][j]; diagonal=kind=='W' and i==j
                glyph=mark(current,diagonal=diagonal,numeric=numeric,plain=self.plain) if kind=='W' else ('?' if current is None else str(current) if numeric or self.plain else '●' if current else '·')
                part=('['+glyph+']' if (i,j)==(route.row,route.column) else ('*'+glyph if kind=='W' and j==own else glyph)).center(5)
                if current is not None and not diagonal and not numeric:
                    colour=band(current).colour if kind=='W' else '#a3bd95' if current else '#172331'
                    styles.append((len(lines),len(row),5,'#111111' if (current>=7 if kind=='W' else current==1) else '#eee8d5',colour,(i,j)==(route.row,route.column)))
                row+=part
            if i==own: highlights.add(len(lines))
            lines.append(row)
        lines += [f'Rows {first_row+1}–{min(count,first_row+row_count)}/{count} · Columns {first_col+1}–{min(len(axis),first_col+col_count)}/{len(axis)}']
        if kind=='W':
            detail=cell(projection,route.row,route.column)
            lines.append('Matching domains: '+(', '.join(detail['matching_domains']) or ('Unknown' if detail['value'] is None else 'None in the observed vocabulary')))
        else: lines.append('Domain: '+projection['vocabulary'][domains[route.column]])
        lines.append('World state '+str(len(self.current().project('log')))+' · Shared vocabulary and snapshot across O / N / W')
        return Screen('ECOSYSTEM / '+('COMPLEMENTARITY MATRIX' if kind=='W' else 'OFFERS O' if kind=='O' else 'NEEDS N')+' / '+('NUMERIC' if numeric else 'HEATMAP'),lines,
            footer='O Offers  N Needs  W Matches  Arrows Cell  Enter Inspect  o/n Own axis  z Numbers  w Network  / Find',highlights=highlights,styles=styles)

    def cell_screen(self):
        projection = matrix(self.world()); ids=[a['id'] for a in projection['actors']]
        relation=self.route.extra.get('relation')
        if relation:
            self.route.row,self.route.column=(ids.index(key) for key in relation)
        detail = cell(projection, self.route.row, self.route.column)
        reverse=cell(projection,self.route.column,self.route.row)
        self._cell = detail
        self.route.extra['relation']=(detail['provider']['id'],detail['requester']['id'])
        lines = ['Provider: '+display_label(detail['provider'])+' → Requester: '+display_label(detail['requester']),
                 score_text(detail)+' matching declared expertise domain(s)',
                 'Matching expertise: '+(', '.join(detail['matching_domains']) or 'None confirmed'),
                 'Reverse: '+display_label(reverse['provider'])+' → '+display_label(reverse['requester'])+
                 ' · '+score_text(reverse)+' matching domain(s)',
                 'Reverse expertise: '+(', '.join(reverse['matching_domains']) or 'None confirmed'),
                 'Scores describe potential, not acknowledged contact or accepted obligations.']
        lines += ['Answer coverage: offers '+detail['offer']['state']+' / needs '+detail['need']['state'],
                  'World state '+str(len(self.current().project('log')))+' · d Source details']
        pair={detail['provider']['id'],detail['requester']['id']}
        if detail['self_pairing']:lines.append('Self-pairing excluded from gameplay. Choose a different row or column.')
        elif self.playing_actor not in pair:lines.append('OBSERVATION ONLY: you are not a party to this relationship. Following a profile does not change who you play.')
        else:lines.append('You may propose new terms as '+self.label(self.playing_actor)+'. They require a separate decision by the other party.')
        if detail['value'] is None:lines.append('Incomplete coverage. Confirmed matches form a lower bound; remaining domains are unknown.')
        elif detail['value']==0:lines.append('No shared selections in this vocabulary; this does not exclude other collaboration.')
        entries = [('Inspect provider · '+display_label(detail['provider']), detail['provider']['id']),
                   ('Inspect requester · '+display_label(detail['requester']), detail['requester']['id'])]
        entries += [('Contract · '+self.contract_title(a['id']),a['id']) for a in self.world()['agreements'].values() if pair <= set(a['parties'])]
        if self.playing_actor in pair and not detail['self_pairing']:
            other = next(p for p in pair if p!=self.playing_actor)
            entries += [('Invite to connect',('invite_to',other))]
            if self.proposal_permitted(other):entries += [('Propose a contract directly',('propose_to',other))]
        entries += [('View in network',('network_of',detail['provider']['id']))]
        if self.route.extra.get('new_contract'):
            self.route.index=next((i for i,(_,key) in enumerate(entries) if key==self.route.extra['new_contract']),self.route.index)
            self.route.extra.pop('new_contract')
        self.route.index=min(self.route.index,len(entries)-1)
        lines.insert(0,'Selected link: '+entries[self.route.index][0])
        contracts=[a for a in self.world()['agreements'].values() if pair<=set(a['parties'])]
        if contracts:
            lines.insert(1,'Contracts here: '+'; '.join(self.contract_title(a['id'])+' · '+status(a['status']) for a in contracts))
        return Screen('A POTENTIAL CONNECTION / POTENTIAL COMPLEMENTARITY', lines, entries,
                      'Enter Choose  j Invite  k Propose contract  a Actions  w Network  d Source details', self.route.index, self.route.scroll)

    def open_network(self):
        centre=self.focused_actor if self.route.kind=='inspect' else self.playing_actor
        centre=centre or (self.focused_relation or (None,None))[0]
        if centre is None:
            actors=people(self.world());centre=actors[0]['id'] if actors else None
        self.push('network',centre)

    def network_screen(self):
        route=self.route;relation=self.focused_relation
        related=next((key for key in (relation or ()) if key!=route.target),None)
        if route.target in self.world()['agreements']:related=None
        limit=6 if self.width<85 or self.height<26 else 8
        visual=focus_graph(self.graph_projection(),route.target,related=related,query=route.query,
                           offset=route.extra.get('offset',0),limit=limit,
                           scope=route.extra.get('scope','neighbourhood'),categories=route.extra.get('categories'),
                           three_d=route.extra.get('three_d',False))
        if not visual['nodes']:return Screen('NETWORK / HACK TERMINAL',['No matching graph nodes. / Search or b Back.'])
        route.index=min(route.index,len(visual['nodes'])-1);selected=visual['nodes'][route.index]
        route.extra['offset'] = visual['offset']
        canvas_width = self.width-2
        zoom = route.extra.get('zoom', 1.)
        rotation = route.extra.get('yaw' if route.extra.get('three_d') else 'angle', 0.)
        lines=['Selected: '+self.node_label(selected)+' · Centre: '+self.label(route.target),
               'Scope: '+route.extra.get('scope_label','Player-centred neighbourhood' if route.target==self.playing_actor else 'Selected-actor neighbourhood')+
               (' · EXPERIMENTAL 3D' if route.extra.get('three_d') else ' · Planar'),
               f"Showing {len(visual['nodes'])}/{visual['full_node_count']} nodes · {visual['rendered_relationship_count']}/{visual['full_relationship_count']} edges ({len(visual['edges'])} bundles)",
               'Layers: '+(', '.join(route.extra['categories']) if route.extra.get('categories') else 'All')+
               f' · Zoom {zoom:.2f}x · Rotation {rotation:.1f} rad',
               f"Context: {len(visual['context_actor_ids'])} off-scope actors · {'o' if self.plain else '∘'} isolated",
               f"Neighbours {visual['offset']+1 if visual['total'] else 0}–{min(visual['total'],visual['offset']+limit)}/{visual['total']} · [ ] Page"]
        # Four header and three footer rows are reserved by CursesViewport.
        canvas_height = self.height-7-len(lines)
        lines = [line if len(line) <= canvas_width else line[:max(0,canvas_width-3)]+'...' for line in lines]
        self._network=visual
        entries = [(self.node_label(n),n['id']) for n in visual['nodes']]
        footer = 'Enter Inspect  Tab View  S Scope  L Layers  [ ] Page  f Centre  + - Zoom  r Rotate'
        if route.region == 'explore' or canvas_height < 3 or canvas_width < 12:
            return Screen('ECOSYSTEM / NETWORK / OBJECT LIST', lines, entries, footer,
                          route.index, route.scroll)
        canvas, spans = draw_graph(visual,canvas_width,canvas_height,selected=selected['id'],plain=self.plain,
            angle=route.extra.get('angle',0.),zoom=zoom,
            yaw=rotation,pitch=route.extra.get('pitch',0.),
            labels={n['id']:self.aliases()[n['id']]+' '+display_label(n) for n in visual['nodes'] if n['kind']=='agreement'})
        start = len(lines)
        styles=[(row+start,column,length,fg,bg,bold) for row,column,length,fg,bg,bold in spans]
        return Screen('ECOSYSTEM / NETWORK / HACK RENDERER',lines+canvas,entries,footer,route.index,0,
                      styles=styles,show_entries=False,raster_start=start)

    def handle(self, key, screen):
        route = self.route
        if key == 'resize':
            return
        if key == 'q':
            self.finished = True; return
        if key in {'b', 'esc'}:
            self.back(); return
        if key in {'e', 'g', 's'}:
            self.resume_mode({'e': 'ecosystem', 'g': 'gathering', 's': 'scenarios'}[key]); return
        if key == 'm':
            self.choose_mode(); return
        if key == 'p':
            self.select_actor(); return
        if route.kind=='matrix' and key in {'O','N','W'}:
            previous = route.extra.get('matrix_kind','W')
            route.extra[previous+'_column'] = route.column
            route.extra['matrix_kind'] = key
            route.column = route.extra.get(key+'_column',0)
            return
        if route.kind=='inbox' and key=='F':
            categories = ['All my records','Incoming invitations','Outgoing invitations','Accepted connections',
                          'Contract proposals','Awaiting my decision','Awaiting other parties',
                          'Agreements in progress','Verification requests','History']
            chosen = self.choose('INBOX FILTER',categories,str)
            route.extra['category'] = None if chosen==categories[0] else chosen
            route.index=route.scroll=0; return
        if route.kind=='inspect' and key in {'y','j','R','X'}:
            kinds = {'y':('accept','respond_contact'),'j':('amend',),'R':('reject','respond_contact'),'X':('withdraw','withdraw_contact')}
            candidate = next((c for c in self.object_actions(route.target) if c['kind'] in kinds[key]
                              and (c['kind']!='respond_contact' or c['response']==('accept' if key=='y' else 'decline'))),None)
            if candidate: self.execute_action(candidate)
            else: self.notice = 'That decision is unavailable for your role and this lifecycle state. a shows valid actions.'
            return
        if route.kind=='cell' and key in {'j','k'}:
            pair=self.focused_relation
            if not pair or self.playing_actor not in pair or pair[0]==pair[1]:
                self.notice='You are observing this pair. Choose your own row or column to act.'; return
            other = next(p for p in pair if p!=self.playing_actor)
            self.contact_to(other) if key=='j' else self.propose_to(other)
            return
        if key in {'c', 'i', '?', 't'}:
            self.push({'c': 'contracts', 'i': 'inbox', '?': 'help', 't': 'trajectory'}[key]); return
        if key == 'v':
            game = self.current()
            self.notice = 'Replay consistent: '+str(game.replay().get_world() == game.get_world()); return
        if key == 'w':
            self.open_network();return
        if key == 'z' and route.kind=='matrix':
            route.extra['numeric']=not route.extra.get('numeric',False);return
        if key in {'tab', 'backtab'}:
            if route.kind == 'network':
                route.region = 'explore' if route.region == 'canvas' else 'canvas'
            elif screen.entries:
                regions = ['explore', *(['decisions'] if screen.decisions else []),
                           *(['details'] if screen.lines else [])]
                index = regions.index(route.region) if route.region in regions else 0
                route.region = regions[(index + (1 if key == 'tab' else -1)) % len(regions)]
                if route.region == 'details' and not screen.details:
                    route.scroll = 0
            route.reveal = True
            return
        if route.kind=='network':
            if key=='S':
                labels=['Whole graph','Player-centred neighbourhood','Selected-actor neighbourhood','Contract neighbourhood','Invitation and connection network']
                choice=self.choose('NETWORK SCOPE',labels,str)
                if choice==labels[1]:route.target=self.playing_actor or route.target
                elif choice==labels[2]:route.target=self.picker('CENTRE ON PERSON',people(self.world()))['id']
                elif choice==labels[3]:
                    route.target=self.picker('CENTRE ON CONTRACT',[n for n in self.graph_projection()['nodes'] if n['kind']=='agreement'])['id']
                route.extra.update(scope='whole' if choice==labels[0] else 'connections' if choice==labels[4] else 'neighbourhood',scope_label=choice,offset=0)
                route.index=0;return
            if key=='L':
                selected=self.choose('NETWORK LAYER',['All layers',*CATEGORIES],str)
                route.extra['categories']=None if selected=='All layers' else [selected]
                route.extra['offset']=route.index=0;return
            if key=='3':route.extra['three_d']=not route.extra.get('three_d',False);return
            if key in {'{','}'}:
                if route.extra.get('three_d'):route.extra['pitch']=route.extra.get('pitch',0.)+(-.2 if key=='{' else .2)
                else:self.notice='3 enables the experimental yaw/pitch camera.'
                return
            if key in {'up','down'}:
                route.index=(route.index+(-1 if key=='up' else 1))%max(1,len(screen.entries))
                route.reveal = True
                return
            if key in {'[',']'}:
                limit=6 if self.width<85 or self.height<26 else 8
                route.extra['offset']=max(0,route.extra.get('offset',0)+(-limit if key=='[' else limit));route.index=0;return
            if key=='f' and screen.entries:
                route.target=screen.entries[route.index][1];route.index=0
                route.extra.update(offset=0,scope='neighbourhood',scope_label='Selected-object neighbourhood');return
            if key=='r':
                axis='yaw' if route.extra.get('three_d') else 'angle'
                route.extra[axis]=route.extra.get(axis,0.)+.3;return
            if key in {'+','-'}:
                route.extra['zoom']=max(.4,min(2.,route.extra.get('zoom',1.)*(1.2 if key=='+' else 1/1.2)));return
        if key == 'x':
            view = self.choose('ECOSYSTEM VIEWS', ['matrix', 'network', 'people', 'organisations', 'resources'], str.capitalize)
            if view == 'matrix':
                self.switch_mode('ecosystem')
            elif view=='network':self.open_network()
            else:
                self.push(view)
            return
        if key == '/':
            query = self.read('Search by first name or expertise domain (blank clears)')
            if route.kind == 'matrix':
                projection=matrix(self.world());roster=projection['actors'];kind=route.extra.get('matrix_kind','W')
                matches = [{**a,'axis':'actor'} for a in roster if folded(query) in folded(display_label(a))]
                matches += [{'id':code,'label':label,'axis':'domain'} for code,label in projection['vocabulary'].items()
                            if folded(query) in folded(label)]
                item = self.picker('FIND MATRIX PARTICIPANT / DOMAIN',matches)
                if item['axis']=='domain':
                    if kind=='W': route.extra['matrix_kind']='O'
                    route.column=projection['domains'].index(item['id'])
                else:
                    index=next(i for i,a in enumerate(roster) if a['id']==item['id'])
                    route.row=index
                    if kind=='W':route.column=index
            else:
                route.query = query; route.index = route.scroll = 0
            return
        if key == ':':
            self.typed_command(self.read('Command (? for help)')); return
        if key == 'd':
            if route.kind in {'cell','incidence'}:
                lines = []
                projection=matrix(self.world())
                if route.kind=='incidence':
                    observation=projection['observations'][route.target]['offer' if route.extra['matrix_kind']=='O' else 'need']
                    lines += [k.replace('_',' ')+': '+str(v) for k,v in observation['source'].items()]
                for row,column in (((route.row,route.column),(route.column,route.row)) if route.kind=='cell' else ()):
                    detail=cell(projection,row,column)
                    lines += [display_label(detail['provider'])+' → '+display_label(detail['requester'])]
                    for side in ('offer','need'):
                        observation=detail[side]
                        lines += [side.upper()]+[k.replace('_',' ')+': '+str(v) for k,v in observation['source'].items()]
                self.push('notice', title='OPTIONAL EXACT SOURCE REFERENCES', lines=lines)
            else:
                self.push('details', route.target)
            return
        if key == 'h':
            target = self.selected_target(screen)
            if target:
                self.push('history', target)
            else:
                self.notice = 'Inspect an object first to open its history.'
            return
        if key == 'a':
            self.act(screen); return
        if route.kind == 'gathering' and key in {'j', 'r'}:
            reason = self.command_availability('invite' if key == 'j' else 'respond')
            if reason:
                self.notice = reason
            else:
                lines = self.capture(lambda: self.invitation(respond=key == 'r'))
                self.notice = ' '.join(lines[-3:])
            return
        if route.kind == 'matrix':
            projection = getattr(self,'_matrix',matrix(self.world()));roster=projection['actors'];kind=route.extra.get('matrix_kind','W')
            if not roster:
                return
            if key in {'o', 'n'} and self.session:
                own = next((i for i, a in enumerate(roster) if a['id'] == self.session.actor), None)
                if own is not None:
                    if key == 'o': route.row = own
                    elif kind=='W': route.column = own
                else:
                    self.notice = 'This development role is outside the imported people matrix.'
            elif key in {'up', 'down'}:
                route.row = max(0, min(len(roster)-1, route.row+(-1 if key == 'up' else 1)))
            elif key in {'left', 'right'}:
                route.column = max(0, min((len(roster) if kind=='W' else len(projection['domains']))-1, route.column+(-1 if key == 'left' else 1)))
            elif key == 'enter':
                if kind!='W':
                    self.push('incidence',roster[route.row]['id'],domain=projection['domains'][route.column],matrix_kind=kind);return
                relation=(roster[route.row]['id'],roster[route.column]['id'])
                self.push('cell',relation=relation); self.route.row, self.route.column = self.stack[-2].row, self.stack[-2].column
            return
        if key in {'pageup', 'pagedown'}:
            route.scroll = max(0, route.scroll+(-1 if key == 'pageup' else 1)*max(1, self.height-10))
        elif key in {'up', 'down'}:
            step = -1 if key == 'up' else 1
            if route.region == 'decisions' and screen.decisions:
                route.decision_index = max(0,min(len(screen.decisions)-1,route.decision_index+step))
                route.reveal = True
            elif screen.entries and route.region != 'details':
                route.index = max(0, min(len(screen.entries)-1, route.index+step))
                route.reveal = True
            else:
                route.scroll = max(0, route.scroll+step)
        elif key == 'enter' and route.region == 'decisions' and screen.decisions:
            self.execute_action(screen.decisions[route.decision_index][1][1])
        elif key == 'enter' and route.region == 'details':
            self.notice = 'Reading details. Tab returns to selectable regions.'
        elif key == 'enter' and screen.entries:
            target = screen.entries[min(route.index, len(screen.entries)-1)][1]
            if route.kind == 'history':
                self.push('inspect', route.target, at=target)
            elif isinstance(target,tuple):
                kind,value=target
                if kind=='decision': self.execute_action(value)
                elif kind=='invite_to': self.contact_to(value)
                elif kind=='propose_to': self.propose_to(value)
                elif kind=='network_of': self.push('network',value)
                elif kind=='relation_to': self.push('cell',relation=value)
                elif kind=='choose_interaction':
                    target=self.picker('CHOOSE A PERSON',[a for a in people(self.world()) if a['id']!=self.playing_actor])['id']
                    self.propose_to(target) if value=='propose' else self.contact_to(target)
                else: self.push(*target)
            else:
                self.push('inspect', target)
        elif isinstance(key,str) and key.isdigit() and key != '0' and int(key) <= len(screen.entries):
            route.index = int(key)-1
            if route.kind != 'network':
                route.region = 'explore'
            self.handle('enter',screen)
        elif key not in {'enter', ''}:
            self.notice = 'Press ? for contextual help. Arrows select; Enter inspects.'

    def selected_target(self, screen):
        if self.route.kind == 'inspect':
            return self.route.target
        if self.route.kind == 'history':
            return self.route.target
        return screen.entries[min(self.route.index, len(screen.entries)-1)][1] if screen.entries else None

    def collect_action(self, candidate, game):
        template = game.get_world()['configuration']['world'].get('proposal')
        if candidate['kind'] != 'propose' or not template:
            return super().collect_action(candidate,game)
        # Frozen scenarios supply constraints and defaults, not silent consent
        # or a reason to bypass the player's contribution form.
        payload = {'kind':'propose',**deepcopy(template)}
        self.write('Proposing actor: '+self.label(self.session.actor))
        self.write('Counterparties: '+', '.join(self.label(p) for p in payload['parties'] if p != self.session.actor))
        payload['label'] = self.ask('Contract title?',default=payload['label'])
        payload['terms']['purpose'] = self.ask('Purpose of this agreement?',default=payload['terms']['purpose'])
        for obligation in payload['terms']['responsibilities']:
            prompt = 'Your offered contribution?' if obligation['actor_id'] == self.session.actor else 'Contribution requested from '+self.label(obligation['actor_id'])+'?'
            obligation['description'] = self.ask(prompt,default=obligation['description'])
        condition = self.ask('Optional conditions (blank for none)?',default='; '.join(payload['terms']['conditions']),parse=lambda value:value.strip())
        payload['terms']['conditions'] = [condition] if condition else []
        self.write('Governing policy: '+self.label(payload['policy_id']))
        for resource in payload['resources']:
            self.write('Scenario resource: '+self.label(resource['resource_id'])+f" × {resource['quantity']}")
        payload=self.refine_proposal(payload,game.get_world())
        self.write('Who is affected: '+', '.join(self.label(p) for p in payload['parties']))
        self.write('What will change: '+ACTION_EFFECTS['propose'])
        self.write('These are suggested terms. Other parties have not accepted them. Simulation only.')
        if not self.confirm('Continue?'):
            raise Cancelled
        return payload

    def refine_proposal(self,payload,world):
        context=self.contact_context()
        invitation=next((r.target for r in reversed(self.stack) if r.target in world['relationships']
                         and world['relationships'][r.target]['kind']=='contact_invitation'),None)
        if context or invitation:payload['interaction_context']={'relationship':context,'invitation_id':invitation}
        while True:
            choices=['Keep these settings', 'Change validity', 'Choose governance policy', 'Choose linked objective']
            selected=self.choose('AGREEMENT SETTINGS / Valid until '+payload['valid_until']+' / Policy: '+self.label(payload['policy_id'])+
                ' / Objective: '+self.label(payload['objective_id']),choices,str)
            if selected==choices[0]:return payload
            if selected==choices[1]:payload['valid_until']=self.ask('Valid until (ISO date and time with timezone)?',default=payload['valid_until'])
            elif selected==choices[2]:payload['policy_id']=self.picker('GOVERNANCE POLICY',list(world['governance'].values()))['id']
            else:payload['objective_id']=self.picker('LINKED OBJECTIVE',list(world['objectives'].values()))['id']

    def act(self, screen):
        if not self.session:
            self.notice = 'p Choose a simulated player before acting.'; return
        if self.route.extra.get('at'):
            self.notice = 'Historical views are read-only. b returns to current state.'; return
        target = self.selected_target(screen)
        if self.route.kind == 'cell':
            detail = self._cell
            if detail['self_pairing']:
                self.notice = 'Self-pairing is excluded from gameplay.'; return
            pair = [detail['provider']['id'], detail['requester']['id']]
            if self.session.actor not in pair:
                self.notice = 'Choose your own row or column to propose from this opportunity.'; return
            target = next(p for p in pair if p != self.session.actor)
        self.selected = target
        world = self.world()
        version, candidates = self.session.available_actions()
        if target in world['actors']:
            template = world['configuration']['world'].get('proposal')
            permitted = self.proposal_permitted(target)
            candidates = [c for c in candidates if c['kind'] == 'propose'] if target != self.session.actor and permitted else []
            if target != self.session.actor and world['actors'][target]['kind']=='person' and world['actors'][self.session.actor]['kind']=='person':
                candidates.append({'kind':'send_contact','recipient_id':target, 'context':self.contact_context()})
            self._proposal_target = target
        elif target in world['agreements']:
            candidates = [c for c in candidates if c.get('agreement_id') == target]
        elif target in world['relationships']:
            candidates = [c for c in candidates if c.get('invitation_id') == target]
        else:
            candidates = []
        if not candidates:
            self.notice = 'No action is permitted for this object, role and current lifecycle state.'; return
        action = self.choose('WHAT CAN I DO?', candidates, lambda c: ACTION_NAMES[c['kind']]+(' · '+c['response'] if c.get('response') else ''))
        self.execute_action(action,version=version)

    def contact_context(self):
        if not self.focused_relation: return {}
        projection=matrix(self.world());ids=[a['id'] for a in projection['actors']]
        if any(p not in ids for p in self.focused_relation):return {}
        provider,requester=self.focused_relation
        detail=cell(projection,ids.index(provider),ids.index(requester))
        return {'provider_id':provider,'requester_id':requester,'matching_codes':detail['matching_codes'],
                'source_version':projection['source_version'],'world_version':len(self.current().project('log'))}

    def contact_to(self, target):
        if not self.playing_actor or self.playing_actor==target:
            self.notice='Choose another person and a simulated player first.';return
        if self.route.extra.get('at') is not None:
            self.notice='Historical views are read-only.';return
        if self.world()['actors'].get(target,{}).get('kind')!='person' or self.world()['actors'][self.playing_actor]['kind']!='person':
            self.notice='Contact invitations currently require two simulated people.';return
        context=self.contact_context()
        if context:
            projection=matrix(self.world())
            self.write('Relevant declared domains: '+(', '.join(projection['vocabulary'][code] for code in context['matching_codes']) or 'None recorded'))
        self._proposal_target=target
        self.execute_action({'kind':'send_contact','recipient_id':target,'context':context})

    def propose_to(self, target):
        if not self.playing_actor or self.playing_actor==target:
            self.notice='Choose another person and a simulated player first.';return
        self._direct_proposal(target)

    def _direct_proposal(self,target):
        if self.route.extra.get('at') is not None:
            self.notice='Historical views are read-only.';return
        if not self.proposal_permitted(target):
            self.notice='A new proposal is unavailable for this role/counterparty and the registered scenario constraints.';return
        self._proposal_target=target
        self.execute_action({'kind':'propose'})

    def proposal_permitted(self,target):
        if not self.playing_actor or target==self.playing_actor:return False
        template=self.world()['configuration']['world'].get('proposal')
        if template:
            return template['id'] not in self.world()['agreements'] and {target,self.playing_actor}<=set(template['parties'])
        return target!='simulation-verifier' and self.playing_actor!='simulation-verifier'

    def execute_action(self, action, *, version=None):
        if not self.session or self.route.extra.get('at') is not None:
            self.notice='Actions require a simulated player in the current world.';return
        if version is None:version=len(self.current().project('log'))
        self.reset_buffer()
        if action['kind']=='send_contact' and action.get('context'):
            vocabulary=matrix(self.world())['vocabulary']
            self.write('Observed context: '+self.label(action['context']['provider_id'])+' → '+self.label(action['context']['requester_id']))
            self.write('Relevant declared domains: '+', '.join(vocabulary[c] for c in action['context']['matching_codes']))
        payload = self.collect_action(action, self.current())
        self.reset_buffer(); result = self.submit(payload, version)
        if result['ok']:
            self.post_action = False
            target = payload.get('agreement_id') or payload.get('id')
            if target in self.world()['agreements']:
                if payload['kind']=='propose' and self.focused_relation:
                    pair=set(payload['parties'])
                    context=next((i for i,r in reversed(list(enumerate(self.stack))) if r.kind=='cell' and set(r.extra.get('relation',()))<=pair),None)
                    if context is not None:
                        self.stack=self.stack[:context+1];self.route.extra['new_contract']=target
                    else:
                        other=next(p for p in payload['parties'] if p!=self.playing_actor)
                        self.push('cell',relation=(self.playing_actor,other),new_contract=target)
                elif self.route.kind == 'inspect' and self.route.target == target:
                    self.route.scroll = 0
                else:
                    self.push('inspect', target)
            if payload['kind'] in {'send_contact','draft_contact','publish_contact','respond_contact','withdraw_contact'}:
                invitation=payload.get('invitation_id') or payload.get('id')
                if self.route.kind!='inspect' or self.route.target!=invitation:self.push('inspect',invitation)
                self.route.index=self.route.scroll=0
                self.notice='INVITATION SENT · In-game delivery only.' if payload['kind']=='send_contact' else 'Invitation saved · Contact and contractual consent remain separate.'
            else:self.notice = 'Contract created · PROPOSED · acceptance is still required.' if payload['kind'] == 'propose' else 'Saved. Current-version acceptance and outcome verification remain separate.'
        else:
            self.notice = 'No state changed: '+', '.join(result['errors'])

    def typed_command(self, raw):
        from .commands import parse
        command, arg = parse(raw)
        if not command:
            self.notice = 'Unknown command. ? opens help.'; return
        name = command.name
        if name in MODES:
            self.resume_mode(name)
        elif name == 'paths':
            self.choose_mode()
        elif name in {'open', 'history', 'metadata', 'actions'}:
            target = resolve(self.world(), arg, selected=self.route.target) if arg else self.route.target
            if target is None:
                target = self.picker('CHOOSE AN OBJECT', self.graph_projection()['nodes'])['id']
            if name == 'actions':
                self.push('inspect', target)
                self.act(Screen('Action', entries=[('', target)]))
            else:
                self.push({'open': 'inspect', 'history': 'history', 'metadata': 'details'}[name], target)
        elif name == 'contracts' and arg:
            import shlex
            filters = dict(value.split('=',1) for value in shlex.split(arg))
            if set(filters)-{'actor','status','objective','resource'}:
                raise ValueError('unknown_contract_filter')
            for field in ('actor','objective','resource'):
                if field in filters:
                    found = resolve(self.world(),filters[field])
                    if found is None:
                        raise ValueError('ambiguous_or_unknown_filter_choose_a_unique_name')
                    filters[field] = found
            self.push('contracts',filters=filters)
        elif name in {'contracts', 'inbox', 'trajectory', 'help'}:
            self.push({'contracts': 'contracts', 'inbox': 'inbox', 'trajectory': 'trajectory', 'help': 'help'}[name])
        elif name == 'player': self.select_actor()
        elif name == 'connect':
            target=resolve(self.world(),arg) if arg else None
            if target not in self.world()['actors']:
                target=self.picker('WHOM WOULD YOU LIKE TO CONNECT WITH?', [a for a in people(self.world()) if a['id']!=self.playing_actor])['id']
            self.contact_to(target)
        elif name == 'back': self.back()
        elif name == 'quit': self.finished = True
        elif name == 'list': self.open_network()
        elif name == 'replay': self.handle('v', Screen('Replay'))
        elif name == 'search':
            if self.route.kind == 'matrix':
                roster = matrix(self.world())['actors']
                actor = self.picker('FIND MATRIX PARTICIPANT', [a for a in roster if folded(arg) in folded(display_label(a))])
                self.route.row = self.route.column = next(i for i,a in enumerate(roster) if a['id'] == actor['id'])
            else:
                self.route.query = arg; self.route.index = 0
        elif name == 'past':
            if not arg:
                self.push('history', self.route.target or self.picker('CHOOSE AN OBJECT', self.graph_projection()['nodes'])['id'])
            else:
                sequence, _, reference = arg.partition(' ')
                target = resolve(self.world(), reference, selected=self.route.target)
                if target is None:
                    target = self.picker('CHOOSE AN OBJECT', self.graph_projection()['nodes'])['id']
                self.push('inspect', target, at=int(sequence))
        elif name in {'invite', 'respond'}:
            reason = self.command_availability(name)
            if reason: self.notice = reason
            elif name == 'invite': self.invitation()
            else:
                pending = [r for r in self.world()['relationships'].values() if r['kind'] == 'invited'
                           and r['target_id'] == self.session.actor and r['status'] == 'proposed']
                if pending: self.invitation(respond=True)
                else: self.push('inbox')


class CursesViewport:
    """POSIX/ttyd viewport: bounded redraw, no growing transcript or raw ANSI input."""
    def __init__(self, window, *, plain=False):
        import curses
        self.curses, self.window, self.plain = curses, window, plain
        self.last_screen = None
        self.pairs={}
        window.keypad(True)
        curses.curs_set(0)
        self.colour=curses.has_colors() and not plain and 'NO_COLOR' not in os.environ
        if self.colour:
            curses.start_color(); curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            self.highlight = curses.color_pair(1) | curses.A_BOLD
        else:
            self.highlight = curses.A_BOLD

    def colour_style(self, foreground, background=None, bold=False):
        attribute=self.curses.A_BOLD if bold else 0
        if not self.colour:return attribute
        def index(value):
            if value is None:return -1
            rgb=[int(value[i:i+2],16) for i in (1,3,5)]
            if self.curses.COLORS>=256:
                levels=[0,95,135,175,215,255]
                r,g,b=(min(range(6),key=lambda j:abs(levels[j]-v)) for v in rgb)
                return 16+36*r+6*g+b
            return self.curses.COLOR_WHITE if sum(rgb)>360 else self.curses.COLOR_BLUE
        colours=(index(foreground),index(background))
        if colours not in self.pairs and len(self.pairs)+2<self.curses.COLOR_PAIRS:
            number=len(self.pairs)+2
            self.curses.init_pair(number,*colours);self.pairs[colours]=number
        return attribute | self.curses.color_pair(self.pairs.get(colours,1))

    def size(self):
        height, width = self.window.getmaxyx()
        return width, height

    def safe(self, value):
        value = clean(value)
        if self.plain:
            value = value.replace('→', '->').replace('–', '-').replace('·', '/').replace('…', '...')
            value = unicodedata.normalize('NFKD',value).encode('ascii', 'ignore').decode('ascii')
        return value

    def put(self, row, text, style=0):
        width, height = self.size()
        if 0 <= row < height:
            try:
                self.window.addnstr(row, 0, self.safe(text), max(0, width-1), style)
            except self.curses.error:
                pass  # A resize or bottom-right cell can invalidate a draw.

    def draw(self, screen, context='', notice=''):
        self.last_screen = screen
        width, height = self.size(); self.window.erase()
        self.put(0, screen.title, self.curses.A_BOLD)
        self.put(1, context)
        if screen.navigation:
            self.put(2, 'm Paths | e Ecosystem | g Gathering | s Scenarios | c Contracts | i Inbox | p Player')
        if screen.breadcrumb:self.put(3,screen.breadcrumb)
        body_start=4 if screen.breadcrumb else 3
        body_height = max(1, height-body_start-3)
        content, painted = [], []

        def add_line(line, style=0, *, raster=False, indent=''):
            safe = self.safe(line)
            rows = [safe] if raster else textwrap.wrap(safe, max(1,width-1),
                    replace_whitespace=False, subsequent_indent=indent) or ['']
            content.extend((row, style) for row in rows)

        for i, line in enumerate(screen.lines):
            start=len(content)
            add_line(line, self.highlight if i in screen.highlights else 0,
                     raster=screen.raster_start is not None)
            # Raster/heatmap rows are bounded to viewport width and never wrap.
            if len(content)==start+1:
                painted += [(start,column,length,fg,bg,bold) for row,column,length,fg,bg,bold in screen.styles if row==i]
        decision_starts = []
        if screen.split_regions:
            add_line('DECISIONS' + ('  <' if screen.region == 'decisions' else ''), self.curses.A_BOLD)
            if not screen.decisions:
                add_line('No decision available for this actor and state.')
            for i, (label, _) in enumerate(screen.decisions):
                decision_starts.append(len(content))
                selected = screen.region == 'decisions' and i == screen.decision_index
                add_line(('> ' if selected else '  ')+label, self.curses.A_REVERSE if selected else 0, indent='  ')
            add_line('EXPLORE' + ('  <' if screen.region == 'explore' else ''), self.curses.A_BOLD)
        entry_starts = []
        for i, (label, _) in enumerate(screen.entries if screen.show_entries else []):
            entry_starts.append(len(content))
            active = screen.region == 'explore' and i == screen.selected
            prefix = '> ' if active else '  '
            text=prefix+f'[{i+1}] '+label
            parts=textwrap.wrap(self.safe(text),max(1,width-1),subsequent_indent='      ') if screen.wrap_entries else [text]
            content.extend((part,self.curses.A_REVERSE if active else 0) for part in parts)
        detail_start = len(content)
        if screen.details:
            add_line('DETAILS' + ('  <' if screen.region == 'details' else ''), self.curses.A_BOLD)
            for line in screen.details:
                add_line(line)
        scroll = min(screen.scroll, max(0, len(content)-body_height))
        selected = None
        if entry_starts and screen.region == 'explore' and screen.reveal:
            selected = entry_starts[min(screen.selected,len(entry_starts)-1)]
        if screen.reveal and screen.region == 'decisions' and decision_starts:
            selected = decision_starts[min(screen.decision_index,len(decision_starts)-1)]
        if screen.reveal and screen.region == 'details' and screen.details:
            scroll = min(detail_start, max(0,len(content)-body_height))
        if selected is not None:
            if selected < scroll:
                scroll = selected
            elif selected >= scroll+body_height:
                scroll = selected-body_height+1
        for i, (line, style) in enumerate(content[scroll:scroll+body_height], body_start):
            self.put(i, line, style)
        for row,column,length,fg,bg,bold in painted:
            if scroll<=row<scroll+body_height:
                try:
                    text=content[row][0][column:column+length]
                    self.window.addnstr(row-scroll+body_start,column,text,length,self.colour_style(fg,bg,bold))
                except self.curses.error:pass
        if len(content) > body_height:
            self.put(height-3, f'Scroll {scroll+1}/{max(1,len(content)-body_height+1)} · PgUp/PgDn')
        self.put(height-2, notice, self.curses.A_BOLD)
        # Help lists the controls when a narrow terminal clips the footer.
        self.put(height-1, ('Esc/b Back  ? Help | ' if screen.navigation else '')+(screen.footer or 'Enter Continue'))
        self.window.refresh()
        return scroll

    def message(self, screen):
        self.draw(screen)

    def key(self):
        key = self.window.get_wch()
        mapping = {self.curses.KEY_UP: 'up', self.curses.KEY_DOWN: 'down', self.curses.KEY_LEFT: 'left',
                   self.curses.KEY_RIGHT: 'right', self.curses.KEY_NPAGE: 'pagedown', self.curses.KEY_PPAGE: 'pageup',
                   self.curses.KEY_RESIZE: 'resize', self.curses.KEY_ENTER: 'enter', '\n': 'enter', '\r': 'enter', '\x1b': 'esc'}
        mapping.update({self.curses.KEY_BTAB:'backtab','\t':'tab'})
        if key in {'\x03', '\x04'}:
            raise EOFError
        return mapping.get(key, key)

    def prompt(self, title, lines, context):
        value = ''
        while True:
            width, height = self.size()
            screen = Screen(title, list(lines)+['', '> '+value[-max(1,width-4):]], footer='Enter Confirm · Esc Cancel', navigation=False)
            screen.scroll = max(0, len(screen.lines)-(height-6))
            self.draw(screen, context)
            key = self.key()
            # Esc and the letter b must remain distinct while entering text.
            if key == 'enter': return value
            if key == 'resize': continue
            if key in {self.curses.KEY_BACKSPACE, '\x7f', '\b'}:
                value = value[:-1]
            elif key == 'esc': return None
            elif isinstance(key, str) and len(key) == 1 and key.isprintable():
                value += key

    def choose(self, title, items, label, context, *, preview=None):
        index = 0; query = ''; scroll = 0; region = 'explore'
        while True:
            filtered = [item for item in items if folded(query) in folded(label(item))]
            index = min(index, max(0, len(filtered)-1))
            lines = ['Search: '+query, f'{len(filtered)} choices']
            if region == 'details':
                lines += ['Up/Down selects an option in the list. Tab returns to choices.',
                          '/ changes search; Enter confirms the current choice.', 'Esc/b goes back.']
                if filtered:
                    lines += ['Selected: '+label(filtered[index])]
            self.draw(Screen(title, lines, [(label(item), item) for item in filtered],
                'Enter Confirm · Tab Regions · / Search · '+('v Preview · ' if preview else '')+'Esc/b Back',
                index, scroll if region == 'explore' else 0, navigation=False,
                show_entries=region == 'explore', reveal=region == 'explore'), context)
            key = self.key()
            if key in {'b', 'q', 'esc'}: raise Cancelled
            if key in {'tab', 'backtab', '?'}:
                region = 'details' if region == 'explore' else 'explore'
                continue
            if key == '/':
                value = self.prompt('Search by name or organisation', [], context)
                if value is not None:
                    query = value; index = scroll = 0
                    region = 'explore'
            elif key in {'up', 'down'}:
                index = max(0, min(len(filtered)-1, index+(-1 if key == 'up' else 1)))
                scroll = max(0, index-max(1,self.size()[1]-10))
            elif key in {'pageup', 'pagedown'}:
                index = max(0, min(len(filtered)-1, index+(-1 if key == 'pageup' else 1)*max(1,self.size()[1]-10)))
                scroll = max(0, index-max(1,self.size()[1]-10))
            elif key == 'enter' and filtered:
                return filtered[index]
            elif key == 'v' and preview and filtered:
                details = preview(filtered[index]); offset = 0
                while True:
                    shown = self.draw(Screen('PROFILE PREVIEW',details,footer='PgUp/PgDn Scroll · Enter or b Return',
                                             scroll=offset,navigation=False),context)
                    key = self.key()
                    if key in {'enter','b','esc','q'}: break
                    if key in {'pageup','pagedown','up','down'}:
                        step = max(1,self.size()[1]-8) if key in {'pageup','pagedown'} else 1
                        offset = max(0,shown+(-step if key in {'pageup','up'} else step))
            elif isinstance(key,str) and key.isdigit() and key != '0' and int(key) <= len(filtered):
                return filtered[int(key)-1]


def supported(source, output):
    if os.getenv('TERM', 'dumb') == 'dumb' or not source.isatty() or not output.isatty():
        return False
    try:
        import curses
        return bool(curses)
    except ImportError:
        return False


def run_fullscreen(game, *, store=None, plain=False, explore=False):
    import curses
    import locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        try:locale.setlocale(locale.LC_ALL,'en_US.UTF-8')
        except locale.Error:plain=True
    result = None
    def start(window):
        nonlocal result
        result = FullScreenTerminal(game, viewport=CursesViewport(window, plain=plain),
                                    store=store, plain=plain, explore=explore).run()
    curses.wrapper(start)
    return result
