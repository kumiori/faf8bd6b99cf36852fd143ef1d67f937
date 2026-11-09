"""Full-screen player interface. Screen state is independent of curses and rules.

All mutations pass through ActorSession and the existing command forms. The
viewport owns keyboard/display concerns only; line-mode play remains available.
"""

from copy import deepcopy
from io import StringIO

from game_gamer.projections.inbox import action_options
from game_gamer.tui.errors import error_list
from game_gamer.tui.i18n import message_key
from game_gamer.tui.matrix import AxisLabel, MatrixView, render_matrix
from game_gamer.tui.navigation import MODE_KEYS, NavigationState, navigation_label
from game_gamer.tui.navigation import Route as Route
from game_gamer.tui.screen import Screen as Screen
from game_gamer.tui.screen import inspector, record_receipt, run_screens
from game_gamer.tui.viewport import CursesViewport as CursesViewport
from game_gamer.tui.viewport import action_form, run_curses
from game_gamer.tui.viewport import supported as supported

from . import curation_panel, curator, montreal_network
from .catalogue import affiliations, people
from .commands import resolve
from .exercises import exercise_menu, tutorial_graph, tutorial_key, tutorial_screen
from .expertise import cell, matrix
from .global_history import history_key, history_screen
from .heatmap import BANDS
from .i18n import t
from .montreal_sources import profile_statements
from .network_view import (
    CATEGORIES,
    OBJECT_TYPES,
    category_label,
    draw_graph,
    focus_graph,
    object_type_label,
)
from .play import ACTION_EFFECTS, PlayableTerminal
from .presentation import (
    INBOX_CATEGORIES,
    OBJECTS,
    clean,
    display_label,
    folded,
    inbox_category,
    status,
)
from .reconstruction import build_exercise, exercise_available, handle_exercise
from .scenario_catalogue import catalogue, objectives_for, scenarios_for
from .tui import Cancelled, action_name, event_name

MODES = {'ecosystem': (message_key('navigation.ecosystem.label'), message_key('navigation.ecosystem.description')),
         'gathering': (message_key('navigation.gathering.label'), message_key('navigation.gathering.description')),
         'scenarios': (message_key('navigation.scenarios.label'), message_key('navigation.scenarios.description'))}
DECISION_KEYS = {'accept': ('y', message_key('contracts.shortcuts.accept')), 'amend': ('j', message_key('contracts.shortcuts.amend')),
                 'reject': ('R', message_key('contracts.shortcuts.reject')), 'withdraw': ('X', message_key('contracts.shortcuts.withdraw'))}


def score_text(detail):
    if detail['value'] is not None: return str(detail['value'])
    if detail.get('upper') is None: return t('common.unknown')
    return t('matrix.score.unknown_lower_bound', lower=detail['lower'], upper=detail['upper'])


