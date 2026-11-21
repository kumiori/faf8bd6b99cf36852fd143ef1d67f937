"""Player-facing terminal screens over existing projections and command rules."""

import json
from collections import Counter
from copy import deepcopy

from game_gamer.tui.errors import error_message
from game_gamer.tui.i18n import message_key
from game_gamer.tui.navigation import navigation_label

from . import mission_ui
from .catalogue import SimulationAuthority, affiliations, people
from .commands import contract_aliases, invitation_aliases, menu, parse, resolve
from .i18n import t
from .missions import install_missions, missions_installed
from .player import ActorSession
from .presentation import (
    OBJECTS,
    Presentation,
    actor_label,
    display_label,
    folded,
    status,
)
from .terminal_input import navigation
from .tui import Cancelled, Terminal, action_name, event_name

ACTION_EFFECTS = {
    'send_contact': message_key('contracts.effects.send_contact'),
    'draft_contact': message_key('contracts.effects.draft_contact'),
    'publish_contact': message_key('contracts.effects.publish_contact'),
    'respond_contact': message_key('contracts.effects.respond_contact'),
    'withdraw_contact': message_key('contracts.effects.withdraw_contact'),
    'propose': message_key('contracts.effects.propose'),
    'accept': message_key('contracts.effects.accept'),
    'amend': message_key('contracts.effects.amend'),
    'authorize': message_key('contracts.effects.authorize'),
    'activate': message_key('contracts.effects.activate'),
    'initiate': message_key('contracts.effects.initiate'),
    'fulfill': message_key('contracts.effects.fulfill'),
    'verify': message_key('contracts.effects.verify'),
    'reject': message_key('contracts.effects.reject'),
    'withdraw': message_key('contracts.effects.withdraw'),
    'terminate': message_key('contracts.effects.terminate'),
    'suspend': message_key('contracts.effects.suspend'),
    'resume': message_key('contracts.effects.resume'),
    'dispute': message_key('contracts.effects.dispute'),
    'publish_proposal': message_key('contracts.effects.publish_proposal'),
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
        revision = self.store.revision() if self.store else self.game.revision
        token = (str(self.store.path.resolve()) if self.store else id(self.game), revision)
        if getattr(self, '_frame_token', None) == token:
            return
        self._frame_game=self.store.load() if self.store else self.game
        self._frame_token = (token[0], self._frame_game.revision)
        self._frame_revision = self._frame_game.revision
        self._projection_cache = {}
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
        actor = actor_label(world,self.session.actor) if self.session else t('line.context.no_role_selected')
        state = len(self.current().project('log'))
        return t('line.context.playing_simulation_only', title=world['configuration']['world']['title'], actor=actor) + (t('line.context.historical_state_current', at=at, state=state) if at is not None else t('line.context.current_state', state=state))

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
        from .montreal_sources import LAYER
        names = world['configuration'].get(LAYER, {}).get('names', {}).get(node_id)
        if names:
            return names[0]
        return t('line.label.unresolved_source_reference')

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
                self.write(t('controls.search_prefix')+query)
            for i,item in enumerate(filtered[start:start+page_size],start+1):
                prefix = ('> ' if i-1==index else '  ')+f'[{i}] '
                if render and isinstance(item,dict) and item.get('kind') in OBJECTS:
                    self.show_node({**item,'label':render(item)},prefix)
                elif render:
                    self.write(prefix+render(item))
                else:
                    self.show_node(item,prefix)
            self.write(t('line.picker.matches_page', filtered_count=len(filtered), value=start // page_size + 1, value_2=max(1, (len(filtered) + page_size - 1) // page_size)))
            self.write(t('line.picker.select_enter_confirm_number_select'))
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
                query = raw[1:].strip() or self.ask(t('line.picker.search_by_name')); index=0; continue
            if raw == '?':
                self.write(t('line.picker.numbers_refer_to_the_visible')); continue
            if raw == 'v' and preview and filtered:
                preview(filtered[index]); self.read(t('line.picker.enter_to_return_to_selection')); continue
            try:
                chosen = int(raw)-1 if raw else index
                if not 0<=chosen<len(filtered):
                    raise ValueError
                return filtered[chosen]
            except ValueError:
                self.write(t('line.picker.choose_a_visible_number_move'))

    def choose(self, prompt, items, label=str):
        if not items:
            self.write(t('line.choose.no_matching_choices_are_available')); raise Cancelled
        return self.picker(prompt,items,render=label)

    def select_actor(self):
        self.refresh();world=self.world()
        organisation = ''; development = False
        while True:
            actors = people(world,organisation=organisation,development=development)
            self.view.heading(t('line.select_actor.who_will_you_play'),self.context())
            self.write(t('line.select_actor.choose_a_person_to_simulate'))
            if not actors:
                self.write(t('line.select_actor.no_eligible_imported_people_match'))
            self.write(t('line.select_actor.enter_open_people_catalogue_f'))
            raw = self.nav()
            if raw in {'b','q','0'}:
                raise Cancelled
            if raw == 'f':
                organisation = self.read(t('line.select_actor.organisation_name_blank_clears')); continue
            if raw == 'd':
                development = not development
                self.write(t('line.select_actor.development_roles_include_organisations_and')); continue
            # A direct number or /query also works without an extra confirmation.
            if raw and raw not in {'people','?'}:
                if raw.startswith('/'):
                    actors = people(world,search=raw[1:],organisation=organisation,development=development)
                elif raw.isdigit() and 0<int(raw)<=len(actors):
                    selected = actors[int(raw)-1]
                    self.assume_actor(selected); return
                else:
                    self.write(t('line.select_actor.enter_opens_the_catalogue_f')); continue
            try:
                selected = self.picker(t('line.select_actor.select_an_actor'),actors,render=lambda a:display_label(a)+
                    (' · '+', '.join(affiliations(world,a['id'])) if affiliations(world,a['id']) else t('line.select_actor.affiliation_unknown')),
                    preview=lambda a:self.inspect_node(a['id']))
                self.assume_actor(selected); return
            except Cancelled:
                continue

    def assume_actor(self, actor):
        if actor['kind']=='organisation' and not self.confirm(t('line.assume_actor.explicitly_simulate_this_organisation_role')):
            raise Cancelled
        identity,binding = self.authority.assume(actor,organisation_confirmed=actor['kind']=='organisation')
        self.session = ActorSession(self.game,actor['id'],store=self.store,identity=identity,binding=binding,provider=self.authority)
        self.identity = identity
        self.write(t('line.assume_actor.now_simulating')+display_label(actor)+t('line.assume_actor.the_shared_world_is_unchanged'))

    def coverage(self):
        world=self.world()
        imported = [a for a in world['actors'].values() if a.get('provenance',{}).get('kind')=='notion_snapshot' and a['kind']=='person']
        summary = world['configuration'].get('ecosystem-coverage',{}).get('summary')
        if summary:
            self.write(t('line.coverage.coverage_eligible_source_people_imported', value=summary.get('eligible_people', 0), imported_count=len(imported), value_2=summary.get('unresolved_identity_count', 0)))
            supplements=sum(a.get('provenance',{}).get('kind')!='notion_snapshot' for a in world['actors'].values())
            if supplements:self.write(t('line.coverage.synthetic_support_roles_are_supplementary', supplements=supplements))
        elif not world['configuration']['world'].get('synthetic',True):
            self.write(t('line.coverage.world_coverage_imported_people_complete', imported_count=len(imported)))

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
            self.write(t('session.closed'))
        return self.current()

    def splash(self):
        import textwrap
        width=max(20,min(46,self.view.width-2))
        plain=self.view.plain
        self.write(('+' if plain else '╔')+('-' if plain else '═')*width+('+' if plain else '╗'))
        for title in ('',t('branding.title'),t('branding.game_name'),'',t('branding.declaration'),''):
            for line in textwrap.wrap(title,width=width) or ['']:
                self.write(('|' if plain else '║')+line.center(width)+('|' if plain else '║'))
        self.write(('+' if plain else '╚')+('-' if plain else '═')*width+('+' if plain else '╝'))
        self.write(t('branding.simulation_mode_only'))

    def explorer(self):
        index = 0; page_size = 12
        while not self.finished:
            self.refresh()
            self.screen='explorer'; nodes = self.visible_nodes()
            index = min(index,max(0,len(nodes)-1)); start=index//page_size*page_size
            self.view.heading(navigation_label(self.mode_name).upper()+t('line.explorer.world_explorer'),self.context())
            self.coverage()
            world = self.current().get_world()
            if self.mode_name=='gathering' and not any(o['mode']=='gathering' for o in world['objectives'].values()):
                self.write(t('line.explorer.this_world_has_no_gathering'))
            if self.post_action:
                self.write(t('line.explorer.contract_created_1_inspect_contract'))
            else:
                self.write(t('line.explorer.modes_ecosystem_gathering_scenarios_clear'))
            previous_kind=None
            for i,node in enumerate(nodes[start:start+page_size],start+1):
                if previous_kind!=node['kind']:
                    self.write('\n'+OBJECTS.get(node['kind'],OBJECTS['evidence']).plural.upper());previous_kind=node['kind']
                self.show_node(node,('> ' if i-1==index else '  ')+f'[{i}] ')
            if not nodes:
                self.write(t('line.explorer.no_objects_match_this_view'))
            self.write(t('line.explorer.page_objects', value=start // page_size + 1, value_2=max(1, (len(nodes) + page_size - 1) // page_size), nodes_count=len(nodes)))
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
                    self.write(t('line.explorer.choose_a_displayed_number_or'))
                continue
            self.selected = nodes[index]['id'] if nodes else None
            self.dispatch(raw)

    def footer(self):
        shortcuts={'paths':'m','ecosystem':'e','gathering':'g','scenarios':'s','actions':'a','contracts':'c',
                   'inbox':'i','player':'p','history':'h','help':'?','back':t('line.footer.esc_b'),'quit':'q'}
        self.write(t('line.footer.select_enter_inspect_search')+ ' · '.join(shortcuts[c.name]+' '+c.description
                   for c in menu(self.screen) if c.name in shortcuts))

    def dispatch(self, raw):
        self.refresh()
        command,arg = parse(raw)
        if not command or self.screen not in command.screens:
            self.write(t('line.dispatch.unknown_command_press_for_commands')); return
        try:
            reason=getattr(self,command.availability)(command.name)
            if reason:
                self.write(command.name.upper()+' · '+reason);return
            if raw.casefold()=='contract history':
                arg=self.select_reference(contracts_only=True)
            return getattr(self,command.handler)(arg)
        except Cancelled:
            self.write(t('line.dispatch.cancelled_no_incomplete_action_was'))
        except (ValueError,RuntimeError) as error:
            self.write(t('feedback.unavailable_prefix')+error_message(error).replace('_',' ')+'.')

    def command_availability(self,name):
        world=self.current().get_world()
        if name in {'actions','inbox','invite','respond','connect'} and not self.session:
            return t('session.player_required')
        if name=='invite' and not any(o['mode']=='gathering' for o in world['objectives'].values()):
            return t('line.command_availability.not_available_in_this_scenario')
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
            self.write(t('line.select_reference.no_contracts_exist_yet') if contracts_only else t('line.select_reference.no_matching_object_exists'));raise Cancelled
        return self.picker(t('controls.choose_object'),nodes)['id']

    def inspector(self, node_id):
        index=0;page_size=10;parents=[]
        while not self.finished:
            self.refresh()
            self.screen='inspector';self.selected=node_id
            self.inspect_node(node_id)
            neighbours=self.neighbours(node_id)
            self.write(t('line.inspector.graph_neighbourhood_connected_objects'))
            index=min(index,max(0,len(neighbours)-1));start=index//page_size*page_size
            for i,node in enumerate(neighbours[start:start+page_size],start+1):
                decorated={**node,'label':node['label']+(' · '+node['_relationship_label'] if node.get('_relationship_label') else '')}
                self.show_node(decorated,('> ' if i-1==index else '  ')+f'[{i}] ')
            self.write(t('line.inspector.connected_objects_page_next_previous', value=start // page_size + 1, value_2=max(1, (len(neighbours) + page_size - 1) // page_size)))
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
                else:self.write(t('line.inspector.no_connected_objects_a_shows'))
                continue
            outcome=self.dispatch(raw)
            if outcome=='back':return

    def neighbours(self,node_id):
        from .projections import neighbourhood
        graph=neighbourhood(self.graph_projection(),node_id)
        nodes=[n for n in graph['nodes'] if n['id']!=node_id]
        for node in nodes:
            kinds={edge['kind'] for edge in graph['edges'] if node['id'] in (edge['source_id'],edge['target_id'])}
            if kinds=={'potential_complementarity'}:node['_relationship_label']=t('line.neighbours.inferred_potential')
        return nodes

    def inspect_node(self, node_id, *, at=None):
        game=self.current();world=game.world_at(event=at) if at is not None else self.world()
        node=self.node(node_id,at=at)
        if not node:raise ValueError('object_not_present_at_this_state')
        self.view.heading(t('objects.inspect_title', kind=OBJECTS.get(node['kind'], OBJECTS['evidence']).label),self.context(at=at))
        self.show_node(node)
        if node['kind']=='agreement':
            version=node['versions'][node['current_version']-1]
            self.write(t('contracts.proposer_prefix')+self.label(node['created_by'],world))
            self.write(t('contracts.parties_prefix')+', '.join(self.label(p,world) for p in node['parties']))
            self.write(t('contracts.proposal_requires_party_acceptance'))
            for party in node['parties']:
                role=t('terminal.proposer') if party==node['created_by'] else t('terminal.counterparty')
                receipt='accepted' if party in version['acceptances'] else t('line.inspect_node.no_acceptance_recorded')
                self.write(f'{role}: {self.label(party,world)} · {receipt}')
            self.write(t('line.inspect_node.linked_objective')+self.label(node['objective_id'],world))
            self.write(t('line.inspect_node.terms')+version['terms']['purpose'])
            for responsibility in version['terms']['responsibilities']:
                self.write('  '+self.label(responsibility['actor_id'],world)+': '+responsibility['description'])
            for condition in version['terms']['conditions']:self.write(t('laboratory.inspect_contract.condition')+condition)
            self.write(t('laboratory.inspect_contract.accepted_by')+(', '.join(self.label(p,world) for p in version['acceptances']) or t('line.inspect_node.no_parties_yet')))
            self.write(t('line.inspect_node.terms_version')+str(version['number']))
            self.write(t('laboratory.inspect_contract.authorised_by')+(', '.join(self.label(p,world) for p in version['authorizations']) or t('line.inspect_node.no_additional_approvals_recorded')))
            policy=world['governance'][version['policy_id']]
            self.write(t('line.inspect_node.governing_policy_governance_policy_node')+policy['label'])
            self.write(t('line.inspect_node.every_party_must_explicitly_accept'))
            self.write(t('line.inspect_node.required_approvals')+str(policy['threshold'])+t('line.inspect_node.named_approvers')+(', '.join(self.label(p,world) for p in policy['required_actors']) or 'none'))
            self.write(t('line.inspect_node.designated_independent_reviewers')+', '.join(self.label(p,world) for p in version['verification']['verifier_ids']))
            for resource in version['resources']:self.write(t('contracts.inspector.resource')+self.label(resource['resource_id'],world)+f" × {resource['quantity']}")
            self.write(t('contracts.inspector.evidence')+str(len(node['evidence_ids']))+t('line.inspect_node.record_s'))
            for evidence_id in node['evidence_ids']:
                evidence=world['evidence'][evidence_id]
                self.write('  '+evidence['kind'].replace('_',' ')+': '+evidence['reference'])
            for commitment in world['commitments'].values():
                if commitment['agreement_id']==node_id:
                    self.write(t('line.inspect_node.obligation')+self.label(commitment['actor_id'],world)+' · '+status(commitment['status']))
        elif node['kind']=='invitation':
            self.write(t('contact.inspector.participants', sender=self.label(node['source_id'], world),
                         recipient=self.label(node['target_id'], world)))
            self.write(t('common.status_prefix')+status(node['status']))
            self.write(node['message'])
            if node.get('purpose'):self.write(t('contracts.purpose_prefix')+node['purpose'])
            if node.get('response'):self.write(t('contact.inspector.response')+node['response']['decision']+' · '+node['response']['message'])
            self.write(t('line.inspect_node.a_simulated_contact_request_acceptance'))
        elif node.get('source_only'):
            from .montreal_sources import profile_statements
            self.write(t('line.inspect_node.montreal_source_identity_roster_binding'))
            for row in profile_statements(world, node_id):
                self.write(t('workshop.directory.motivation')+row['raw']['Pourquoi suis-je ici ?'])
                self.write(t('line.inspect_node.source', file=row['provenance']['file'], line=row['provenance']['line']))
        elif node_id in world['actors']:
            self.write(t('profiles.affiliation')+(', '.join(affiliations(world,node_id)) or t('common.unknown_or_not_recorded')))
            for table in ('capacities','needs'):
                self.write('\n'+table.upper())
                records=[r for r in world[table].values() if r['actor_id']==node_id]
                for record in records:self.show_node({**record,'kind':'capacity' if table=='capacities' else 'need','label':record['domain']})
                if not records:self.write(t('line.inspect_node.not_recorded_this_does_not'))
            self.write(t('line.inspect_node.recorded_relationships'))
            for relation in world['relationships'].values():
                if node_id in (relation['source_id'],relation['target_id']):
                    other=relation['target_id'] if relation['source_id']==node_id else relation['source_id']
                    self.write(relation['kind'].replace('_',' ')+' · '+self.label(other,world)+' · '+relation.get('status','unknown'))
            self.write(t('line.inspect_node.potential_complementarities_inferred_not_collaboration'))
            potentials=[p for p in game.derive_possibilities(world) if node_id in (p['source_id'],p['target_id'])]
            grouped=Counter(p['target_id'] if p['source_id']==node_id else p['source_id'] for p in potentials)
            for other,count in grouped.most_common(8):self.write(self.label(other,world)+t('line.inspect_node.declared_domain_match_es', count=count))
            self.write(t('line.inspect_node.contracts'))
            for agreement in world['agreements'].values():
                if node_id in agreement['parties']:self.show_node({**agreement,'kind':'agreement'})
        elif node['kind']=='policy':
            self.write(t('line.inspect_node.governance_policy_rule_enforced'))
            self.write(t('line.inspect_node.every_party_accepts_the_same'))
            self.write(t('line.inspect_node.additional_approval_threshold', threshold=node['threshold']))
            self.write(t('laboratory.inspect_contract.required_approvers')+(', '.join(self.label(p,world) for p in node['required_actors']) or t('common.none')))
            self.write(t('line.inspect_node.eligible_approvers')+(', '.join(self.label(p,world) for p in node['eligible_actors']) or t('common.none')))
            self.write(t('line.inspect_node.required_categories')+(', '.join(node['required_categories']) or t('common.none')))
            self.write(t('line.inspect_node.these_rules_confer_no_real'))
        else:
            for field in ('domain','quantity','unit','status','reference','label'):
                if field in node and field!='label':self.write(field.replace('_',' ').capitalize()+': '+(t('common.unknown') if node[field] is None else str(node[field])))
        self.write(t('line.inspect_node.provenance')+(t('line.inspect_node.source_assertion_unverified') if node.get('provenance',{}).get('kind')=='notion_snapshot' else t('line.inspect_node.recorded_simulation_fixture')))
        self.write(t('line.inspect_node.source_details_metadata_optional'))

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
            if not contracts:self.write(t('line.cmd_contracts.no_contracts_match_these_filters'));return
            chosen=self.picker(t('line.cmd_contracts.contract_registry'),[{**a,'kind':'agreement'} for a in contracts]);self.inspector(chosen['id']);return
        contracts=[a for a in world['agreements'].values() if not self.focus_actor or self.focus_actor in a['parties']]
        if not contracts:self.write(t('line.cmd_contracts.no_contracts_yet_for_this'));return
        chosen=self.picker(t('line.cmd_contracts.contract_registry'),[{**a,'kind':'agreement'} for a in contracts]);self.inspector(chosen['id'])

    def cmd_actions(self,arg):
        if not self.session:
            self.write(t('line.cmd_actions.choose_a_simulated_player_with'));return
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
            self.write(t('line.cmd_actions.no_action_is_permitted_for'));return
        candidate=self.choose(t('contracts.actions_title'),candidates,lambda c:action_name(c['kind'])+(' · '+c['response'] if c.get('response') else '')+(' · '+self.label(c['agreement_id']) if c.get('agreement_id') else ''))
        payload=self.collect_action(candidate,self.current());self.submit(payload,version)

    def collect_action(self,candidate,game):
        from game_gamer.transitions import active_transition_id, stage
        tracing_invite=active_transition_id()=='exercise.reconstruct.connect.invite'
        world=game.get_world();kind=candidate['kind']
        if kind in {'send_contact','draft_contact'}:
            target=world['actors'].get(candidate.get('recipient_id') or self._proposal_target)
            if not target or target['id']==self.session.actor:
                target=self.picker(t('contact.choose_recipient'),[a for a in people(world) if a['id']!=self.session.actor])
            self.write(t('line.collect_action.simulating')+self.label(self.session.actor)+' → '+self.label(target['id']))
            self.write(t('line.collect_action.an_invitation_proposes_contact_it'))
            if tracing_invite:stage('question',state_id='exercise.reconstruct.invite.message')
            message=self.ask(t('line.collect_action.invitation_message'),default=t('contact.message_example'))
            if tracing_invite:stage('question',state_id='exercise.reconstruct.invite.purpose')
            purpose=self.ask(t('line.collect_action.optional_invitation_purpose_blank_for'),default='',parse=lambda value:value.strip())
            payload={'kind':kind,'id':f'contact-{len(world["actions"])+1:06}', 'recipient_id':target['id'],
                     'message':message,'purpose':purpose}
            if candidate.get('context'):payload['context']=deepcopy(candidate['context'])
            if kind=='send_contact':
                if tracing_invite:
                    from .reconstruction_transitions import REGISTRY, P, choice
                    self._reconstruction_modal=P+'invite.delivery'
                    stage('question',state_id=P+'invite.delivery')
                    delivery=self.choose(t('contact.delivery_title'),[choice('invite.delivery.send'),
                        choice('invite.delivery.draft')],lambda choice:choice.label)
                    selected=REGISTRY.execute(delivery.transition_id,self)
                    if selected.outcome=='aborted':raise KeyboardInterrupt
                    if selected.outcome!='completed':raise ValueError('invitation_delivery_failed')
                    kind=payload['kind']=selected.value
                    self._reconstruction_modal=None
                else:
                    delivery = self.choose(t('contact.delivery_title'), ['send_contact', 'draft_contact'],
                                           lambda action: t('contact.send_now') if action == 'send_contact' else t('contact.save_draft'))
                    kind = payload['kind'] = delivery
        elif kind in {'publish_contact','withdraw_contact','respond_contact'}:
            payload=deepcopy(candidate)
            if kind=='respond_contact':
                payload['response_message']=self.ask(t('line.collect_action.optional_response_message_blank_for'),default='',parse=lambda value:value.strip())
        elif kind=='propose':
            template=world['configuration']['world']['proposal']
            if template:
                payload={'kind':kind,**deepcopy(template)}
            else:
                target=world['actors'].get(self._proposal_target)
                if not target or target['id']==self.session.actor:
                    choices=[a for a in people(world) if a['id']!=self.session.actor]
                    target=self.picker(t('line.collect_action.who_would_you_like_to'),choices)
                objectives=list(world['objectives'].values())
                objective=objectives[0]
                if len(objectives)>1 and self.confirm(t('line.collect_action.link_this_agreement_to_a')):
                    objective=self.choose(t('line.collect_action.optional_wider_objective'),objectives,lambda o:o['label'])
                parties=[self.session.actor,target['id']]
                self.write(t('line.collect_action.proposing_actor')+self.label(self.session.actor))
                self.write(t('line.collect_action.counterparty')+self.label(target['id']))
                title=self.ask(t('laboratory.collect_action.contract_title'),default=t('contracts.defaults.title'))
                purpose=self.ask(t('line.collect_action.purpose_of_this_agreement'),default=title)
                offered=self.ask(t('line.collect_action.your_offered_contribution'),default=t('contracts.defaults.offer'))
                requested=self.ask(t('line.collect_action.contribution_requested_from')+self.label(target['id'])+'?',default=t('contracts.defaults.request'))
                condition=self.ask(t('line.collect_action.optional_conditions_blank_for_none'),default='',parse=lambda value:value.strip())
                resources=[]
                if world['resources'] and self.confirm(t('line.collect_action.include_a_resource_allocation')):
                    resource=self.choose(t('line.collect_action.optional_resource'),list(world['resources'].values()),display_label)
                    quantity=self.ask(t('line.collect_action.requested_quantity'),default=1,parse=self.positive)
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
                terms=deepcopy(current['terms']);terms['purpose']=self.ask(t('line.collect_action.revised_shared_purpose'),default=terms['purpose'])
                for responsibility in terms['responsibilities']:
                    responsibility['description']=self.ask(t('line.collect_action.proposed_contribution_from')+self.label(responsibility['actor_id'])+'?',default=responsibility['description'])
                condition=self.ask(t('line.collect_action.conditions_for_this_revision'),default='; '.join(terms['conditions']))
                terms['conditions']=[condition] if condition else []
                payload['terms']=terms
            if kind in {'initiate','fulfill','verify'}:
                if kind=='fulfill':
                    for criterion in current['verification']['criteria']:
                        if not self.confirm(t('laboratory.collect_action.does_your_report_address')+criterion+'?'):raise Cancelled
                    payload['criteria']=deepcopy(current['verification']['criteria'])
                payload['reference']=self.ask(t('line.collect_action.describe_the_supplied_evidence_or'))
            if kind in {'reject','withdraw','terminate','suspend','dispute'}:payload['reason']=self.ask(t('forms.reason_question'))
        if kind=='propose':payload=self.refine_proposal(payload,world)
        self.view.heading(t('line.collect_action.action')+action_name(kind),self.context())
        affected=payload.get('parties',world['agreements'].get(payload.get('agreement_id'),{}).get('parties',[]))
        if kind in {'send_contact','draft_contact'}:affected=[self.session.actor,payload['recipient_id']]
        elif kind in {'respond_contact','publish_contact','withdraw_contact'}:
            item=world['relationships'][payload['invitation_id']];affected=[item['source_id'],item['target_id']]
        self.write(t('line.collect_action.who_is_affected')+', '.join(self.label(p) for p in affected))
        self.write(t('line.collect_action.what_will_change')+t(ACTION_EFFECTS[kind]))
        self.write(t('line.collect_action.this_simulated_action_is_not'))
        if tracing_invite:stage('question',state_id='exercise.reconstruct.invite.confirm')
        if not self.confirm(t('controls.confirm_continue')):raise Cancelled
        return payload

    def refine_proposal(self,payload,world):
        """Presentation hook; line-mode retains its reproducible default form."""
        return payload

    def submit(self,payload,version):
        from game_gamer.transitions import observe_engine_result, stage
        stage('submission_requested')
        result=self.session.submit(payload,expected_version=version)
        observe_engine_result(payload['kind'],result,boundary='host')
        self.refresh()
        if result['ok']:
            target=payload.get('agreement_id') or payload.get('id')
            self.view.heading(t('line.submit.contract_created') if payload['kind']=='propose' else t('line.submit.shared_world_updated'),self.context())
            if target in self.current().get_world()['agreements']:
                self.last_contract=target;self.selected=target;self.show_node(self.node(target));self.post_action=True
                self.write(t('line.submit.shortcut_1_inspect_contract_2_view'))
            elif payload['kind']=='invite':
                self.write(t('contact.saved_invitation', recipient=self.label(payload['recipient_id'])))
            self.write(t('line.submit.simulated_action_saved_other_parties'))
        else:self.write(t('feedback.no_state_changed')+', '.join(error.replace('_',' ') for error in result['errors']))
        return result

    def cmd_player(self,arg):
        self.select_actor()

    def cmd_search(self,arg):
        self.query=arg or self.read(t('line.picker.search_by_name'));self.focus_actor=None
        if self.screen!='explorer':return 'back'

    def cmd_help(self,arg):
        self.view.heading(t('help.contextual_help')+self.screen,self.context())
        for command in menu(self.screen):
            self.write(command.name+' '+command.grammar+' · '+command.description+'\n  '+command.help)
            reason=self.command_availability(command.name)
            if reason:self.write(t('help.currently_unavailable')+reason)
        self.write(t('help.shortcuts_are_followed_by_enter'))

    def cmd_history(self,arg):
        mission_id = arg.upper()
        if self.world()['configuration'].get(mission_id, {}).get('kind') == 'mission_definition':
            return mission_ui.show_line_history(self, mission_id)
        target=self.select_reference(arg)
        entries=[e for e in self.current().project('log') if any(m['entity_id']==target for m in e['mutations'])]
        if not entries:self.write(t('line.cmd_history.no_transitions_recorded_for_this'));return
        while True:
            try:
                event=self.picker(t('line.cmd_history.history')+self.label(target),entries,render=lambda e:t('line.cmd_history.state', sequence=e['sequence'])+event_name(e['kind'].split('.')[0], e['kind'].replace('_', ' ')))
                self.inspect_node(target,at=event['sequence'])
                self.read(t('line.cmd_history.historical_graph_enter_returns_to'))
            except Cancelled:return

    def cmd_past(self,arg):
        if not arg:return self.cmd_history('')
        sequence,_,reference=arg.partition(' ')
        target=self.select_reference(reference)
        self.inspect_node(target,at=int(sequence))

    def cmd_inbox(self,arg):
        if not self.session:self.write(t('session.player_required'));return
        while not self.finished:
            items=self.session.inbox_records(localized=True)
            if not items:self.write(t('line.cmd_inbox.no_pending_contracts_require_your'));return
            try:
                item=self.picker(t('inbox.all_title'),items,render=lambda item:self.aliases().get(item['id'],'')+' · '+item['label']+' · '+'; '.join(item['badges']))
                self.inspector(item['id'])
            except Cancelled:return

    def cmd_invite(self,arg):
        world=self.current().get_world()
        if not any(o['mode']=='gathering' for o in world['objectives'].values()):
            self.write(t('line.cmd_invite.invite_not_available_in_this'));return
        if not self.session:self.write(t('line.cmd_invite.invite_select_a_simulated_actor'));return
        self.invitation()

    def cmd_connect(self,arg):
        target=resolve(self.world(),arg,selected=self.selected) if arg else self.selected
        if target not in self.world()['actors'] or target==self.session.actor:
            target=self.picker(t('contact.choose_recipient'),[a for a in people(self.world()) if a['id']!=self.session.actor])['id']
        self._proposal_target=target
        self.submit(self.collect_action({'kind':'send_contact','recipient_id':target},self.current()),len(self.current().project('log')))

    def cmd_respond(self,arg):
        if not self.session:self.write(t('line.cmd_respond.respond_select_a_simulated_actor'));return
        pending=[r for r in self.current().get_world()['relationships'].values() if r['kind']=='invited' and r['target_id']==self.session.actor and r['status']=='proposed']
        if pending:self.invitation(respond=True)
        elif self.session.inbox_records('Awaiting my decision'):self.cmd_inbox('')
        else:self.write(t('line.cmd_respond.respond_no_pending_invitations_or'))

    def invitation(self,respond=False):
        world=self.world();version=len(self.current().project('log'))
        if respond:
            pending=[r for r in world['relationships'].values() if r['kind']=='invited' and r['status']=='proposed' and r['target_id']==self.session.actor]
            item=self.choose(t('line.invitation.invitations_requiring_your_response'),pending,
                             lambda r:t('line.invitation.invitation_from')+self.label(r['source_id'])+' · '+self.label(r['objective_id']))
            response=self.choose(t('line.invitation.how_do_you_respond'), ['accept','decline'],str)
            payload={'kind':'respond_invitation','invitation_id':item['id'],'response':response}
            self.write(t('line.invitation.this_responds_to_an_event'))
        else:
            objective=self.choose(t('line.invitation.what_gathering_are_you_preparing'),
                [o for o in world['objectives'].values() if o['mode']=='gathering'],lambda o:o['label'])
            recipient=self.choose(t('line.invitation.whom_would_you_like_to'),
                [a for a in world['actors'].values() if a['id']!=self.session.actor and a['status']=='active'],display_label)
            payload={'kind':'invite','recipient_id':recipient['id'],'objective_id':objective['id']}
            self.write(t('line.invitation.this_records_a_pending_invitation')+display_label(recipient)+t('line.invitation.they_have_not_consented_by'))
        if self.confirm(t('line.invitation.save_this_simulated_response') if respond else t('line.invitation.send_this_simulated_invitation')):
            self.submit(payload,version)

    def cmd_trajectory(self,arg):
        from .trajectory import frames, project_trajectory
        document=project_trajectory(self.current())
        self.view.heading(t('line.cmd_trajectory.recorded_simulation_trajectory'),self.context())
        for frame in frames(document):
            self.write(t('line.cmd_history.state', sequence=frame['sequence'])+event_name(frame['kind'], frame['kind'].replace('_', ' ')))
            for agreement in frame['agreements']:
                node=self.node(agreement['id'])
                self.show_node({**node,**agreement,'kind':'agreement'})

    def cmd_replay(self,arg):
        game=self.current()
        self.write(t('laboratory.history.replay_consistent')+str(game.replay().get_world()==game.get_world()))

    def cmd_metadata(self,arg):
        target=self.select_reference(arg);node=self.node(target)
        self.view.heading(t('line.cmd_metadata.source_technical_details'),self.context())
        self.write(t('line.cmd_metadata.internal_reference')+target)
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
        mode=self.choose(t('terminal.standalone.choose_your_path'),['ecosystem','gathering','scenarios'],navigation_label)
        return getattr(self,'cmd_'+mode)('')

    def cmd_gathering(self,arg):
        self.mode_name='gathering';self.kind_filter='objective';self.focus_actor=None;self.query=''
        return 'back' if self.screen!='explorer' else None

    def ensure_missions(self):
        self.refresh()
        world = self.world()
        if world['configuration']['world']['scenario'] != 'montreal-commons' or missions_installed(world):
            return
        if self.store:
            self.store.transact(install_missions)
        else:
            install_missions(self.game)
        self.refresh()

    def cmd_scenarios(self,arg):
        self.ensure_missions()
        if mission_ui.mission_menu(self.world()):
            mission_id = arg.upper() or None
            if mission_id and self.world()['configuration'].get(mission_id, {}).get('kind') != 'mission_definition':
                self.write(t('missions.unknown'))
                return
            return mission_ui.run_line(self, mission_id)
        self.mode_name='scenarios';self.kind_filter='objective';self.focus_actor=None;self.query=''
        return 'back' if self.screen!='explorer' else None

    def cmd_quit(self,arg):
        self.finished=True
        return 'back'
