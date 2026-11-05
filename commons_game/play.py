"""Player-facing terminal screens over existing projections and command rules."""
from collections import Counter
from copy import deepcopy
import json

from .catalogue import SimulationAuthority, affiliations, people
from .commands import contract_aliases, invitation_aliases, menu, parse, resolve
from .player import ActorSession
from .presentation import OBJECTS, Presentation, actor_label, display_label, folded, status
from .terminal_input import navigation
from .tui import ACTION_NAMES, EVENT_NAMES, Cancelled, Terminal

ACTION_EFFECTS = {
    'send_contact': 'Record a pending in-game contact invitation. No email is sent and no contract is created.',
    'draft_contact': 'Save an invitation draft. It is not delivered to the recipient.',
    'publish_contact': 'Send the draft to the recipient’s simulated inbox.',
    'respond_contact': 'Record your response. Acceptance acknowledges contact only; it accepts no obligations.',
    'withdraw_contact': 'Withdraw your pending contact request, retaining its history.',
    'propose': 'Create one proposed contract in the shared world. The other parties have not accepted it.',
    'accept': 'Record your simulated acceptance of this exact version. Other parties must still decide for themselves.',
    'amend': 'Create revised terms and clear current-version acceptance and authorisation. Previous versions remain in history.',
    'authorize': 'Record the additional approval permitted by this role. This does not replace each party\'s acceptance.',
    'activate': 'Activate the accepted agreement, reserve its resources and create the agreed responsibilities.',
    'initiate': 'Record evidence that work has started. This does not report completion.',
    'fulfill': 'Report completion against the agreed criteria. Independent verification is still required.',
    'verify': 'Record the designated independent review of reported evidence. Only simulation outcomes are affected.',
    'reject': 'Decline this proposal. The contract remains visible in history.',
    'withdraw': 'Withdraw this unactivated agreement while retaining its history.',
    'terminate': 'Close the contract and release held resources.',
    'suspend': 'Suspend further execution pending resolution; held resources remain reserved.',
    'resume': 'Resume the suspended agreement under the existing rules.',
    'dispute': 'Record a dispute; the agreement and its evidence remain inspectable.',
    'publish_proposal': 'Make this drafted agreement available for party responses.',
}