class FullScreenTerminal(PlayableTerminal):
    """A screen stack over one shared saved world and one simulated perspective."""
    def __init__(self, game, *, viewport, **options):
        options.pop('output', None)
        self.transition_trace=options.pop('transition_trace',None)
        super().__init__(game, output=StringIO(), **options)
        self.viewport = viewport
        self.navigation = NavigationState()
        self.mode_routes = self.navigation.roots
        self.notice = ''
        self.width, self.height = 80, 24

    @property
    def route(self):
        return self.navigation.route

    @property
    def stack(self):
        return self.navigation.stack

    @stack.setter
    def stack(self, value):
        self.navigation.stack = value

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
            if route.kind=='matrix':parts.append(t('navigation.ecosystem.label'))
            elif route.kind=='cell' and route.extra.get('relation'):
                parts.append(' → '.join(self.label(p) for p in route.extra['relation']))
            elif route.kind=='scenario':parts.append(t('navigation.scenario.label'))
            elif route.target:parts.append(self.label(route.target) if route.kind!='network' else t('terminal.network')+self.label(route.target))
            else:parts.append(navigation_label(route.kind))
        return ' > '.join(parts)

    def reset_buffer(self):
        self.output.seek(0); self.output.truncate()

    def context(self, *, at=None):
        if getattr(self, '_capturing', False):
            return ''
        if self.route.kind in {'tutorial', 'tutorial_graph'}:
            practice = getattr(self, '_tutorial_sessions', {}).get(self.route.target)
            if practice:
                step = practice.definition['steps'][min(practice.index, len(practice.definition['steps'])-1)]
                return t('terminal.practice_sandbox_role_v', title=practice.definition['title'], actor_id=step['actor_id'], version=practice.collective.project()['version'])
        actor = self.label(self.session.actor) if self.session else t('terminal.choose_a_person')
        route = self.route
        world = self.world()['configuration']['world']['title']
        historical = t('terminal.historical_view') if at is not None else ''
        if route.kind.startswith('curator'):
            focus = t('terminal.inspecting')+self.label(route.target) if route.target else ''
            if route.kind == 'curator' and route.extra.get('panel_page') == 'queue':
                focus = t('terminal.inspecting_curation_requests')
            elif route.kind == 'curator' and route.extra.get('panel_page') == 'review':
                from game_gamer.runtime.curation_requests import records
                request = records(self.world()).get(route.extra.get('request_id'))
                if request:
                    focus = t('terminal.inspecting_request_for')+self.label(request['target_id'])
            return t('terminal.context', actor=actor, focus=focus, world=world,
                     revision=self._frame_revision, historical=historical)
        mode = t(MODES[self.navigation.mode][0])
        if any(item.kind in {'exercises', 'reconstruction_intro'} | montreal_network.MAIN_ROUTES
               for item in self.stack):
            mode = t('navigation.workshop').title()
        elif route.kind in {'history', 'history_event', 'history_object', 'trajectory'}:
            mode = t('terminal_polish.activity').title()
        return t('terminal_polish.context', world=world, actor=actor, mode=mode, historical=historical)

    def decorate_screen(self, screen):
        screen.masthead = t('branding.title')
        screen.breadcrumb = ''
        screen.navigation_text = ''
        if self.route.kind not in {'tutorial', 'tutorial_graph'} and curator.allowed(self):
            screen.header_indicator = t('curation.indicator')

    def panel_drawn(self, screen, scroll):
        curation_panel.finish_frame(self, scroll)

    def capture(self, operation):
        self.reset_buffer()
        self._capturing = True
        try:
            operation()
        finally:
            self._capturing = False
        return [line for line in self.output.getvalue().strip().splitlines()
                if not (line.strip() and set(line.strip()) <= {'=','-','─'})]

    def read(self, prompt='>'):
        result = self.viewport.prompt(prompt, self.output.getvalue().splitlines(), self.context())
        self.reset_buffer()
        if result is None:
            raise Cancelled
        return result.strip()

    def confirm(self, prompt):
        confirm = getattr(self.viewport, 'confirm', None)
        if confirm:
            result = confirm(prompt, self.output.getvalue().splitlines(), self.context())
            self.reset_buffer()
            return result
        return super().confirm(prompt)

    def picker(self, title, items, *, render=None, preview=None, section=None, menu=None):
        if not items:
            self.notice = t('terminal.no_matching_choices_are_available')
            raise Cancelled
        def label(item):
            if render:
                return render(item)
            return display_label(item)
        options = {'preview': preview, 'masthead': t('branding.title')}
        if menu is not None:
            options['menu'] = menu
        if curator.allowed(self) and self.route.kind not in {'tutorial', 'tutorial_graph'}:
            options['header_indicator'] = t('curation.indicator')
        if section is not None:
            options['section'] = section
        return self.viewport.choose(title, items, label, self.context(), **options)

    def choose(self, prompt, items, label=str):
        return self.picker(prompt, items, render=label)

    def select_actor(self):
        self.refresh()
        roster = people(self.world())
        # Deliberate development-only roles remain reachable without polluting
        # the imported people catalogue or implying source authentication.
        choices = [*roster, {'id': '__development__', 'kind': 'role', 'label': t('terminal.development_simulation_roles')}]
        def label(actor):
            orgs = affiliations(self.world(), actor['id'])
            return display_label(actor) + (' · '+', '.join(orgs) if orgs else '') + (t('curation.role_suffix') if 'curator' in actor.get('roles', []) else '')
        actor = self.picker(t('terminal.who_will_you_play_search'), choices, render=label,
            preview=lambda a: self.capture(lambda: self.inspect_node(a['id'])) if a['id'] != '__development__' else
                [t('terminal.explicit_development_roles_grant_simulation')])
        if actor['id'] == '__development__':
            actor = self.picker(t('terminal.development_roles_simulation_authority_only'), people(self.world(), development=True))
        self.assume_actor(actor)
        if not self.mode_routes['ecosystem'].extra.get('positioned'):
            ids = [a['id'] for a in matrix(self.world())['actors']]
            if actor['id'] in ids:
                self.mode_routes['ecosystem'].row = self.mode_routes['ecosystem'].column = ids.index(actor['id'])
            self.mode_routes['ecosystem'].extra['positioned'] = True
        self.notice = t('session.role_changed', actor=display_label(actor))

    def choose_mode(self):
        options = [*MODES, 'exercises']
        if exercise_available(self.world()):
            options.append('montreal_network')
        options.append('history')
        menu = {name: (t(label).upper(), t(description)) for name, (label, description) in MODES.items()}
        menu.update(
            exercises=(t('navigation.exercises.title'), t('navigation.exercises.description')),
            montreal_network=(t('navigation.montreal_network.title'), t('navigation.montreal_network.description')),
            history=(t('history.title').upper(), t('navigation.history.description')),
        )
        def section(name):
            if name in MODES:
                return t('terminal_polish.world')
            return t('terminal_polish.activity') if name == 'history' else t('navigation.workshop')
        def label(name):
            title, description = menu[name]
            return t('navigation.path_entry', title=title, description=description)
        mode = self.picker(t('navigation.commons_game_choose_your_path'), options, render=label,
                           section=section, menu=menu)
        if mode == 'montreal_network':
            self.push(mode, self.playing_actor)
            self.route.region = 'directory'
        elif mode in {'exercises', 'history'}:
            self.push(mode)
        else:
            self.resume_mode(mode)

    def switch_mode(self, mode):
        """Explicitly reopen a mode root (for example x → Matrix)."""
        self.navigation.resume(mode, reset=True)
        self.mode_name = mode
        self.selected = None

    def resume_mode(self, mode):
        self.navigation.resume(mode)
        self.mode_name = mode
        self.selected = None

    def push(self, kind, target=None, **extra):
        if kind == 'inspect' and not self.node(target,at=extra.get('at')):
            raise ValueError('object_not_present_at_this_state')
        if 'relation' not in extra and self.focused_relation:
            extra['relation']=self.focused_relation
        if kind=='inspect' and target in self.world()['relationships']:
            context=self.world()['relationships'][target].get('context',{})
            if context:extra['relation']=(context['provider_id'],context['requester_id'])
        self.navigation.push(kind, target, **extra)

    def back(self):
        if self.route.kind == 'montreal_network_graph' and len(self.stack) > 1:
            parent = self.stack[-2]
            parent.target = self.route.target
            for key in ('graph_groups', 'zoom', 'angle', 'filter', 'actor_type', 'sort'):
                if key in self.route.extra:
                    parent.extra[key] = self.route.extra[key]
            parent.extra.update(network_detail=0, network_page=0)
        if self.route.kind == 'reconstruction_graph' and len(self.stack) > 1:
            self.stack[-2].target = self.route.target
        if not self.navigation.back():
            self.choose_mode()

    def run(self):
        try:
            self.viewport.message(Screen(t('branding.title'), ['', t('branding.declaration'), '',
                t('terminal.simulation_2'), '', t('controls.begin_or_quit')], footer=t('controls.begin_or_quit'), navigation=False))
            if self.viewport.key() == 'q':
                return self.current()
            if not self.explore and not self.session:
                self.select_actor()
            self.choose_mode()
            run_screens(self)
        except (EOFError, KeyboardInterrupt, Cancelled):
            pass
        return self.current()

    def prepare_screen(self):
        self.refresh()
        self.width, self.height = self.viewport.size()
        self.view.width = max(16, self.width-2)

    def build_screen(self):
        route = self.route
        if route.kind in montreal_network.ROUTES:
            return montreal_network.build(self)
        self.screen = 'inspector' if route.kind == 'inspect' else 'inbox' if route.kind == 'inbox' else 'explorer'
        if route.kind == 'exercises':
            return exercise_menu(self)
        if route.kind == 'tutorial':
            return tutorial_screen(self)
        if route.kind == 'tutorial_graph':
            return tutorial_graph(self)
        if route.kind.startswith('curator'):
            if any(r.kind == 'curator' and r.extra.get('contextual') for r in self.stack):
                return curation_panel.panel_screen(self)
            return curator.screen(self)
        if route.kind in {'reconstruction', 'reconstruction_intro', 'reconstruction_filters', 'reconstruction_facet', 'reconstruction_graph', 'reconstruction_layers', 'reconstruction_provenance', 'action_result'}:
            return build_exercise(self)
        if route.kind == 'matrix':
            return self.matrix_screen()
        if route.kind == 'cell':
            return self.cell_screen()
        if route.kind == 'expertise':
            actor = self.world()['actors'][route.target]; projection = matrix(self.world())
            i = next(i for i,a in enumerate(projection['actors']) if a['id']==actor['id'])
            lines = [self.label(actor['id']),t('matrix.expertise.complete_declared_expertise_unknown_values')]
            for side,kind in (('offer','O'),('need','N')):
                observation = projection['observations'][actor['id']][side]
                lines += [side.upper()+': '+observation['state']]
                lines += [projection['vocabulary'][code]+': '+('?' if value is None else t('matrix.expertise.selected') if value else t('matrix.expertise.not_selected'))
                          for code,value in zip(projection['domains'],projection[kind][i])]
            return Screen(t('matrix.expertise.offers_and_needs'),lines,scroll=route.scroll,footer=t('matrix.expertise.pgup_pgdn_scroll_b_profile'))
        if route.kind == 'incidence':
            projection=matrix(self.world()); i=next(i for i,a in enumerate(projection['actors']) if a['id']==route.target)
            k=projection['domains'].index(route.extra['domain']);kind=route.extra['matrix_kind'];value=projection[kind][i][k]
            observation=projection['observations'][route.target]['offer' if kind=='O' else 'need']
            return Screen(t('terminal.declared_topic', topic=t('matrix.expertise.offer') if kind=='O' else t('matrix.expertise.need')),[
                self.label(route.target),projection['vocabulary'][route.extra['domain']],
                t('matrix.expertise.value')+(t('common.unknown') if value is None else str(value)),
                t('matrix.expertise.answer_state')+observation['state']],
                [(t('matrix.expertise.explore')+self.label(route.target),route.target)],t('matrix.expertise.enter_profile_d_source_details'))
        if route.kind == 'inspect':
            return self.inspector_screen()
        if route.kind == 'contracts':
            nodes = [n for n in self.graph_projection()['nodes'] if n['kind'] == 'agreement']
            if route.extra.get('filters'):
                from .projections import contract_registry
                matches = {a['id'] for a in contract_registry(self.world(),**route.extra['filters'])}
                nodes = [n for n in nodes if n['id'] in matches]
            result=self.list_screen(t('contracts.registry.contract_registry_transversal_layer'), nodes)
            if self.playing_actor:
                result.entries += [(t('contracts.registry.propose_a_contract_choose_a'),('choose_interaction','propose'))]
                if self.world()['actors'][self.playing_actor]['kind']=='person':
                    result.entries += [(t('contracts.registry.invite_to_connect_choose_a'),('choose_interaction','invite'))]
            return result
        if route.kind == 'inbox':
            if not self.session:
                return Screen(t('inbox.title'), [t('inbox.p_choose_a_simulated_player')])
            category = route.extra.get('category')
            items = self.session.inbox_records(category, localized=True)
            entries = [(self.aliases().get(item['id'], t('objects.invitation.singular'))+' · '+item['label']+' · '+' / '.join(item['badges']), item['id'])
                       for item in items if folded(route.query) in folded(item['label'])]
            route.index = min(route.index, max(0, len(entries)-1))
            lines = [t('inbox.filter')+inbox_category(category)+t('inbox.one_entry_per_object'),
                     t('inbox.badges_describe_pending_decisions_filters')]
            if not entries: lines.append(t('inbox.no_items_in_this_view'))
            return Screen(t('inbox.all_title'), lines, entries,
                          t('inbox.enter_review_a_actions_f'), route.index, route.scroll, wrap_entries=True)
        if route.kind in {'history', 'history_event', 'history_object'}:
            return history_screen(self)
        if route.kind == 'trajectory':
            from .trajectory import frames, project_trajectory
            try:
                document = project_trajectory(self.current())
                records = frames(document)
                lines = [t('trajectory.recorded_simulation_history_no_invented')]
                for record in records:
                    lines.append(event_name(record['event_kind'], event_name(record['kind'], record['kind'].replace('_', ' '))))
                    lines += ['  '+self.aliases().get(item['id'],t('objects.invitation.singular'))+' · '+status(item['status'])+t('trajectory.contact_only')
                              for item in record['invitations']]
                    for agreement in record['agreements']:
                        lines.append('  '+self.contract_title(agreement['id'])+' · '+status(agreement['status'])+t('contracts.inline_outcome_prefix')+status(agreement['outcome_status']))
            except (ImportError, ValueError) as error:
                lines = [t('trajectory.trajectory_package_unavailable_install_the'), clean(error),
                         t('trajectory.h_history_and_replay_remain')]
            return Screen(t('trajectory.recorded_trajectory'), lines, footer=t('trajectory.v_verify_replay_pgup_pgdn'), scroll=route.scroll)
        if route.kind == 'gathering':
            from .gathering import conditions
            objectives = [n for n in self.graph_projection()['nodes'] if n['kind'] == 'objective' and n.get('mode') == 'gathering']
            if not objectives:
                return Screen(t('gathering.gathering_conditions'), [
                    t('gathering.no_gathering_objective_is_registered'),
                    t('gathering.invitation_and_attendance_actions_are'),
                    t('gathering.this_mode_remains_an_inspectable'),
                    t('gathering.contracts_are_available_with_c')])
            pending = [r for r in self.world()['relationships'].values() if r['kind'] == 'invited']
            lines = [t('gathering.registered_gathering_objectives_and_recorded')]
            for objective in objectives:lines += conditions(self.world(),objective)
            lines += [self.label(r['source_id'])+' → '+self.label(r['target_id'])+' · '+status(r['status']) for r in pending]
            lines += [t('gathering.conditions_and_outcomes_come_from')]
            return self.list_screen(t('gathering.gathering_conditions'), objectives, lines, t('gathering.j_invite_r_respond'))
        if route.kind == 'scenarios':
            records=[r for r in catalogue(self.world()) if folded(route.query) in folded(r['title'])]
            return Screen(t('scenarios.scenarios_catalogue'),[
                t('scenarios.scenario_situation_and_possible_transformation'),
                t('scenarios.workshop_source_material_is_inspectable'),
                t('scenarios.synthetic_fixtures_are_labelled_separately')],
                [(r['title']+' · '+r['status'],('scenario',r['id'])) for r in records],
                t('scenarios.enter_inspect_scenario_t_trajectory'),route.index,route.scroll)
        if route.kind == 'scenario':
            record=next(r for r in catalogue(self.world()) if r['id']==route.target)
            lines=[record['title'],record['status'],record['description'],record['context'],
                   t('terminal_polish.scenario_source')]
            if curator.allowed(self):
                lines += self.scenario_source(record)
            lines += [t('scenarios.possible_desired_conditions_source_prompts')]
            lines += ['  '+o['title'] for o in record.get('possible_objectives',[])]
            lines += [t('scenarios.conditions_steps')]+record.get('conditions',[])
            bound=objectives_for(record,self.world())
            lines += [t('scenarios.linked_objectives_in_this_world')]+[meaning for _,meaning in bound]
            if not bound:lines.append(t('scenarios.no_objective_is_registered_for'))
            return Screen(t('scenarios.scenario_inspect'),lines,[(self.node_label({**o,'kind':'objective'}),o['id']) for o,_ in bound],
                          t('scenarios.enter_objective_t_recorded_trajectory'),route.index,route.scroll)
        if route.kind == 'network':
            return self.network_screen()
        if route.kind == 'help':
            montreal_help = [
                t('montreal_ui.help.scopes'), t('montreal_ui.help.overview'), t('montreal_ui.help.directory'),
                t('montreal_ui.help.network'), t('montreal_ui.help.source'),
            ]
            general_help = [
                t('help.arrows_move_the_heatmap_cell'),
                t('help.a_matrix_row_offers_expertise'),
                t('help.marks_your_row_and_column'),
                t('help.z_switches_heatmap_numbers_fixed'),
                t('help.uppercase_o_n_w_switch'),
                t('help.a_partially_observed_cell_shows'),
                t('help.w_opens_hack_network_tab'),
                t('help.network_s_scope_l_layer'),
                t('help.playing_is_your_simulated_agency'),
                t('help.diagonal_self_pairings_are_excluded'),
                t('help.m_chooses_a_path_e'),
                t('help.b_or_esc_returns_to'),
                t('help.up_down_select_or_scroll'),
                t('help.contract_explore_decisions_details_network'),
                t('help.pgup_pgdn_scroll_long_content'),
                t('help.a_shows_permitted_actions_for'),
                t('help.h_opens_collective_history_changes'),
                t('help.context_panel_tab_switches_main'),
                t('help.in_a_relationship_j_invites'),
                t('help.in_a_contract_y_accepts'),
                t('help.inbox_f_chooses_a_filter'),
                t('help.p_changes_simulated_perspective_it'),
                t('help.first_names_only_1_2'),
                t('help.opens_typed_commands_including_open'),
                t('help.d_opens_optional_source_and'),
                t('help.network_people_organisations_and_resources'),
                t('help.reconstruct_c_connect_c_contracts'),
                t('help.network_s_changes_scope_l'),
                t('help.matrix_changes_detail_home_returns'),
                t('help.dark_points_are_off_scope'),
                t('help.q_quits_completed_actions_are'),
            ]
            context = len(self.stack) > 1 and self.stack[-2].kind in montreal_network.ROUTES
            lines = [*montreal_help, '', *general_help] if context else [*general_help, '', *montreal_help]
            return Screen(t('help.help_your_path_through_the'), lines,
                          footer=t('montreal_ui.keys.help'), scroll=route.scroll)
        if route.kind == 'details':
            lines = [self.world()['configuration']['world']['title'],
                     t('technical.current_saved_state_version')+str(len(self.current().project('log')))]
            if route.target:
                lines += self.capture(lambda: self.cmd_metadata(route.target))
                for row in profile_statements(self.world(), route.target):
                    origin = row['provenance']
                    lines.append(t('profiles.motivation_source', question=row['raw']['Pourquoi suis-je ici ?'],
                                   source=origin['file'], field=origin['line']))
            return Screen(t('technical.optional_source_technical_details'), lines, scroll=route.scroll)
        if route.kind == 'notice':
            return Screen(route.extra.get('title', t('technical.notice')), route.extra.get('lines', []), scroll=route.scroll)
        # Alternative ecosystem views remain projections over the same world.
        kinds = {'people': 'person', 'organisations': 'organisation', 'resources': 'resource'}
        nodes = self.graph_projection()['nodes']
        if route.kind in kinds:
            nodes = [n for n in nodes if n['kind'] == kinds[route.kind]]
        else:
            nodes = [n for n in nodes if n['kind'] not in {'capacity', 'need', 'evidence'}]
        return self.list_screen(t('terminal.ecosystem')+route.kind.upper(), nodes)

    def scenario_source(self, record):
        provenance = record['provenance']
        lines = [t('terminal.source_provenance_prefix')+provenance['kind'].replace('_', ' ')+' · '+provenance['source_path']]
        if record.get('source_review'):
            lines.append(record['source_review'])
        return lines

    def node_label(self, node):
        style = OBJECTS.get(node['kind'], OBJECTS['evidence'])
        symbol = style.plain if self.plain else style.symbol
        return symbol+' '+(self.aliases().get(node['id'], '')+' ' if node['kind'] in {'agreement','invitation'} else '')+display_label(node)+(
            ' · '+status(node['status'])+t('terminal.outcome')+status(node['outcome_status']) if node['kind'] == 'agreement' else '')

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
            return Screen(t('terminal.historical_title', title=self.label(route.target, world)),
                self.capture(lambda:self.inspect_node(route.target,at=at)), footer=t('profiles.read_only_b_current_context'), scroll=route.scroll)
        if node is None:
            from game_gamer.runtime.curation import canonical
            resolved = canonical(world, route.target)
            links = [(t('profiles.inspect_canonical_profile'), resolved)] if resolved != route.target and self.node(resolved) else []
            return Screen(t('profiles.profile_discovery_updated'),
                          [t('profiles.this_profile_has_a_recorded'),
                           t('profiles.historical_references_remain_available_through')],
                          links, t('profiles.enter_inspect_h_history_b'), route.index, route.scroll)
        actions = self.object_actions(route.target)
        decision_entries = []
        for action in actions:
            title = action_name(action['kind'])
            if action['kind'] == 'respond_contact': title = t('contracts.inspector.accept_invitation') if action['response']=='accept' else t('contracts.inspector.decline_invitation')
            decision_entries.append((title, ('decision', action)))
        if node['kind'] == 'agreement':
            version = node['versions'][node['current_version']-1]
            def acceptance(party):
                role = t('terminal.proposer') if party == node['created_by'] else t('terminal.counterparty')
                receipt = 'accepted' if party in version['acceptances'] else t('line.inspect_node.no_acceptance_recorded')
                return f'{role}: {self.label(party)} · {receipt}'
            lines = [self.contract_title(node['id']), t('contracts.purpose_prefix')+version['terms']['purpose'],
                     t('contracts.proposer_prefix')+self.label(node['created_by']),
                     t('common.status_prefix')+status(node['status'])+t('contracts.inline_outcome_prefix')+status(node['outcome_status']),
                     t('line.inspect_node.terms_version')+str(version['number'])+t('contracts.inspector.amendments_require_renewed_acceptance'),
                     *(acceptance(p) for p in node['parties']),
                     t('contracts.proposal_requires_party_acceptance'),
                     t('contracts.inspector.governing_policy')+self.label(version['policy_id'])]
            kinds = {a['kind'] for a in actions}
            details = [self.label(r['actor_id'])+': '+r['description'] for r in version['terms']['responsibilities']]
            details += [t('contracts.inspector.condition')+c for c in version['terms']['conditions']]
            details += [t('contracts.inspector.resource')+self.label(r['resource_id'])+f" × {r['quantity']}" for r in version['resources']]
            details += [t('laboratory.inspect_contract.valid_until')+version['valid_until'],
                        t('contracts.inspector.party_acceptance_and_institutional_authorisation'),
                        t('contracts.inspector.reject_declines_a_proposal_withdraw'),
                        t('contracts.inspector.evidence')+str(len(node['evidence_ids']))+t('contracts.inspector.record_s_d_source_details')]
            # One readable link per participant, despite proposer/party relations.
            linked = [*node['parties'],node['objective_id'],version['policy_id'],
                      *(r['resource_id'] for r in version['resources']),*node['evidence_ids']]
            entries = [(self.node_label(self.node(key)),key) for key in dict.fromkeys(linked)]
            entries += [(t('contracts.inspector.relevant_scenario')+r['title'],('scenario',r['id'])) for r in scenarios_for(node['objective_id'],world)]
            decision_entries = [
                (f'[{DECISION_KEYS[a["kind"]][0]}] {label}' if a['kind'] in DECISION_KEYS else label, ('decision', a))
                for label, (_, a) in decision_entries]
            route.index = min(route.index, max(0, len(entries)-1))
            route.decision_index = min(route.decision_index, max(0, len(decision_entries)-1))
            if route.region == 'decisions' and not decision_entries:
                route.region = 'explore'
            footer = '  '.join(f'{shortcut} {t(label)}' for kind, (shortcut, label) in DECISION_KEYS.items() if kind in kinds)
            if self.session:
                for option in action_options(self.current(), self.session.actor, include_attendance=False):
                    action = option['action']
                    if action.get('agreement_id') == route.target and option['errors']:
                        details.append(action_name(action['kind']) + ' · ' +
                                       ', '.join(error.replace('_', ' ') for error in option['errors']))
            return inspector(t('contracts.inspector.contract_inspector'), lines, links=entries, decisions=decision_entries,
                             details=details, route=route, footer=footer+t('contracts.inspector.tab_regions_a_actions_h'),
                             wrap_entries=False)
        if node['kind'] == 'invitation':
            lines = [self.aliases().get(node['id'],t('objects.invitation.singular'))+t('contact.inspector.invitation_to_connect')+status(node['status']),
                     t('contact.inspector.direction', sender=self.label(node['source_id']), recipient=self.label(node['target_id'])),
                     node['message'], t('contracts.purpose_prefix')+(node['purpose'] or t('contact.inspector.explore_a_possible_collaboration')),
                     t('contact.inspector.simulation_contact_only_no_contractual')]
            if node.get('response'): lines.append(t('contact.inspector.response')+node['response']['decision']+' · '+node['response']['message'])
            if node['status']=='accepted': lines.append(t('contact.inspector.connection_acknowledged_a_contract_remains'))
            elif not actions: lines.append(t('contact.inspector.no_decision_is_available_to'))
            entries = [(self.node_label(self.node(p)),p) for p in (node['source_id'],node['target_id'])]
            if self.playing_actor in (node['source_id'],node['target_id']):
                other = node['target_id'] if node['source_id']==self.playing_actor else node['source_id']
                entries += [(t('contracts.propose_directly'),('propose_to',other))]
                entries += [(t('contact.inspector.invite_to_connect_again'),('invite_to',other))]
            entries = decision_entries+entries
            return Screen(t('contact.inspector.invitation_connect'),lines,entries,t('contact.inspector.enter_choose_a_actions_h'),route.index,route.scroll)
        if node['id'] in world['actors']:
            lines = [display_label(node),t('profiles.affiliation')+(', '.join(affiliations(world,node['id'])) or t('common.unknown_or_not_recorded'))]
            statements = profile_statements(world, node['id'])
            if statements:
                if 'motivation' in node:
                    lines.append(t('profiles.motivation')+(node['motivation'] or t('common.not_recorded')))
                else:
                    motivations = dict.fromkeys(row['raw']['Pourquoi suis-je ici ?'].strip() for row in statements)
                    lines.append(t('profiles.motivation') + (' / '.join(text for text in motivations if text)
                                                            or t('common.not_recorded')))
            for table, label in (('capacities',t('objects.offers')),('needs',t('objects.need.plural'))):
                records = [r for r in world[table].values() if r['actor_id']==node['id']]
                lines.append(label+f' ({len(records)}): '+(', '.join(r['domain'] for r in records[:3]) or t('common.not_recorded'))+(' …' if len(records)>3 else ''))
            connections = [r for r in world['relationships'].values() if r['kind']=='acknowledged_connection' and node['id'] in (r['source_id'],r['target_id'])]
            lines += [t('profiles.acknowledged_connections', connections_count=len(connections)), t('profiles.potential_complementarities_are_declared_possibilities')]
            entries = []
            if self.playing_actor and self.playing_actor!=node['id'] and node['kind']=='person':
                if world['actors'][self.playing_actor]['kind']=='person':
                    entries += [(t('contact.invite'),('invite_to',node['id']))]
                if self.proposal_permitted(node['id']):
                    entries += [(t('contracts.propose_directly'),('propose_to',node['id']))]
                else:lines.append(t('profiles.contract_proposal_unavailable_for_this'))
            entries += [(t('profiles.complete_offers_and_needs'),('expertise',node['id']))]
            contracts = [a for a in world['agreements'].values() if node['id'] in a['parties']]
            entries += [(t('profiles.contract')+self.contract_title(a['id']),a['id']) for a in contracts]
            for r in connections:
                other = r['target_id'] if r['source_id']==node['id'] else r['source_id']
                entries.append((t('profiles.acknowledged_connection')+self.label(other), r['invitation_id']))
            potentials = self.current().derive_possibilities(world)
            relevant = []
            for p in potentials:
                if node['id'] in (p['source_id'],p['target_id']):
                    other=p['target_id'] if p['source_id']==node['id'] else p['source_id']
                    if other not in relevant: relevant.append(other)
            entries += [(t('profiles.potential')+self.label(p),('relation_to',(node['id'],p))) for p in relevant[:4]]
            lines += [t('profiles.potential_counterparties_w_opens_the', relevant_count=len(relevant))]
            return Screen(t('objects.inspect_title', kind=node['kind'].upper()),lines,entries,t('profiles.enter_choose_a_actions_w'),route.index,route.scroll)
        lines = self.capture(lambda:self.inspect_node(route.target))
        entries = [(self.node_label(n),n['id']) for n in self.neighbours(route.target)]
        if node['kind']=='objective': entries = [(t('objects.inspector.scenario')+r['title'],('scenario',r['id'])) for r in scenarios_for(route.target,world)]+entries
        return Screen(t('objects.inspect_title', kind=node['kind'].upper()),lines,entries,t('objects.inspector.enter_follow_link_h_history'),route.index,route.scroll)

    def contract_title(self, target):
        return self.aliases().get(target, t('objects.agreement.singular'))+' · '+self.label(target)

    def list_screen(self, title, nodes, lines=None, footer=None):
        footer = t('terminal.enter_inspect_search') if footer is None else footer
        nodes = [n for n in nodes if folded(self.route.query) in folded(display_label(n))]
        nodes.sort(key=lambda n: (folded(display_label(n)), n['id']))
        self.route.index = min(self.route.index, max(0, len(nodes)-1))
        entries = [(self.node_label(n), n['id']) for n in nodes]
        context = list(lines or [])
        if self.route.query:
            context.append(t('controls.search_prefix')+self.route.query)
        if not nodes:
            context.append(t('terminal.no_matching_objects_changes_the'))
        return Screen(title, context, entries, footer, self.route.index, self.route.scroll)

    def matrix_screen(self):
        projection = matrix(self.world()); self._matrix = projection
        route = self.route; roster = projection['actors']; count = len(roster)
        kind = route.extra.get('matrix_kind', 'W'); numeric = route.extra.get('numeric', False)
        domains = projection['domains']; axis = roster if kind=='W' else [{'id':code,'label':projection['vocabulary'][code]} for code in domains]
        if not count or not axis:
            return Screen(t('matrix.ecosystem_matrix_explorer'), [t('matrix.no_eligible_matrix_observations_in'), t('matrix.x_opens_alternative_ecosystem_views')])
        route.row = min(route.row,count-1); route.column = min(route.column,len(axis)-1)
        value = projection[kind][route.row][route.column]
        meaning = t('matrix.w_o_n_t_rows') if kind=='W' else (t('matrix.o_offers') if kind=='O' else t('matrix.n_needs'))+t('matrix.people_expertise_domains')
        exact = score_text(cell(projection,route.row,route.column)) if kind=='W' else (t('common.unknown') if value is None else str(value))
        lines = [meaning,
            t('controls.selected_prefix')+display_label(roster[route.row])+' → '+display_label(axis[route.column])+t('matrix.exact_matches')+exact,
            t('matrix.your_row_column_selection_unknown') if kind=='W' else t('matrix.current_player_selection_1_selected'),
            t('matrix.scale')+' '.join((b.ascii if self.plain else b.glyph)+'='+b.label for b in BANDS)+t('matrix.z_heatmap_numbers') if kind=='W' else t('matrix.fixed_categories_1_selected_0')]
        styles=[]; highlights=set()
        if kind=='W' and not numeric:
            column=len(t('matrix.scale'))
            for item in BANDS:
                label=(item.ascii if self.plain else item.glyph)+'='+item.label
                styles.append((3,column,len(label),'#111111' if item.maximum is None or item.maximum>=10 else '#eee8d5',item.colour,False));column+=len(label)+1
        def labels(records):
            return [AxisLabel(item['id'], display_label(item)) for item in records]

        view = MatrixView(labels(roster), labels(axis), projection[kind], exclude_self=kind == 'W')
        grid = render_matrix(view, route.matrix, row=route.row, column=route.column, width=self.width-2,
                             height=self.height-19, own_id=self.playing_actor, numeric=numeric,
                             plain=self.plain, incidence=kind != 'W')
        start = len(lines)
        lines.extend(grid.lines)
        styles.extend((r+start, c, n, fg, bg, bold) for r,c,n,fg,bg,bold in grid.styles)
        highlights.update(r+start for r in grid.highlights)
        lines.append(t('matrix.rows_columns', value=grid.rows.start + 1, stop=grid.rows.stop, count=count, value_2=grid.columns.start + 1, stop_2=grid.columns.stop, axis_count=len(axis)))
        lines.append(t('matrix.matrix_detail_columns_overflow_inspect', value=route.matrix.detail.name.title(), cell_width=grid.cell_width))
        if kind=='W':
            detail=cell(projection,route.row,route.column)
            lines.append(t('matrix.matching_domains')+(', '.join(detail['matching_domains']) or (t('common.unknown') if detail['value'] is None else t('matrix.none_in_the_observed_vocabulary'))))
        else: lines.append(t('matrix.domain')+projection['vocabulary'][domains[route.column]])
        lines.append(t('matrix.expertise.world_state')+str(len(self.current().project('log')))+t('matrix.shared_vocabulary_and_snapshot_across'))
        return Screen(t('terminal.ecosystem')+(t('matrix.complementarity_matrix') if kind=='W' else t('matrix.offers_o') if kind=='O' else t('matrix.needs_n'))+' / '+(t('matrix.numeric') if numeric else t('matrix.heatmap')),lines,
            footer=t('matrix.o_n_w_arrows_cell'),
            highlights=highlights, styles=styles, fixed_rows=set(range(start,start+len(grid.lines))))

    def cell_screen(self):
        projection = matrix(self.world()); ids=[a['id'] for a in projection['actors']]
        relation=self.route.extra.get('relation')
        if relation:
            self.route.row,self.route.column=(ids.index(key) for key in relation)
        detail = cell(projection, self.route.row, self.route.column)
        reverse=cell(projection,self.route.column,self.route.row)
        self._cell = detail
        self.route.extra['relation']=(detail['provider']['id'],detail['requester']['id'])
        lines = [t('matrix.pair.offers_needs')+display_label(detail['provider'])+' → '+display_label(detail['requester']),
                 score_text(detail)+t('matrix.pair.matching_declared_expertise_domain_s'),
                 t('matrix.pair.matching_expertise')+(', '.join(detail['matching_domains']) or t('matrix.pair.none_confirmed')),
                 t('matrix.pair.reverse')+display_label(reverse['provider'])+' → '+display_label(reverse['requester'])+
                 ' · '+score_text(reverse)+t('matrix.pair.matching_domain_s'),
                 t('matrix.pair.reverse_expertise')+(', '.join(reverse['matching_domains']) or t('matrix.pair.none_confirmed')),
                 t('matrix.pair.scores_describe_potential_not_acknowledged')]
        lines.append(t('matrix.pair.answer_coverage_offers')+detail['offer']['state']+' / needs '+detail['need']['state'])
        pair={detail['provider']['id'],detail['requester']['id']}
        if detail['self_pairing']:lines.append(t('matrix.pair.self_pairing_excluded_from_gameplay'))
        elif self.playing_actor not in pair:lines.append(t('matrix.pair.observation_only_you_are_not'))
        else:lines.append(t('matrix.pair.you_may_propose_new_terms')+self.label(self.playing_actor)+t('matrix.pair.they_require_a_separate_decision'))
        if detail['value'] is None:lines.append(t('matrix.pair.incomplete_coverage_confirmed_matches_form'))
        elif detail['value']==0:lines.append(t('matrix.pair.no_shared_selections_in_this'))
        entries = [(t('matrix.pair.inspect_offers')+display_label(detail['provider']), detail['provider']['id']),
                   (t('matrix.pair.inspect_needs')+display_label(detail['requester']), detail['requester']['id'])]
        entries += [(t('profiles.contract')+self.contract_title(a['id']),a['id']) for a in self.world()['agreements'].values() if pair <= set(a['parties'])]
        if self.playing_actor in pair and not detail['self_pairing']:
            other = next(p for p in pair if p!=self.playing_actor)
            entries += [(t('contact.invite'),('invite_to',other))]
            if self.proposal_permitted(other):entries += [(t('contracts.propose_directly'),('propose_to',other))]
        entries += [(t('matrix.pair.view_in_network'),('network_of',detail['provider']['id']))]
        if self.route.extra.get('new_contract'):
            self.route.index=next((i for i,(_,key) in enumerate(entries) if key==self.route.extra['new_contract']),self.route.index)
            self.route.extra.pop('new_contract')
        self.route.index=min(self.route.index,len(entries)-1)
        lines.insert(0,t('matrix.pair.selected_link')+entries[self.route.index][0])
        contracts=[a for a in self.world()['agreements'].values() if pair<=set(a['parties'])]
        if contracts:
            lines.insert(1,t('matrix.pair.contracts_here')+'; '.join(self.contract_title(a['id'])+' · '+status(a['status']) for a in contracts))
        return Screen(t('matrix.pair.a_potential_connection_potential_complementarity'), lines, entries,
                      t('matrix.pair.enter_choose_j_invite_k')+t('matrix.pair.d_source_details'),
                      self.route.index, self.route.scroll)

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
        limit = route.extra.setdefault('page_limit', 6 if self.width < 85 or self.height < 26 else 8)
        visual=focus_graph(self.graph_projection(),route.target,related=related,query=route.query,
                           offset=route.extra.get('offset',0),limit=limit,
                           scope=route.extra.get('scope','neighbourhood'),categories=route.extra.get('categories'),
                           three_d=route.extra.get('three_d',False), object_type=route.extra.get('object_type'))
        if not visual['nodes']:return Screen(t('network.network_hack_terminal'),[t('network.no_matching_graph_nodes_search')])
        route.index=min(route.index,len(visual['nodes'])-1);selected=visual['nodes'][route.index]
        route.extra['offset'] = visual['offset']
        canvas_width = self.width-2
        zoom = route.extra.get('zoom', 1.)
        rotation = route.extra.get('yaw' if route.extra.get('three_d') else 'angle', 0.)
        lines=[t('controls.selected_prefix')+self.node_label(selected)+t('network.centre')+self.label(route.target),
               t('network.scope')+route.extra.get('scope_label',t('network.player_centred_neighbourhood') if route.target==self.playing_actor else t('network.selected_actor_neighbourhood'))+
               (t('network.camera.experimental_3d') if route.extra.get('three_d') else t('network.camera.planar')),
               t('network.showing_nodes_edges_bundles', nodes_count=len(visual['nodes']), full_node_count=visual['full_node_count'], rendered_relationship_count=visual['rendered_relationship_count'], full_relationship_count=visual['full_relationship_count'], edges_count=len(visual['edges'])),
               t('network.types')+object_type_label(route.extra.get('object_type'))+t('network.layers')+(', '.join(category_label(category) for category in route.extra['categories']) if route.extra.get('categories') else t('controls.all'))+
               t('network.zoom_x_rotation_rad', zoom=zoom, rotation=rotation),
               t('network.context_off_scope_actors_background', context_actor_ids_count=len(visual['context_actor_ids']), value=route.extra.get('background', 'dim').title(), value_2='o' if self.plain else '∘'),
               t('network.neighbours_page', value=visual['offset'] + 1 if visual['total'] else 0, value_2=min(visual['total'], visual['offset'] + limit), total=visual['total'])]
        # Four header and three footer rows are reserved by CursesViewport.
        canvas_height = self.height-7-len(lines)
        lines = [line if len(line) <= canvas_width else line[:max(0,canvas_width-3)]+'...' for line in lines]
        self._network=visual
        entries = [(self.node_label(n),n['id']) for n in visual['nodes']]
        footer = t('network.enter_inspect_tab_view_t')
        if route.region == 'explore' or canvas_height < 3 or canvas_width < 12:
            return Screen(t('network.ecosystem_network_object_list'), lines, entries, footer,
                          route.index, route.scroll)
        canvas, spans = draw_graph(visual,canvas_width,canvas_height,selected=selected['id'],plain=self.plain,
            angle=route.extra.get('angle',0.),zoom=zoom,
            yaw=rotation,pitch=route.extra.get('pitch',0.),background=route.extra.get('background','dim'),
            labels={n['id']:self.aliases()[n['id']]+' '+display_label(n) for n in visual['nodes'] if n['kind']=='agreement'})
        start = len(lines)
        styles=[(row+start,column,length,fg,bg,bold) for row,column,length,fg,bg,bold in spans]
        return Screen(t('network.ecosystem_network_hack_renderer'),lines+canvas,entries,footer,route.index,0,
                      styles=styles,show_entries=False,raster_start=start)

    def handle(self, key, screen):
        route = self.route
        if key == 'resize':
            return
        if route.kind.startswith('curator') and screen.panel is not None:
            if curation_panel.handle(self, key, screen):
                return
        if key == 'H':
            self.push('history')
            return
        if route.kind in {'history', 'history_event', 'history_object'} and history_key(self, key, screen):
            return
        if route.kind in montreal_network.ROUTES and montreal_network.handle(self, key, screen):
            return
        from .reconstruction_transitions import dispatch
        if dispatch(self,key,screen):
            return
        if route.kind == 'reconstruction_intro' and not route.extra.get('opening_finished', False):
            route.extra['opening_finished'] = True
            return
        if key == 'q':
            self.finished = True; return
        if key in {'b', 'esc'}:
            self.back(); return
        if key in MODE_KEYS:
            self.resume_mode(MODE_KEYS[key]); return
        if key == 'm':
            self.choose_mode(); return
        if key == 'p':
            self.select_actor(); return
        if key == 'u':
            curation_panel.open_panel(self, screen)
            return
        if route.kind.startswith('curator') and curator.handle(self, key, screen):
            return
        if route.kind == 'tutorial' and tutorial_key(self, key, screen):
            return
        if route.kind == 'matrix' and route.matrix.handle(key):
            if key == 'home':
                route.row = route.column = 0
            return
        if route.kind=='matrix' and key in {'O','N','W'}:
            previous = route.extra.get('matrix_kind','W')
            route.extra[previous+'_column'] = route.column
            route.extra['matrix_kind'] = key
            route.column = route.extra.get(key+'_column',0)
            return
        if route.kind=='inbox' and key=='F':
            route.extra['category'] = self.choose(t('terminal.inbox_filter'), list(INBOX_CATEGORIES), inbox_category)
            route.index=route.scroll=0; return
        if route.kind=='inspect' and key in {'y','j','R','X'}:
            kinds = {'y':('accept','respond_contact'),'j':('amend',),'R':('reject','respond_contact'),'X':('withdraw','withdraw_contact')}
            candidate = next((c for c in self.object_actions(route.target) if c['kind'] in kinds[key]
                              and (c['kind']!='respond_contact' or c['response']==('accept' if key=='y' else 'decline'))),None)
            if candidate: self.execute_action(candidate)
            else: self.notice = t('terminal.that_decision_is_unavailable_for')
            return
        if route.kind=='cell' and key in {'j','k'}:
            pair=self.focused_relation
            if not pair or self.playing_actor not in pair or pair[0]==pair[1]:
                self.notice=t('terminal.you_are_observing_this_pair'); return
            other = next(p for p in pair if p!=self.playing_actor)
            self.contact_to(other) if key=='j' else self.propose_to(other)
            return
        if key in {'c', 'i', '?', 't'}:
            self.push({'c': 'contracts', 'i': 'inbox', '?': 'help', 't': 'trajectory'}[key]); return
        if key == 'v':
            game = self.current()
            self.notice = t('terminal.replay_consistent')+str(game.replay().get_world() == game.get_world()); return
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
            if key == 'T':
                selected = screen.entries[route.index][1] if screen.entries else route.target
                kind = self.choose(t('network.object_types.title'), list(OBJECT_TYPES), lambda name: object_type_label(OBJECT_TYPES[name]))
                route.extra.update(object_type=OBJECT_TYPES[kind], offset=0)
                route.index = 0
                refreshed = self.network_screen()
                route.index = next((i for i, (_, ident) in enumerate(refreshed.entries) if ident == selected), 0)
                route.reveal = True
                return
            if key == 'B':
                route.extra['background'] = self.choose(t('network.background.title'), ['dim', 'hidden', 'full'], str.title)
                return
            if key=='S':
                labels=[t('terminal.whole_graph'),t('network.player_centred_neighbourhood'),t('network.selected_actor_neighbourhood'),t('terminal.contract_neighbourhood'),t('terminal.invitation_and_connection_network')]
                choice=self.choose(t('network.scope.title'),labels,str)
                if choice==labels[1]:route.target=self.playing_actor or route.target
                elif choice==labels[2]:route.target=self.picker(t('terminal.centre_on_person'),people(self.world()))['id']
                elif choice==labels[3]:
                    route.target=self.picker(t('terminal.centre_on_contract'),[n for n in self.graph_projection()['nodes'] if n['kind']=='agreement'])['id']
                route.extra.update(scope='whole' if choice==labels[0] else 'connections' if choice==labels[4] else 'neighbourhood',scope_label=choice,offset=0)
                route.index=0;return
            if key=='L':
                selected=self.choose(t('terminal.network_layer'),[None, *CATEGORIES], lambda category: category_label(category) if category else t('terminal.all_layers'))
                route.extra['categories']=None if selected is None else [selected]
                route.extra['offset']=route.index=0;return
            if key=='3':route.extra['three_d']=not route.extra.get('three_d',False);return
            if key in {'{','}'}:
                if route.extra.get('three_d'):route.extra['pitch']=route.extra.get('pitch',0.)+(-.2 if key=='{' else .2)
                else:self.notice=t('terminal.shortcut_3_enables_the_experimental_yaw')
                return
            if key in {'up','down'}:
                route.index=(route.index+(-1 if key=='up' else 1))%max(1,len(screen.entries))
                route.reveal = True
                return
            if key in {'[',']'}:
                limit = route.extra.setdefault('page_limit', 6 if self.width < 85 or self.height < 26 else 8)
                route.extra['offset']=max(0,route.extra.get('offset',0)+(-limit if key=='[' else limit));route.index=0;return
            if key=='f' and screen.entries:
                route.target=screen.entries[route.index][1];route.index=0
                route.extra.update(offset=0,scope='neighbourhood',scope_label=t('terminal.selected_object_neighbourhood'));return
            if key=='r':
                axis='yaw' if route.extra.get('three_d') else 'angle'
                route.extra[axis]=route.extra.get(axis,0.)+.3;return
            if key in {'+','-'}:
                route.extra['zoom']=max(.4,min(2.,route.extra.get('zoom',1.)*(1.2 if key=='+' else 1/1.2)));return
        if key == 'x':
            view = self.choose(t('terminal.ecosystem_views'), ['matrix', 'network', 'people', 'organisations', 'resources'], str.capitalize)
            if view == 'matrix':
                self.switch_mode('ecosystem')
            elif view=='network':self.open_network()
            else:
                self.push(view)
            return
        if key == '/':
            query = self.read(t('terminal.search_by_first_name_or'))
            if route.kind == 'matrix':
                projection=matrix(self.world());roster=projection['actors'];kind=route.extra.get('matrix_kind','W')
                matches = [{**a,'axis':'actor'} for a in roster if folded(query) in folded(display_label(a))]
                matches += [{'id':code,'label':label,'axis':'domain'} for code,label in projection['vocabulary'].items()
                            if folded(query) in folded(label)]
                item = self.picker(t('terminal.find_matrix_participant_domain'),matches)
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
            self.typed_command(self.read(t('terminal.command_for_help'))); return
        if key == 'd':
            if route.kind == 'scenario':
                record = next(item for item in catalogue(self.world()) if item['id'] == route.target)
                self.push('notice', title=t('terminal.optional_exact_source_references'),
                          lines=self.scenario_source(record))
            elif route.kind in {'cell','incidence'}:
                lines = [t('matrix.expertise.world_state')+str(self._frame_revision)]
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
                self.push('notice', title=t('terminal.optional_exact_source_references'), lines=lines)
            else:
                self.push('details', route.target)
            return
        if key == 'h':
            target = self.selected_target(screen)
            if target:
                self.push('history', target)
            else:
                self.push('history')
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
                    self.notice = t('terminal.this_development_role_is_outside')
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
            self.notice = t('terminal.reading_details_tab_returns_to')
        elif key == 'enter' and screen.entries:
            target = screen.entries[min(route.index, len(screen.entries)-1)][1]
            from game_gamer.transitions import Choice
            if isinstance(target,Choice):
                from .reconstruction_transitions import REGISTRY
                REGISTRY.execute(target.transition_id,self,payload=target.payload)
            elif route.kind == 'history':
                self.push('inspect', route.target, at=target)
            elif isinstance(target,tuple):
                kind,value=target
                if kind=='decision': self.execute_action(value)
                elif kind=='invite_to': self.contact_to(value)
                elif kind=='propose_to': self.propose_to(value)
                elif kind=='network_of': self.push('network',value)
                elif kind=='relation_to': self.push('cell',relation=value)
                elif kind=='choose_interaction':
                    target=self.picker(t('terminal.choose_a_person_2'),[a for a in people(self.world()) if a['id']!=self.playing_actor])['id']
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
            self.notice = t('terminal.press_for_contextual_help_arrows')

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
        self.write(t('line.collect_action.proposing_actor')+self.label(self.session.actor))
        self.write(t('terminal.counterparties')+', '.join(self.label(p) for p in payload['parties'] if p != self.session.actor))
        payload['label'] = self.ask(t('laboratory.collect_action.contract_title'),default=payload['label'])
        payload['terms']['purpose'] = self.ask(t('line.collect_action.purpose_of_this_agreement'),default=payload['terms']['purpose'])
        for obligation in payload['terms']['responsibilities']:
            prompt = t('line.collect_action.your_offered_contribution') if obligation['actor_id'] == self.session.actor else t('line.collect_action.contribution_requested_from')+self.label(obligation['actor_id'])+'?'
            obligation['description'] = self.ask(prompt,default=obligation['description'])
        condition = self.ask(t('line.collect_action.optional_conditions_blank_for_none'),default='; '.join(payload['terms']['conditions']),parse=lambda value:value.strip())
        payload['terms']['conditions'] = [condition] if condition else []
        self.write(t('contracts.inspector.governing_policy')+self.label(payload['policy_id']))
        for resource in payload['resources']:
            self.write(t('terminal.scenario_resource')+self.label(resource['resource_id'])+f" × {resource['quantity']}")
        payload=self.refine_proposal(payload,game.get_world())
        self.write(t('line.collect_action.who_is_affected')+', '.join(self.label(p) for p in payload['parties']))
        self.write(t('line.collect_action.what_will_change')+t(ACTION_EFFECTS['propose']))
        self.write(t('terminal.these_are_suggested_terms_other'))
        if not self.confirm(t('controls.confirm_continue')):
            raise Cancelled
        return payload

    def refine_proposal(self,payload,world):
        context=self.contact_context()
        invitation=next((r.target for r in reversed(self.stack) if r.target in world['relationships']
                         and world['relationships'][r.target]['kind']=='contact_invitation'),None)
        if context or invitation:payload['interaction_context']={'relationship':context,'invitation_id':invitation}
        while True:
            choices=[t('contracts.settings.keep_these_settings'), t('contracts.settings.change_validity'), t('contracts.settings.choose_governance_policy'), t('contracts.settings.choose_linked_objective')]
            selected=self.choose(t('contracts.settings.agreement_settings_valid_until')+payload['valid_until']+t('contracts.settings.policy')+self.label(payload['policy_id'])+
                t('contracts.settings.objective')+self.label(payload['objective_id']),choices,str)
            if selected==choices[0]:return payload
            if selected==choices[1]:payload['valid_until']=self.ask(t('contracts.settings.valid_until_iso_date_and'),default=payload['valid_until'])
            elif selected==choices[2]:payload['policy_id']=self.picker(t('forms.governance_policy'),list(world['governance'].values()))['id']
            else:payload['objective_id']=self.picker(t('contracts.settings.linked_objective'),list(world['objectives'].values()))['id']

    def act(self, screen):
        if not self.session:
            self.notice = t('terminal.p_choose_a_simulated_player'); return
        if self.route.extra.get('at'):
            self.notice = t('terminal.historical_views_are_read_only'); return
        target = self.selected_target(screen)
        if self.route.kind == 'cell':
            detail = self._cell
            if detail['self_pairing']:
                self.notice = t('terminal.self_pairing_is_excluded_from'); return
            pair = [detail['provider']['id'], detail['requester']['id']]
            if self.session.actor not in pair:
                self.notice = t('terminal.choose_your_own_row_or'); return
            target = next(p for p in pair if p != self.session.actor)
        self.selected = target
        world = self.world()
        version, candidates = self.session.available_actions()
        if target in world['actors']:
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
            self.notice = t('terminal.no_action_is_permitted_for'); return
        action = self.choose(t('contracts.actions_title'), candidates, lambda c: action_name(c['kind'])+(' · '+c['response'] if c.get('response') else ''))
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
            self.notice=t('terminal.choose_another_person_and_a');return
        if self.route.extra.get('at') is not None:
            self.notice=t('terminal.historical_views_are_read_only_2');return
        if self.world()['actors'].get(target,{}).get('kind')!='person' or self.world()['actors'][self.playing_actor]['kind']!='person':
            self.notice=t('terminal.contact_invitations_currently_require_two');return
        context=self.contact_context()
        if context:
            projection=matrix(self.world())
            self.write(t('terminal.relevant_declared_domains')+(', '.join(projection['vocabulary'][code] for code in context['matching_codes']) or t('terminal.none_recorded')))
        self._proposal_target=target
        self.execute_action({'kind':'send_contact','recipient_id':target,'context':context})

    def propose_to(self, target):
        if not self.playing_actor or self.playing_actor==target:
            self.notice=t('terminal.choose_another_person_and_a');return
        self._direct_proposal(target)

    def _direct_proposal(self,target):
        if self.route.extra.get('at') is not None:
            self.notice=t('terminal.historical_views_are_read_only_2');return
        if not self.proposal_permitted(target):
            self.notice=t('terminal.a_new_proposal_is_unavailable');return
        self._proposal_target=target
        self.execute_action({'kind':'propose'})

    def proposal_permitted(self,target):
        if not self.playing_actor or target==self.playing_actor:return False
        template=self.world()['configuration']['world'].get('proposal')
        if template:
            return template['id'] not in self.world()['agreements'] and {target,self.playing_actor}<=set(template['parties'])
        return target!='simulation-verifier' and self.playing_actor!='simulation-verifier'

    def submit(self, payload, version):
        previous_revision = self._frame_revision
        result = super().submit(payload, version)
        record_receipt(self, result, previous_revision)
        return result

    def execute_action(self, action, *, version=None):
        if not self.session or self.route.extra.get('at') is not None:
            self.notice=t('terminal.actions_require_a_simulated_player');return
        if version is None:version=len(self.current().project('log'))
        self.reset_buffer()
        if action['kind']=='send_contact' and action.get('context'):
            vocabulary=matrix(self.world())['vocabulary']
            self.write(t('terminal.observed_context')+self.label(action['context']['provider_id'])+' → '+self.label(action['context']['requester_id']))
            self.write(t('terminal.relevant_declared_domains')+', '.join(vocabulary[c] for c in action['context']['matching_codes']))
        with action_form(self.viewport):
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
                self.notice=t('terminal.invitation_sent_in_game_delivery') if payload['kind']=='send_contact' else t('terminal.invitation_saved_contact_and_contractual')
            else:self.notice = t('terminal.contract_created_proposed_acceptance_is') if payload['kind'] == 'propose' else t('terminal.saved_current_version_acceptance_and')
        else:
            self.notice = t('feedback.no_state_changed')+error_list(result['errors'])
        return result

    def typed_command(self, raw):
        from .commands import parse
        command, arg = parse(raw)
        if not command:
            self.notice = t('terminal.unknown_command_opens_help'); return
        name = command.name
        if name in MODES:
            self.resume_mode(name)
        elif name == 'paths':
            self.choose_mode()
        elif name in {'open', 'history', 'metadata', 'actions'}:
            target = resolve(self.world(), arg, selected=self.route.target) if arg else self.route.target
            if target is None:
                target = self.picker(t('controls.choose_object'), self.graph_projection()['nodes'])['id']
            if name == 'actions':
                self.push('inspect', target)
                self.act(Screen(t('controls.action'), entries=[('', target)]))
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
                target=self.picker(t('contact.choose_recipient'), [a for a in people(self.world()) if a['id']!=self.playing_actor])['id']
            self.contact_to(target)
        elif name == 'back': self.back()
        elif name == 'quit': self.finished = True
        elif name == 'list': self.open_network()
        elif name == 'replay': self.handle('v', Screen(t('terminal.replay')))
        elif name == 'search':
            if self.route.kind == 'matrix':
                roster = matrix(self.world())['actors']
                actor = self.picker(t('terminal.find_matrix_participant'), [a for a in roster if folded(arg) in folded(display_label(a))])
                self.route.row = self.route.column = next(i for i,a in enumerate(roster) if a['id'] == actor['id'])
            else:
                self.route.query = arg; self.route.index = 0
        elif name == 'past':
            if not arg:
                self.push('history', self.route.target or self.picker(t('controls.choose_object'), self.graph_projection()['nodes'])['id'])
            else:
                sequence, _, reference = arg.partition(' ')
                target = resolve(self.world(), reference, selected=self.route.target)
                if target is None:
                    target = self.picker(t('controls.choose_object'), self.graph_projection()['nodes'])['id']
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


def run_fullscreen(game, *, store=None, plain=False, explore=False,transition_trace=None):
    return run_curses(lambda viewport, plain: FullScreenTerminal(
        game, viewport=viewport, store=store, plain=plain, explore=explore,
        transition_trace=transition_trace).run(), plain=plain)