class PlayableTerminal(Terminal):
    def __init__(self, game, **options):
        super().__init__(game,**options)
        self.view = Presentation(self.output,plain=self.plain)
        self.authority = SimulationAuthority()
        self.selected = None
        self.finished = False
        self.mode_name = 'ecosystem'
        self.screen = 'explorer'
        self.query = ''
        self.kind_filter = None
        self.focus_actor = None
        self.post_action = False
        self.splash_done = False
        self._proposal_target = None
        self.refresh()

    def refresh(self):
        """One consistent read-only display frame; writes still go to the store."""
        self._frame_game=self.store.load() if self.store else self.game
        self._frame_world=self._frame_game.get_world()
        self._frame_graph=None
        self._frame_aliases={value:key for key,value in {**contract_aliases(self._frame_world),**invitation_aliases(self._frame_world)}.items()}

    def current(self):
        return getattr(self,'_frame_game',None) or super().current()

    def world(self):
        return self._frame_world

    def graph_projection(self):
        if self._frame_graph is None:self._frame_graph=self.current().project('network')
        return self._frame_graph

    def write(self, value=''):
        self.view.write(value)

    def nav(self):
        self.write('>')
        return navigation(self.source,self.output)

    def context(self, *, at=None):
        world = self.world()
        actor = actor_label(world,self.session.actor) if self.session else 'No role selected'
        state = len(self.current().project('log'))
        return f"{world['configuration']['world']['title']} · Playing: {actor}\nSIMULATION ONLY · " + (f'HISTORICAL STATE {at} (current {state})' if at is not None else f'CURRENT STATE {state}')

    def aliases(self):
        return self._frame_aliases

    def node(self, node_id, *, at=None):
        graph=self.current().project('network',at=at) if at is not None else self.graph_projection()
        return next((n for n in graph['nodes'] if n['id']==node_id),None)

    def label(self, node_id, world=None):
        world = world or self.world()
        for table in ('actors','agreements','objectives','resources','governance','capacities','needs','evidence','relationships'):
            record = world[table].get(node_id)
            if record:
                if table=='actors':return actor_label(world,node_id)
                return display_label(record)
        return 'Unresolved source reference'

    def show_node(self, node, prefix=''):
        self.view.node(node,prefix=prefix,alias=self.aliases().get(node['id']))

    def picker(self, title, items, *, render=None, preview=None):
        """Number, cursor and search selection share one testable boundary."""
        index = 0; query = ''; page_size = max(4,min(12,(self.view.width//8)+2))
        while True:
            self.refresh()
            filtered = [item for item in items if folded(query) in folded(render(item) if render else display_label(item))]
            index = min(index,max(0,len(filtered)-1)); start = (index//page_size)*page_size
            self.view.heading(title,self.context())
            if query:
                self.write('Search: '+query)
            for i,item in enumerate(filtered[start:start+page_size],start+1):
                prefix = ('> ' if i-1==index else '  ')+f'[{i}] '
                if render and isinstance(item,dict) and item.get('kind') in OBJECTS:
                    self.show_node({**item,'label':render(item)},prefix)
                elif render:
                    self.write(prefix+render(item))
                else:
                    self.show_node(item,prefix)
            self.write(f'{len(filtered)} matches · page {start//page_size+1} / {max(1,(len(filtered)+page_size-1)//page_size)}')
            self.write('↑↓ Select · Enter Confirm · number Select · / Search · > Next · < Previous · v Preview · b Back')
            raw = self.nav()
            if raw in {'b','q','0'}:
                raise Cancelled
            if raw in {'down','j'}:
                index = min(len(filtered)-1,index+1); continue
            if raw in {'up','k'}:
                index = max(0,index-1); continue
            if raw in {'next','>'}:
                index = min(max(0,len(filtered)-1),index+page_size); continue
            if raw in {'prev','<'}:
                index = max(0,index-page_size); continue
            if raw.startswith('/'):
                query = raw[1:].strip() or self.ask('Search by name?'); index=0; continue
            if raw == '?':
                self.write('Numbers refer to the visible ordered catalogue. Search is accent-insensitive. No internal identifier is needed.'); continue
            if raw == 'v' and preview and filtered:
                preview(filtered[index]); self.read('Enter to return to selection'); continue
            try:
                chosen = int(raw)-1 if raw else index
                if not 0<=chosen<len(filtered):
                    raise ValueError
                return filtered[chosen]
            except ValueError:
                self.write('Choose a visible number, move the cursor, or search by name.')

    def choose(self, prompt, items, label=str):
        if not items:
            self.write('No matching choices are available in the current world.'); raise Cancelled
        return self.picker(prompt,items,render=label)

    def select_actor(self):
        self.refresh();world=self.world()
        organisation = ''; development = False
        while True:
            actors = people(world,organisation=organisation,development=development)
            self.view.heading('WHO WILL YOU PLAY?',self.context())
            self.write('Choose a person to simulate. This is perspective selection, not authentication or authority from Notion.')
            if not actors:
                self.write('No eligible imported people match. Clear the filter or import a scoped ecosystem snapshot.')
            self.write('[Enter] Open people catalogue · f Filter by organisation · d Development roles · b Back')
            raw = self.nav()
            if raw in {'b','q','0'}:
                raise Cancelled
            if raw == 'f':
                organisation = self.read('Organisation name (blank clears)?'); continue
            if raw == 'd':
                development = not development
                self.write('Development roles include organisations and synthetic support roles. They confer simulation authority only.'); continue
            # A direct number or /query also works without an extra confirmation.
            if raw and raw not in {'people','?'}:
                if raw.startswith('/'):
                    actors = people(world,search=raw[1:],organisation=organisation,development=development)
                elif raw.isdigit() and 0<int(raw)<=len(actors):
                    selected = actors[int(raw)-1]
                    self.assume_actor(selected); return
                else:
                    self.write('Enter opens the catalogue. f filters organisation; d explicitly enables development roles.'); continue
            try:
                selected = self.picker('SELECT AN ACTOR',actors,render=lambda a:display_label(a)+
                    (' · '+', '.join(affiliations(world,a['id'])) if affiliations(world,a['id']) else ' · Affiliation unknown'),
                    preview=lambda a:self.inspect_node(a['id']))
                self.assume_actor(selected); return
            except Cancelled:
                continue

    def assume_actor(self, actor):
        if actor['kind']=='organisation' and not self.confirm('Explicitly simulate this organisation role? No real representation authority is granted.'):
            raise Cancelled
        identity,binding = self.authority.assume(actor,organisation_confirmed=actor['kind']=='organisation')
        self.session = ActorSession(self.game,actor['id'],store=self.store,identity=identity,binding=binding,provider=self.authority)
        self.identity = identity
        self.write('NOW SIMULATING: '+display_label(actor)+'. The shared world is unchanged.')

    def coverage(self):
        world=self.world()
        imported = [a for a in world['actors'].values() if a.get('provenance',{}).get('kind')=='notion_snapshot' and a['kind']=='person']
        summary = world['configuration'].get('ecosystem-coverage',{}).get('summary')
        if summary:
            self.write(f"Coverage: {summary.get('eligible_people',0)} eligible source people / {len(imported)} imported people; "
                       f"{summary.get('unresolved_identity_count',0)} unresolved source identities.")
            supplements=sum(a.get('provenance',{}).get('kind')!='notion_snapshot' for a in world['actors'].values())
            if supplements:self.write(f'{supplements} synthetic support roles are supplementary, not source participants.')
        elif not world['configuration']['world'].get('synthetic',True):
            self.write(f'World coverage: {len(imported)} imported people. Complete source coverage has not been recorded.')

    def visible_nodes(self):
        world=self.world();nodes=self.graph_projection()['nodes']
        if self.focus_actor:
            ids = {a['id'] for a in world['agreements'].values() if self.focus_actor in a['parties']}
            nodes = [n for n in nodes if n['id'] in ids]
        elif self.kind_filter:
            nodes = [n for n in nodes if n['kind']==self.kind_filter]
        else:
            nodes = [n for n in nodes if n['kind'] not in {'capacity','need','evidence'}]
        order = list(OBJECTS)
        return sorted([n for n in nodes if folded(self.query) in folded(display_label(n))],
                      key=lambda n:(order.index(n['kind']) if n['kind'] in order else 99,folded(display_label(n)),n['id']))

    def run(self):
        try:
            if not self.splash_done:
                self.splash()
            if not self.explore and not self.session:
                self.select_actor()
            self.explorer()
        except (EOFError,Cancelled,KeyboardInterrupt):
            self.write('Session closed. Accepted history is preserved.')
        return self.current()

    def splash(self):
        import textwrap
        width=max(20,min(46,self.view.width-2))
        plain=self.view.plain
        self.write(('+' if plain else '╔')+('-' if plain else '═')*width+('+' if plain else '╗'))
        for title in ('','SADDLE PATHWAYS','THE COMMONS GAME','','I hereby declare the right of the commons.',''):
            for line in textwrap.wrap(title,width=width) or ['']:
                self.write(('|' if plain else '║')+line.center(width)+('|' if plain else '║'))
        self.write(('+' if plain else '╚')+('-' if plain else '═')*width+('+' if plain else '╝'))
        self.write('SIMULATION MODE ONLY')

    def explorer(self):
        index = 0; page_size = 12
        while not self.finished:
            self.refresh()
            self.screen='explorer'; nodes = self.visible_nodes()
            index = min(index,max(0,len(nodes)-1)); start=index//page_size*page_size
            self.view.heading(self.mode_name.upper()+' / WORLD EXPLORER',self.context())
            self.coverage()
            world = self.current().get_world()
            if self.mode_name=='gathering' and not any(o['mode']=='gathering' for o in world['objectives'].values()):
                self.write('This world has no gathering objective. Invitation actions explain that restriction; exploration and contracts remain available.')
            if self.post_action:
                self.write('CONTRACT CREATED · [1] Inspect contract · [2] View in graph · [3] Return to ecosystem')
            else:
                self.write('Modes: ecosystem · gathering · scenarios · Clear filter: list')
            previous_kind=None
            for i,node in enumerate(nodes[start:start+page_size],start+1):
                if previous_kind!=node['kind']:
                    self.write('\n'+OBJECTS.get(node['kind'],OBJECTS['evidence']).plural.upper());previous_kind=node['kind']
                self.show_node(node,('> ' if i-1==index else '  ')+f'[{i}] ')
            if not nodes:
                self.write('No objects match this view. Use list to clear filters.')
            self.write(f'Page {start//page_size+1}/{max(1,(len(nodes)+page_size-1)//page_size)} · {len(nodes)} objects')
            self.footer()
            raw = self.nav()
            if self.post_action and raw in {'1','2','3'}:
                self.post_action=False
                if raw in {'1','2'}:
                    self.inspector(self.last_contract)
                continue
            self.post_action=False
            if raw in {'up','k','down','j','next','>','prev','<'}:
                delta={'up':-1,'k':-1,'down':1,'j':1,'next':page_size,'>':page_size,'prev':-page_size,'<':-page_size}[raw]
                index=max(0,min(max(0,len(nodes)-1),index+delta));continue
            if raw=='' or raw.isdigit():
                chosen = int(raw)-1 if raw else index
                if 0<=chosen<len(nodes):
                    self.selected=nodes[chosen]['id']; self.inspector(self.selected)
                else:
                    self.write('Choose a displayed number or search with /.')
                continue
            self.selected = nodes[index]['id'] if nodes else None
            self.dispatch(raw)

    def footer(self):
        shortcuts={'paths':'m','ecosystem':'e','gathering':'g','scenarios':'s','actions':'a','contracts':'c',
                   'inbox':'i','player':'p','history':'h','help':'?','back':'Esc/b','quit':'q'}
        self.write('\n↑↓ Select · Enter Inspect · / Search · '+ ' · '.join(shortcuts[c.name]+' '+c.description
                   for c in menu(self.screen) if c.name in shortcuts))

    def dispatch(self, raw):
        self.refresh()
        command,arg = parse(raw)
        if not command or self.screen not in command.screens:
            self.write('Unknown command. Press ? for commands available on this screen.'); return
        try:
            reason=getattr(self,command.availability)(command.name)
            if reason:
                self.write(command.name.upper()+' · '+reason);return
            if raw.casefold()=='contract history':
                arg=self.select_reference(contracts_only=True)
            return getattr(self,command.handler)(arg)
        except Cancelled:
            self.write('Cancelled. No incomplete action was submitted.')
        except (ValueError,RuntimeError) as error:
            self.write('Unavailable: '+str(error).replace('_',' ')+'.')

    def command_availability(self,name):
        world=self.current().get_world()
        if name in {'actions','inbox','invite','respond','connect'} and not self.session:
            return 'Select a simulated player with p first.'
        if name=='invite' and not any(o['mode']=='gathering' for o in world['objectives'].values()):
            return 'Not available in this scenario. A registered invitation requires a gathering objective; this world has none.'
        return None

    def select_reference(self, arg='', *, contracts_only=False):
        world=self.current().get_world()
        if arg:
            resolved=resolve(world,arg,selected=self.selected)
            if resolved and (not contracts_only or resolved in world['agreements']):
                return resolved
        elif self.selected and (not contracts_only or self.selected in world['agreements']):
            return self.selected
        nodes=self.current().project('network')['nodes']
        if contracts_only:
            nodes=[n for n in nodes if n['kind']=='agreement']
        if arg and arg.casefold() not in {'latest','latest contract'}:
            candidates=[n for n in nodes if folded(arg) in folded(display_label(n))]
            if candidates:nodes=candidates
        if not nodes:
            self.write('No contracts exist yet.' if contracts_only else 'No matching object exists.');raise Cancelled
        return self.picker('CHOOSE AN OBJECT',nodes)['id']

    def inspector(self, node_id):
        index=0;page_size=10;parents=[]
        while not self.finished:
            self.refresh()
            self.screen='inspector';self.selected=node_id
            self.inspect_node(node_id)
            neighbours=self.neighbours(node_id)
            self.write('\nGRAPH NEIGHBOURHOOD / CONNECTED OBJECTS')
            index=min(index,max(0,len(neighbours)-1));start=index//page_size*page_size
            for i,node in enumerate(neighbours[start:start+page_size],start+1):
                decorated={**node,'label':node['label']+(' · '+node['_relationship_label'] if node.get('_relationship_label') else '')}
                self.show_node(decorated,('> ' if i-1==index else '  ')+f'[{i}] ')
            self.write(f'Connected objects page {start//page_size+1}/{max(1,(len(neighbours)+page_size-1)//page_size)} · > Next · < Previous')
            self.footer()
            raw=self.nav()
            if self.post_action and raw in {'1','2','3'}:
                self.post_action=False
                if raw=='3':return
                node_id=self.last_contract;continue
            self.post_action=False
            if raw in {'b','0','q'}:
                if raw=='q':self.finished=True
                elif parents:
                    node_id,index=parents.pop()
                    continue
                return
            if raw in {'up','k','down','j','next','>','prev','<'}:
                delta={'up':-1,'k':-1,'down':1,'j':1,'next':page_size,'>':page_size,'prev':-page_size,'<':-page_size}[raw]
                index=max(0,min(max(0,len(neighbours)-1),index+delta));continue
            if raw.isdigit() and 0<int(raw)<=len(neighbours):
                parents.append((node_id,int(raw)-1))
                node_id=neighbours[int(raw)-1]['id'];index=0;continue
            if raw=='':
                if neighbours:
                    parents.append((node_id,index))
                    node_id=neighbours[index]['id'];index=0
                else:self.write('No connected objects. a shows actions; b returns.')
                continue
            outcome=self.dispatch(raw)
            if outcome=='back':return

    def neighbours(self,node_id):
        from .projections import neighbourhood
        graph=neighbourhood(self.graph_projection(),node_id)
        nodes=[n for n in graph['nodes'] if n['id']!=node_id]
        for node in nodes:
            kinds={edge['kind'] for edge in graph['edges'] if node['id'] in (edge['source_id'],edge['target_id'])}
            if kinds=={'potential_complementarity'}:node['_relationship_label']='INFERRED POTENTIAL'
        return nodes

    def inspect_node(self, node_id, *, at=None):
        game=self.current();world=game.world_at(event=at) if at is not None else self.world()
        node=self.node(node_id,at=at)
        if not node:raise ValueError('object_not_present_at_this_state')
        self.view.heading('INSPECT / '+OBJECTS.get(node['kind'],OBJECTS['evidence']).label,self.context(at=at))
        self.show_node(node)
        if node['kind']=='agreement':
            version=node['versions'][node['current_version']-1]
            self.write('Proposed by: '+self.label(node['created_by'],world))
            self.write('Parties: '+', '.join(self.label(p,world) for p in node['parties']))
            self.write('Proposing does not accept the terms. Each party decides independently.')
            for party in node['parties']:
                role='Proposer' if party==node['created_by'] else 'Counterparty'
                receipt='accepted' if party in version['acceptances'] else 'no acceptance recorded'
                self.write(f'{role}: {self.label(party,world)} · {receipt}')
            self.write('Linked objective: '+self.label(node['objective_id'],world))
            self.write('\nTERMS\n'+version['terms']['purpose'])
            for responsibility in version['terms']['responsibilities']:
                self.write('  '+self.label(responsibility['actor_id'],world)+': '+responsibility['description'])
            for condition in version['terms']['conditions']:self.write('  Condition: '+condition)
            self.write('Accepted by: '+(', '.join(self.label(p,world) for p in version['acceptances']) or 'No parties yet'))
            self.write('Terms version: '+str(version['number']))
            self.write('Authorised by: '+(', '.join(self.label(p,world) for p in version['authorizations']) or 'No additional approvals recorded'))
            policy=world['governance'][version['policy_id']]
            self.write('Governing policy (governance-policy node): '+policy['label'])
            self.write('Every party must explicitly accept this version. Policy approvals are additional to party consent.')
            self.write('Required approvals: '+str(policy['threshold'])+'; named approvers: '+(', '.join(self.label(p,world) for p in policy['required_actors']) or 'none'))
            self.write('Designated independent reviewers: '+', '.join(self.label(p,world) for p in version['verification']['verifier_ids']))
            for resource in version['resources']:self.write('Resource: '+self.label(resource['resource_id'],world)+f" × {resource['quantity']}")
            self.write('Evidence: '+str(len(node['evidence_ids']))+' record(s).')
            for evidence_id in node['evidence_ids']:
                evidence=world['evidence'][evidence_id]
                self.write('  '+evidence['kind'].replace('_',' ')+': '+evidence['reference'])
            for commitment in world['commitments'].values():
                if commitment['agreement_id']==node_id:
                    self.write('Obligation: '+self.label(commitment['actor_id'],world)+' · '+status(commitment['status']))
        elif node['kind']=='invitation':
            self.write('From: '+self.label(node['source_id'],world)+' · To: '+self.label(node['target_id'],world))
            self.write('Status: '+status(node['status']))
            self.write(node['message'])
            if node.get('purpose'):self.write('Purpose: '+node['purpose'])
            if node.get('response'):self.write('Response: '+node['response']['decision']+' · '+node['response']['message'])
            self.write('A simulated contact request. Acceptance acknowledges contact, never contractual obligations or real-world consent.')
        elif node_id in world['actors']:
            self.write('Affiliation: '+(', '.join(affiliations(world,node_id)) or 'Unknown / not recorded'))
            for table in ('capacities','needs'):
                self.write('\n'+table.upper())
                records=[r for r in world[table].values() if r['actor_id']==node_id]
                for record in records:self.show_node({**record,'kind':'capacity' if table=='capacities' else 'need','label':record['domain']})
                if not records:self.write('Not recorded. This does not mean none.')
            self.write('\nRECORDED RELATIONSHIPS')
            for relation in world['relationships'].values():
                if node_id in (relation['source_id'],relation['target_id']):
                    other=relation['target_id'] if relation['source_id']==node_id else relation['source_id']
                    self.write(relation['kind'].replace('_',' ')+' · '+self.label(other,world)+' · '+relation.get('status','unknown'))
            self.write('\nPOTENTIAL COMPLEMENTARITIES / INFERRED, NOT COLLABORATION')
            potentials=[p for p in game.derive_possibilities(world) if node_id in (p['source_id'],p['target_id'])]
            grouped=Counter(p['target_id'] if p['source_id']==node_id else p['source_id'] for p in potentials)
            for other,count in grouped.most_common(8):self.write(self.label(other,world)+f' · {count} declared-domain match(es)')
            self.write('\nCONTRACTS')
            for agreement in world['agreements'].values():
                if node_id in agreement['parties']:self.show_node({**agreement,'kind':'agreement'})
        elif node['kind']=='policy':
            self.write('GOVERNANCE POLICY / RULE ENFORCED')
            self.write('Every party accepts the same contract version before activation. An amendment clears current-version receipts.')
            self.write(f"Additional approval threshold: {node['threshold']}")
            self.write('Required approvers: '+(', '.join(self.label(p,world) for p in node['required_actors']) or 'None'))
            self.write('Eligible approvers: '+(', '.join(self.label(p,world) for p in node['eligible_actors']) or 'None'))
            self.write('Required categories: '+(', '.join(node['required_categories']) or 'None'))
            self.write('These rules confer no real-world authorisation in a simulation.')
        else:
            for field in ('domain','quantity','unit','status','reference','label'):
                if field in node and field!='label':self.write(field.replace('_',' ').capitalize()+': '+('Unknown' if node[field] is None else str(node[field])))
        self.write('\nProvenance: '+('Source assertion; unverified' if node.get('provenance',{}).get('kind')=='notion_snapshot' else 'Recorded simulation / fixture'))
        self.write('Source details: metadata (optional).')

    def cmd_open(self,arg):
        node_id=self.select_reference(arg);self.selected=node_id;self.inspector(node_id)

    def cmd_list(self,arg):
        kinds={style.plural.casefold():kind for kind,style in OBJECTS.items()}
        self.kind_filter=kinds.get(arg.casefold());self.query='';self.focus_actor=None
        return 'back' if self.screen!='explorer' else None

    def cmd_contracts(self,arg):
        self.query='';self.kind_filter='agreement';self.focus_actor=None
        world=self.current().get_world()
        if not arg and self.selected in world['actors']:self.focus_actor=self.selected
        if arg:
            from .projections import contract_registry
            filters=dict(value.split('=',1) for value in arg.split())
            for field in ('actor','objective','resource'):
                if field in filters:
                    filters[field]=resolve(world,filters[field]) or filters[field]
            contracts=contract_registry(world,**filters)
            if not contracts:self.write('No contracts match these filters.');return
            chosen=self.picker('CONTRACT REGISTRY',[{**a,'kind':'agreement'} for a in contracts]);self.inspector(chosen['id']);return
        contracts=[a for a in world['agreements'].values() if not self.focus_actor or self.focus_actor in a['parties']]
        if not contracts:self.write('No contracts yet for this selection. Use a on a person to propose an agreement.');return
        chosen=self.picker('CONTRACT REGISTRY',[{**a,'kind':'agreement'} for a in contracts]);self.inspector(chosen['id'])

    def cmd_actions(self,arg):
        if not self.session:
            self.write('Choose a simulated player with p before acting.');return
        world=self.current().get_world();target=resolve(world,arg,selected=self.selected) if arg else self.selected
        if arg and not target:target=self.select_reference(arg)
        self._proposal_target=target if target in world['actors'] and target!=self.session.actor else None
        version,candidates=self.session.available_actions()
        if target in world['agreements']:candidates=[c for c in candidates if c.get('agreement_id')==target]
        elif target in world['actors']:
            self._proposal_target=target if target!=self.session.actor else None
            candidates=[c for c in candidates if c['kind']=='propose']
            if target!=self.session.actor and world['actors'][target]['kind']=='person' and world['actors'][self.session.actor]['kind']=='person':
                candidates.append({'kind':'send_contact','recipient_id':target})
        elif target in world['relationships']:
            candidates=[c for c in candidates if c.get('invitation_id')==target]
        if not candidates:
            self.write('No action is permitted for this actor on the selected object in its current state. Inspect its parties, lifecycle and pending conditions; changing perspective does not bypass the engine.');return
        candidate=self.choose('WHAT CAN I DO?',candidates,lambda c:ACTION_NAMES[c['kind']]+(' · '+c['response'] if c.get('response') else '')+(' · '+self.label(c['agreement_id']) if c.get('agreement_id') else ''))
        payload=self.collect_action(candidate,self.current());self.submit(payload,version)

    def collect_action(self,candidate,game):
        world=game.get_world();kind=candidate['kind']
        if kind in {'send_contact','draft_contact'}:
            target=world['actors'].get(candidate.get('recipient_id') or self._proposal_target)
            if not target or target['id']==self.session.actor:
                target=self.picker('WHOM WOULD YOU LIKE TO CONNECT WITH?',[a for a in people(world) if a['id']!=self.session.actor])
            self.write('Simulating: '+self.label(self.session.actor)+' → '+self.label(target['id']))
            self.write('An invitation proposes contact. It imposes no obligation.')
            payload={'kind':kind,'id':f'contact-{len(world["actions"])+1:06}', 'recipient_id':target['id'],
                     'message':self.ask('Invitation message?',default='Would you like to explore a possible collaboration?'),
                     'purpose':self.ask('Optional invitation purpose (blank for none)?',default='',parse=lambda value:value.strip())}
            if candidate.get('context'):payload['context']=deepcopy(candidate['context'])
            if kind=='send_contact':
                delivery=self.choose('INVITATION DELIVERY', ['Send now','Save draft'],str)
                if delivery=='Save draft':kind=payload['kind']='draft_contact'
        elif kind in {'publish_contact','withdraw_contact','respond_contact'}:
            payload=deepcopy(candidate)
            if kind=='respond_contact':
                payload['response_message']=self.ask('Optional response message (blank for none)?',default='',parse=lambda value:value.strip())
        elif kind=='propose':
            template=world['configuration']['world']['proposal']
            if template:
                payload={'kind':kind,**deepcopy(template)}
            else:
                target=world['actors'].get(self._proposal_target)
                if not target or target['id']==self.session.actor:
                    choices=[a for a in people(world) if a['id']!=self.session.actor]
                    target=self.picker('WHO WOULD YOU LIKE TO COLLABORATE WITH?',choices)
                objectives=list(world['objectives'].values())
                objective=objectives[0]
                if len(objectives)>1 and self.confirm('Link this agreement to a wider scenario objective?'):
                    objective=self.choose('OPTIONAL WIDER OBJECTIVE',objectives,lambda o:o['label'])
                parties=[self.session.actor,target['id']]
                self.write('Proposing actor: '+self.label(self.session.actor))
                self.write('Counterparty: '+self.label(target['id']))
                title=self.ask('Contract title?',default='A proposed collaboration')
                purpose=self.ask('Purpose of this agreement?',default=title)
                offered=self.ask('Your offered contribution?',default='Discuss and review the proposed collaboration')
                requested=self.ask('Contribution requested from '+self.label(target['id'])+'?',default='Review and negotiate the requested contribution')
                condition=self.ask('Optional conditions (blank for none)?',default='',parse=lambda value:value.strip())
                resources=[]
                if world['resources'] and self.confirm('Include a resource allocation?'):
                    resource=self.choose('OPTIONAL RESOURCE',list(world['resources'].values()),display_label)
                    quantity=self.ask('Requested quantity?',default=1,parse=self.positive)
                    resources=[{'resource_id':resource['id'],'quantity':quantity}]
                payload={'kind':kind,'id':f'contract-{len(world["agreements"])+1:04}',
                    'label':title,
                    'parties':parties,'objective_id':objective['id'],
                    'terms':{'purpose':purpose,
                        'responsibilities':[{'actor_id':parties[0],'description':offered},{'actor_id':parties[1],'description':requested}],
                        'conditions':['Simulation only. No real-world consent or institutional obligation.']+([condition] if condition else [])},
                    'resources':resources,'valid_until':'2026-12-01T00:00:00+00:00','policy_id':'simulation-personal',
                    'verification':{'verifier_ids':['simulation-verifier'],'independent':True,
                                    'criteria':['Agreed responsibilities independently reviewed against supplied evidence']}}
        else:
            payload=deepcopy(candidate)
            agreement=world['agreements'][candidate['agreement_id']]
            current=agreement['versions'][agreement['current_version']-1]
            if kind=='amend':
                terms=deepcopy(current['terms']);terms['purpose']=self.ask('Revised shared purpose?',default=terms['purpose'])
                for responsibility in terms['responsibilities']:
                    responsibility['description']=self.ask('Proposed contribution from '+self.label(responsibility['actor_id'])+'?',default=responsibility['description'])
                condition=self.ask('Conditions for this revision?',default='; '.join(terms['conditions']))
                terms['conditions']=[condition] if condition else []
                payload['terms']=terms
            if kind in {'initiate','fulfill','verify'}:
                if kind=='fulfill':
                    for criterion in current['verification']['criteria']:
                        if not self.confirm('Does your report address: '+criterion+'?'):raise Cancelled
                    payload['criteria']=deepcopy(current['verification']['criteria'])
                payload['reference']=self.ask('Describe the supplied evidence or action record?')
            if kind in {'reject','withdraw','terminate','suspend','dispute'}:payload['reason']=self.ask('Reason?')
        if kind=='propose':payload=self.refine_proposal(payload,world)
        self.view.heading('ACTION: '+ACTION_NAMES[kind],self.context())
        affected=payload.get('parties',world['agreements'].get(payload.get('agreement_id'),{}).get('parties',[]))
        if kind in {'send_contact','draft_contact'}:affected=[self.session.actor,payload['recipient_id']]
        elif kind in {'respond_contact','publish_contact','withdraw_contact'}:
            item=world['relationships'][payload['invitation_id']];affected=[item['source_id'],item['target_id']]
        self.write('Who is affected: '+', '.join(self.label(p) for p in affected))
        self.write('What will change: '+ACTION_EFFECTS[kind])
        self.write('This simulated action is not genuine consent by the represented person.')
        if not self.confirm('Continue?'):raise Cancelled
        return payload

    def refine_proposal(self,payload,world):
        """Presentation hook; line-mode retains its reproducible default form."""
        return payload

    def submit(self,payload,version):
        result=self.session.submit(payload,expected_version=version)
        self.refresh()
        if result['ok']:
            target=payload.get('agreement_id') or payload.get('id')
            self.view.heading('CONTRACT CREATED' if payload['kind']=='propose' else 'SHARED WORLD UPDATED',self.context())
            if target in self.current().get_world()['agreements']:
                self.last_contract=target;self.selected=target;self.show_node(self.node(target));self.post_action=True
                self.write('[1] Inspect contract · [2] View in graph · [3] Return to ecosystem')
            elif payload['kind']=='invite':
                self.write('Invitation sent to '+self.label(payload['recipient_id'])+'. It remains pending their response.')
            self.write('Simulated action saved. Other parties\' decisions and outcome verification remain separate.')
        else:self.write('No state changed: '+', '.join(error.replace('_',' ') for error in result['errors']))
        return result

    def cmd_player(self,arg):
        self.select_actor()

    def cmd_search(self,arg):
        self.query=arg or self.read('Search by name?');self.focus_actor=None
        if self.screen!='explorer':return 'back'

    def cmd_help(self,arg):
        self.view.heading('CONTEXTUAL HELP / '+self.screen,self.context())
        for command in menu(self.screen):
            self.write(command.name+' '+command.grammar+' · '+command.description+'\n  '+command.help)
            reason=self.command_availability(command.name)
            if reason:self.write('  Currently unavailable: '+reason)
        self.write('Shortcuts are followed by Enter; arrow keys move the selection immediately. Enter inspects the highlighted object. b or Esc returns. Numbered entries do not require internal IDs.')

    def cmd_history(self,arg):
        target=self.select_reference(arg)
        entries=[e for e in self.current().project('log') if any(m['entity_id']==target for m in e['mutations'])]
        if not entries:self.write('No transitions recorded for this object.');return
        while True:
            try:
                event=self.picker('HISTORY / '+self.label(target),entries,render=lambda e:f"State {e['sequence']} · "+EVENT_NAMES.get(e['kind'].split('.')[0],e['kind'].replace('_',' ')))
                self.inspect_node(target,at=event['sequence'])
                self.read('HISTORICAL GRAPH. Enter returns to the transition list; b returns too.')
            except Cancelled:return

    def cmd_past(self,arg):
        if not arg:return self.cmd_history('')
        sequence,_,reference=arg.partition(' ')
        target=self.select_reference(reference)
        self.inspect_node(target,at=int(sequence))

    def cmd_inbox(self,arg):
        if not self.session:self.write('Select a simulated player with p first.');return
        while not self.finished:
            items=self.session.inbox_records()
            if not items:self.write('No pending contracts require your response. c opens all contracts.');return
            try:
                item=self.picker('INBOX / INVITATIONS AND CONTRACTS',items,render=lambda item:self.aliases().get(item['id'],'')+' · '+item['label']+' · '+'; '.join(item['badges']))
                self.inspector(item['id'])
            except Cancelled:return

    def cmd_invite(self,arg):
        world=self.current().get_world()
        if not any(o['mode']=='gathering' for o in world['objectives'].values()):
            self.write('INVITE · Not available in this scenario. The engine has an invitation action, but this world has no gathering objective.');return
        if not self.session:self.write('INVITE · Select a simulated actor first.');return
        self.invitation()

    def cmd_connect(self,arg):
        target=resolve(self.world(),arg,selected=self.selected) if arg else self.selected
        if target not in self.world()['actors'] or target==self.session.actor:
            target=self.picker('WHOM WOULD YOU LIKE TO CONNECT WITH?',[a for a in people(self.world()) if a['id']!=self.session.actor])['id']
        self._proposal_target=target
        self.submit(self.collect_action({'kind':'send_contact','recipient_id':target},self.current()),len(self.current().project('log')))

    def cmd_respond(self,arg):
        if not self.session:self.write('RESPOND · Select a simulated actor first.');return
        pending=[r for r in self.current().get_world()['relationships'].values() if r['kind']=='invited' and r['target_id']==self.session.actor and r['status']=='proposed']
        if pending:self.invitation(respond=True)
        elif self.session.inbox_records('Awaiting my decision'):self.cmd_inbox('')
        else:self.write('RESPOND · No pending invitations or proposals require your response. c opens all contracts.')

    def invitation(self,respond=False):
        world=self.world();version=len(self.current().project('log'))
        if respond:
            pending=[r for r in world['relationships'].values() if r['kind']=='invited' and r['status']=='proposed' and r['target_id']==self.session.actor]
            item=self.choose('INVITATIONS REQUIRING YOUR RESPONSE',pending,
                             lambda r:'Invitation from '+self.label(r['source_id'])+' · '+self.label(r['objective_id']))
            response=self.choose('HOW DO YOU RESPOND?', ['accept','decline'],str)
            payload={'kind':'respond_invitation','invitation_id':item['id'],'response':response}
            self.write('This responds to an event invitation. It does not sign a contract or verify an outcome.')
        else:
            objective=self.choose('WHAT GATHERING ARE YOU PREPARING?',
                [o for o in world['objectives'].values() if o['mode']=='gathering'],lambda o:o['label'])
            recipient=self.choose('WHOM WOULD YOU LIKE TO INVITE?',
                [a for a in world['actors'].values() if a['id']!=self.session.actor and a['status']=='active'],display_label)
            payload={'kind':'invite','recipient_id':recipient['id'],'objective_id':objective['id']}
            self.write('This records a pending invitation to '+display_label(recipient)+'. They have not consented by receiving it.')
        if self.confirm('Save this simulated response?' if respond else 'Send this simulated invitation?'):
            self.submit(payload,version)

    def cmd_trajectory(self,arg):
        from .trajectory import project_trajectory,frames
        document=project_trajectory(self.current())
        self.view.heading('RECORDED SIMULATION TRAJECTORY',self.context())
        for frame in frames(document):
            self.write(f"State {frame['sequence']} · "+EVENT_NAMES.get(frame['kind'],frame['kind'].replace('_',' ')))
            for agreement in frame['agreements']:
                node=self.node(agreement['id'])
                self.show_node({**node,**agreement,'kind':'agreement'})

    def cmd_replay(self,arg):
        game=self.current()
        self.write('REPLAY CONSISTENT: '+str(game.replay().get_world()==game.get_world()))

    def cmd_metadata(self,arg):
        target=self.select_reference(arg);node=self.node(target)
        self.view.heading('SOURCE / TECHNICAL DETAILS',self.context())
        self.write('Internal reference: '+target)
        for field in ('kind','record_id','data_source_id','database_id','captured_at','created_at','last_edited_at','epistemic_status','import_version','synchronisation_status'):
            if field in node.get('provenance',{}):
                self.write(field.replace('_',' ')+': '+str(node['provenance'][field]))

    def cmd_back(self,arg):
        self.query='';self.kind_filter=None;self.focus_actor=None
        if self.screen=='explorer':self.finished=True
        return 'back'

    def cmd_ecosystem(self,arg):
        self.mode_name='ecosystem';self.kind_filter=None;self.focus_actor=None;self.query=''
        return 'back' if self.screen!='explorer' else None

    def cmd_paths(self,arg):
        mode=self.choose('CHOOSE YOUR PATH',['ecosystem','gathering','scenarios'],str.capitalize)
        return getattr(self,'cmd_'+mode)('')

    def cmd_gathering(self,arg):
        self.mode_name='gathering';self.kind_filter='objective';self.focus_actor=None;self.query=''
        return 'back' if self.screen!='explorer' else None

    def cmd_scenarios(self,arg):
        self.mode_name='scenarios';self.kind_filter='objective';self.focus_actor=None;self.query=''
        return 'back' if self.screen!='explorer' else None

    def cmd_quit(self,arg):
        self.finished=True
        return 'back'
