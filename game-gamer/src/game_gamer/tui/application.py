"""Interactive simulation using only the public Game-Gamer engine."""

import sys
from collections import Counter
from uuid import uuid4

from game_gamer import ActionSubmission, Collective, SimulationBinding, epistemic_status

from .forms import ActionForms
from .i18n import t
from .matrix import AxisLabel, MatrixView, render_matrix
from .navigation import MODE_KEYS, NavigationState, navigation_label
from .network import (
    CATEGORIES,
    OBJECT_TYPES,
    category_label,
    draw_graph,
    focus_graph,
    object_type_label,
)
from .screen import Cancelled, Screen, inspector, run_screens
from .text import label
from .viewport import LineViewport, action_form, run_curses, supported
from .visual import graph_pages

_SHORTCUTS = {'y': {'accept', 'respond_contact', 'respond_invitation'}, 'j': {'amend'},
              'R': {'reject', 'respond_contact', 'respond_invitation'}, 'X': {'withdraw', 'withdraw_contact'}}
_MODE_NAMES = ('ecosystem', 'gathering', 'scenarios')


def action_label(action):
    kind = action['kind'].replace('_', ' ').capitalize().replace('Authorize', 'Authorise').replace('Fulfill', 'Fulfil')
    return kind + (' · ' + action['response'] if 'response' in action else '')


class TerminalGame:
    def __init__(self, *, collective: Collective, binding: SimulationBinding | None = None, viewport=None,
                 plain=False, hot_seat=False):
        self.collective, self.binding, self.viewport = collective, binding, viewport
        self.plain, self.hot_seat = plain, hot_seat
        self.navigation = NavigationState()
        self.notice = ''
        self.finished = False
        self.forms = ActionForms(self)

    @property
    def route(self):
        return self.navigation.route

    def run(self):
        if self.viewport is not None:
            return self._run()
        if supported(sys.stdin, sys.stdout):
            return run_curses(self._curses, plain=self.plain)
        self.viewport = LineViewport(sys.stdin, sys.stdout)
        self.plain = True
        return self._run()

    def _curses(self, viewport, plain):
        self.viewport, self.plain = viewport, plain
        return self._run()

    def _run(self):
        try:
            self.prepare_screen()
            if self.binding is None:
                self.select_player()
            run_screens(self)
        except (EOFError, KeyboardInterrupt, Cancelled):
            pass
        return self.collective

    def prepare_screen(self):
        self.width, self.height = self.viewport.size()
        key = (self.collective.scope_id, self.collective.revision, self.route.extra.get('at'))
        if getattr(self, '_snapshot_key', None) == key:
            return
        self.snapshot = self.collective.project(at=self.route.extra.get('at'))
        self._snapshot_key = (key[0], self.snapshot['version'] if key[2] is None else key[1], key[2])
        self.world = self.snapshot['world']
        self.graph = self.snapshot['network']

    def context(self, *, at=None):
        player = self.world['actors'].get(self.binding.actor_id, {}) if self.binding else {}
        return t('terminal.standalone.playing_as_simulation_v', title=self.world['configuration']['world']['title'],
                 actor=label(player) or t('terminal.standalone.choose_a_player'), version=self.snapshot['version'])

    def breadcrumbs(self):
        return ' > '.join((t('navigation.ecosystem.label') if r.kind == 'matrix' else navigation_label(r.kind)) +
                          (f' / {self.name(r.target)}' if r.target else '') +
                          (f" @ v{r.extra['at']}" if 'at' in r.extra else '') for r in self.navigation.stack)

    def name(self, target):
        return next((label(node) for node in self.graph['nodes'] if node['id'] == target), target)

    def pick(self, title, items, labeler=label):
        return self.forms.pick(title, items, labeler)

    def select_player(self):
        if self.binding and not self.hot_seat:
            self.notice = t('terminal.standalone.this_host_supplies_a_fixed')
            return
        actors = [actor for actor in self.world['actors'].values() if actor['status'] == 'active']
        actor = self.pick(t('terminal.standalone.who_will_you_play_simulation'), actors)
        self.binding = SimulationBinding(scope_id=self.collective.scope_id, actor_id=actor['id'],
                                         authority='organisation' if actor['kind'] == 'organisation' else 'personal')

    def push(self, kind, target=None, **extra):
        if 'at' in self.route.extra:
            extra.setdefault('at', self.route.extra['at'])
        self.navigation.push(kind, target, **extra)

    def build_screen(self):
        route = self.route
        if route.kind == 'matrix':
            return self.matrix_screen()
        if route.kind == 'network':
            return self.network_screen()
        if route.kind == 'inspect':
            return self.inspect()
        if route.kind == 'cell':
            provider, requester = route.extra['pair']
            matches = [item for item in self.snapshot['possibilities']
                       if (item['source_id'], item['target_id']) == (provider, requester)]
            return Screen(t('terminal.standalone.complementarity_inspect'),
                          [t('terminal.standalone.offers_requests', value=self.name(provider), value_2=self.name(requester)),
                           t('terminal.standalone.inferred_match_records', matches_count=len(matches)),
                           *[f"{edge.get('domain', t('terminal.standalone.match'))} · {', '.join(edge['source_record_ids'])}" for edge in matches]],
                          [(self.name(key), ('inspect', key)) for key in dict.fromkeys((provider, requester))],
                          t('terminal.standalone.j_invite_k_propose_w'), route.index, route.scroll)
        if route.kind == 'inbox':
            items = self.collective.inbox(binding=self.binding, at=route.extra.get('at'))
            entries = [(self.name(item['id']) + ' · ' + ', '.join(map(action_label, item['actions'])),
                        ('inspect', item['id'])) for item in items]
            return self.list_screen(t('inbox.title'), entries, [t('terminal.standalone.pending_decisions_and_obligations_for')])
        if route.kind in {'gathering', 'scenarios'}:
            objectives = [o for o in self.world['objectives'].values()
                          if route.kind == 'scenarios' or o['mode'] == 'gathering']
            entries = [(label(o) + ' · ' + o['status'], ('inspect', o['id'])) for o in objectives]
            if route.kind == 'gathering':
                entries.extend((t('terminal.standalone.attendance', value=self.name(r['target_id']), status=r['status']), ('inspect', r['id']))
                               for r in self.world['relationships'].values() if r['kind'] == 'invited')
            return self.list_screen(route.kind.upper(), entries, [t('terminal.standalone.j_invite_to_a_gathering') if route.kind == 'gathering'
                                                                 else t('terminal.standalone.inspect_an_objective_k_starts')])
        if route.kind == 'contracts':
            return self.list_screen(t('contracts.title'), [(label(a) + ' · ' + a['status'], ('inspect', a['id']))
                                                 for a in self.world['agreements'].values()], [t('terminal.standalone.k_propose_an_agreement')])
        if route.kind == 'people':
            return self.list_screen(t('terminal.standalone.ecosystem_actors'), [(label(a), ('inspect', a['id']))
                                                          for a in self.world['actors'].values()])
        if route.kind == 'history':
            events = self.collective.project('timeline', at=route.extra.get('at'))
            if route.target:
                events = [e for e in events if any(m['entity_id'] == route.target for m in e['mutations'])]
            entries = [(f"v{e['sequence']} · {e['kind']}", ('past', e['sequence'])) for e in events]
            return self.list_screen(t('terminal.standalone.history'), entries)
        return Screen(t('terminal.standalone.help_keyboard'), [
            t('terminal.standalone.m_paths_e_ecosystem_g'),
            t('terminal.standalone.enter_inspect_b_esc_back'),
            t('terminal.standalone.matrix_arrows_enter_detail_home'),
            t('terminal.standalone.network_arrows_tab_list_canvas'),
            t('terminal.standalone.network_camera_zoom_r_rotate'),
            t('terminal.standalone.j_contact_or_negotiate_k'),
            t('terminal.standalone.tab_switches_decisions_explore_and'),
            t('terminal.standalone.forms_capture_input_until_confirmed')],
            scroll=route.scroll)

    def list_screen(self, title, entries, lines=None):
        self.route.index = min(self.route.index, max(0, len(entries) - 1))
        return Screen(title, lines or [], entries, t('terminal.standalone.enter_inspect_h_history'), self.route.index, self.route.scroll)

    def matrix_screen(self):
        actors = list(self.world['actors'].values())
        if not actors:
            return Screen(t('matrix.ecosystem_complementarity_matrix'), [t('matrix.no_actors_in_this_world')])
        route = self.route
        route.row, route.column = min(route.row, len(actors) - 1), min(route.column, len(actors) - 1)
        axes = [AxisLabel(a['id'], label(a)) for a in actors]
        counts = Counter((edge['source_id'], edge['target_id']) for edge in self.snapshot['possibilities'])
        values = [[counts.get((a.id, b.id)) for b in axes] for a in axes]
        view = MatrixView(axes, axes, values, exclude_self=True)
        cell = view.cell(route.row, route.column)
        grid = render_matrix(view, route.matrix, row=route.row, column=route.column, width=self.width - 2,
                             height=self.height - 15, own_id=self.binding.actor_id if self.binding else None,
                             numeric=route.extra.get('numeric', False), plain=self.plain)
        lines = [t('terminal.standalone.offers_requests', value=self.name(cell.row_id), value_2=self.name(cell.column_id)),
                 t('matrix.inferred_match_records_no_inferred', value=cell.value or 0),
                 t('matrix.detail_width', detail=route.matrix.detail.name.title(), columns=grid.cell_width)]
        start = len(lines)
        lines.extend(grid.lines)
        return Screen(t('matrix.ecosystem_complementarity_matrix'), lines,
                      footer=t('matrix.arrows_cell_enter_inspect_detail'),
                      fixed_rows=set(range(start, len(lines))),
                      styles=[(r+start, c, n, fg, bg, bold) for r, c, n, fg, bg, bold in grid.styles],
                      highlights={r+start for r in grid.highlights})

    def network_screen(self):
        route = self.route
        visual = focus_graph(self.graph, route.target, limit=8, offset=route.extra.get('offset', 0),
                             scope=route.extra.get('scope', 'neighbourhood'), categories=route.extra.get('categories'),
                             three_d=route.extra.get('three_d', False), object_type=route.extra.get('object_type'))
        if not visual['nodes']:
            return Screen(t('network.ecosystem_network'), [t('network.no_matching_graph_nodes')])
        route.extra['offset'] = visual['offset']
        entries = [(label(n), ('inspect', n['id'])) for n in visual['nodes']]
        route.index = min(route.index, len(entries) - 1)
        selected = entries[route.index][1][1]
        mode = route.extra.get('background', 'dim')
        lines = [t('network.selected_centre', value=self.name(selected), value_2=self.name(route.target)),
                 t('network.visible_nodes_background', entries_count=len(entries), full_node_count=visual['full_node_count'], value=mode.title()),
                 t('network.experimental_3d') if visual['three_d'] else t('network.planar')]
        page = graph_pages(visual['offset'], visual['total'], 8)
        if page:
            lines.append(page)
        screen = self.list_screen(t('network.ecosystem_network'), entries, lines)
        screen.footer = t('network.enter_inspect_tab_view_s')
        if route.region != 'explore' and self.height >= 14 and self.width >= 24 and not isinstance(self.viewport, LineViewport):
            canvas, spans = draw_graph(visual, self.width - 2, self.height - 8 - len(lines), selected=selected, plain=self.plain, emphasise=True,
                                       background=mode, angle=route.extra.get('angle', 0.),
                                       yaw=route.extra.get('angle', 0.), pitch=route.extra.get('pitch', 0.),
                                       zoom=route.extra.get('zoom', 1.))
            screen.raster_start = len(lines)
            screen.styles = [(r+screen.raster_start, c, n, fg, bg, bold) for r, c, n, fg, bg, bold in spans]
            screen.lines.extend(canvas)
            screen.show_entries = False
        return screen

    def inspect(self):
        target = self.route.target
        record = next((n for n in self.graph['nodes'] if n['id'] == target),
                      self.world['relationships'].get(target))
        if record is None:
            return Screen(t('objects.inspect'), [t('terminal.standalone.object_is_outside_this_history')])
        kind = record['kind']
        lines = [f"{kind.title()} · {record['status']} · {epistemic_status(record)}"]
        details = []
        links = [(t('terminal.standalone.network'), ('network', target)), (t('history.title'), ('history', target))]
        if kind == 'agreement':
            version = record['versions'][record['current_version'] - 1]
            lines += [t('terminal.standalone.terms_v_outcome', number=version['number'], outcome_status=record['outcome_status']), version['terms']['purpose']]
            details += [f"{self.name(p)} · {t('terminal.standalone.accepted') if p in version['acceptances'] else t('terminal.standalone.acceptance_pending')}"
                        for p in record['parties']]
            details += [f"{self.name(r['actor_id'])} · {r['description']}" for r in version['terms']['responsibilities']]
            details += [t('terminal.standalone.policy', value=self.name(version['policy_id'])), t('terminal.standalone.expiry', valid_until=version['valid_until']),
                        *version['terms']['conditions']]
            details += [t('terminal.standalone.approval_by', value=self.name(p)) for p in version['authorizations']]
            links += [(self.name(p), ('inspect', p)) for p in [*record['parties'], record['objective_id'], *record['evidence_ids']]]
        elif target in self.world['relationships']:
            lines += [f"{self.name(record['source_id'])} → {self.name(record['target_id'])}", record.get('message', '')]
            links += [(self.name(record[key]), ('inspect', record[key])) for key in ('source_id', 'target_id')]
        elif kind == 'objective':
            lines += [t('terminal.standalone.verified_agreements_required', verified_agreements=record['success']['verified_agreements'])]
            links += [(self.name(key), ('inspect', key)) for key in record['support_ids']]
        else:
            details += [f"{key.replace('_', ' ').title()} · {record[key]}" for key in ('roles', 'category', 'quantity', 'unit', 'reference')
                        if key in record]
        decisions = []
        if 'at' in self.route.extra:
            details.append(t('terminal.standalone.historical_view_decisions_available_in'))
        else:
            result = self.collective.action_options(binding=self.binding)
            options = result['options'] if result['revision'] == self.snapshot['version'] else []
            for option in options:
                action = option['action']
                if target != (action.get('agreement_id') or action.get('invitation_id')):
                    continue
                if option['errors']:
                    details.append(f"{action_label(action)} · {'; '.join(e.replace('_', ' ') for e in option['errors'])}")
                else:
                    decisions.append((action_label(action), (action, result['revision'])))
        self.route.index = min(self.route.index, max(0, len(links) - 1))
        self.route.decision_index = min(self.route.decision_index, max(0, len(decisions) - 1))
        return inspector(t('objects.inspect_title', kind=label(record)), lines, links=links, decisions=decisions, details=details, route=self.route)

    def execute(self, candidate, revision=None):
        if 'at' in self.route.extra:
            self.notice = t('terminal.standalone.return_to_the_current_world')
            return
        with action_form(self.viewport):
            payload = self.forms.collect(candidate, self.world)
            kind = payload.pop('kind')
            target = next((payload[key] for key in ('agreement_id', 'invitation_id', 'resource_id', 'id', 'objective_id')
                           if key in payload), None)
            action = ActionSubmission(action_id='terminal-' + uuid4().hex, actor_id=self.binding.actor_id,
                                      scope_id=self.collective.scope_id, target_id=target,
                                      expected_revision=self.snapshot['version'] if revision is None else revision,
                                      action_type=kind, payload=payload)
            evaluation = self.collective.evaluate(action, binding=self.binding)
            if evaluation.status != 'allowed':
                self.notice = t('feedback.unavailable_prefix') + ', '.join(e.replace('_', ' ') for e in evaluation.reasons)
                return
            if not self.forms.confirm(t('terminal.standalone.submit_simulated_action') + action_label({'kind': kind})):
                raise Cancelled
            result = self.collective.submit(action, binding=self.binding)
        if result['ok']:
            self.notice = t('terminal.standalone.saved') + action_label({'kind': kind})
            if kind == 'propose':
                self.push('inspect', payload['id'])
        else:
            self.notice = t('feedback.unavailable_prefix') + ', '.join(e.replace('_', ' ') for e in result['errors'])

    def interaction(self, kind, *, recipient=None):
        actor = self.binding.actor_id
        if recipient is None:
            choices = [a for a in self.world['actors'].values() if a['id'] != actor and a['status'] == 'active']
            recipient = self.pick(t('terminal.standalone.choose_counterparty'), choices)['id']
        candidate = {'kind': kind, 'recipient_id': recipient}
        if kind == 'propose' and self.route.target in self.world['objectives']:
            candidate['objective_id'] = self.route.target
        self.execute(candidate)

    def handle(self, key, screen):
        route = self.route
        if key == 'H':
            self.push('history')
            return
        if key == 'resize':
            return
        if key == 'q':
            self.finished = True
        elif key in {'b', 'esc'}:
            if not self.navigation.back():
                self.navigation.resume(self.pick(t('terminal.standalone.choose_your_path'), list(_MODE_NAMES), navigation_label))
        elif key in MODE_KEYS:
            self.navigation.resume(MODE_KEYS[key])
        elif key == 'm':
            self.navigation.resume(self.pick(t('terminal.standalone.choose_your_path'), list(_MODE_NAMES), navigation_label))
        elif key == 'p':
            self.select_player()
        elif key in {'c', 'i', '?', 'x', 'h'}:
            self.push({'c': 'contracts', 'i': 'inbox', '?': 'help', 'x': 'people', 'h': 'history'}[key],
                      route.target if key == 'h' else None)
        elif key == 'w':
            centre = next((key for key in (route.target, self.binding.actor_id) if
                           any(n['id'] == key for n in self.graph['nodes'])), None)
            if centre:
                self.push('network', centre)
        elif route.kind == 'matrix' and key in {'up', 'down', 'left', 'right', 'enter', '+', '-', 'home', 'f', 'z'}:
            self.matrix_key(key)
        elif route.kind == 'network' and self.network_key(key, screen):
            return
        elif key in {'tab', 'backtab'} and screen.split_regions:
            regions = ('explore', 'decisions', 'details')
            route.region = regions[(regions.index(route.region) + (1 if key == 'tab' else -1)) % len(regions)]
            route.reveal = True
        elif key in {'j', 'k'} and (route.kind != 'inspect' or key == 'k'):
            if route.kind == 'gathering' and key == 'j':
                objective = self.pick(t('terminal.standalone.gathering_objective'), [o for o in self.world['objectives'].values() if o['mode'] == 'gathering'])
                actor = self.pick(t('terminal.standalone.invite_actor'), [a for a in self.world['actors'].values() if a['id'] != self.binding.actor_id])
                self.execute({'kind': 'invite', 'objective_id': objective['id'], 'recipient_id': actor['id']})
            else:
                pair = route.extra.get('pair', ())
                recipient = next((a for a in pair if a != self.binding.actor_id), None) if self.binding.actor_id in pair else None
                if pair and recipient is None:
                    self.notice = t('terminal.standalone.select_an_opportunity_involving_the')
                else:
                    self.interaction('send_contact' if key == 'j' else 'propose', recipient=recipient)
        elif route.kind == 'inspect' and key in _SHORTCUTS:
            decision = next((item for _, item in screen.decisions if item[0]['kind'] in _SHORTCUTS[key]
                             and item[0].get('response', 'accept' if key == 'y' else 'decline')
                             == ('accept' if key == 'y' else 'decline')), None)
            if decision:
                self.execute(*decision)
            else:
                self.notice = t('terminal.standalone.decision_unavailable_tab_to_details')
        else:
            self.select_entry(key, screen)

    def matrix_key(self, key):
        route = self.route
        if route.matrix.handle(key):
            if key == 'home':
                route.row = route.column = 0
            return
        actors = list(self.world['actors'])
        if not actors:
            return
        if key == 'z':
            route.extra['numeric'] = not route.extra.get('numeric', False)
        elif key == 'enter':
            self.push('cell', pair=(actors[route.row], actors[route.column]))
        elif key in {'up', 'down'}:
            route.row = max(0, min(len(actors) - 1, route.row + (1 if key == 'down' else -1)))
        else:
            route.column = max(0, min(len(actors) - 1, route.column + (1 if key == 'right' else -1)))

    def network_key(self, key, screen):
        route = self.route
        extra = route.extra
        if key == 'T':
            extra['object_type'] = OBJECT_TYPES[self.pick(t('network.object_types.title'), list(OBJECT_TYPES), lambda name: object_type_label(OBJECT_TYPES[name]))]
            route.index = extra['offset'] = 0
        elif key == 'tab':
            route.region = 'explore' if route.region == 'canvas' else 'canvas'
        elif key == 'B':
            extra['background'] = self.pick(t('network.background.title'), ['dim', 'hidden', 'full'], str.title)
        elif key == 'S':
            extra['scope'] = self.pick(t('network.scope.title'), ['neighbourhood', 'whole', 'connections'], str.title)
            route.index = extra['offset'] = 0
        elif key == 'L':
            layer = self.pick(t('terminal.standalone.network_layers'), [None, *CATEGORIES], lambda category: category_label(category) if category else t('controls.all'))
            extra['categories'] = None if layer is None else [layer]
            route.index = extra['offset'] = 0
        elif key == '3':
            extra['three_d'] = not extra.get('three_d', False)
        elif key == 'r':
            extra['angle'] = extra.get('angle', 0.) + .3
        elif key in {'{', '}'}:
            extra['pitch'] = extra.get('pitch', 0.) + (.2 if key == '}' else -.2)
        elif key in {'+', '-'}:
            extra['zoom'] = max(.4, min(2., extra.get('zoom', 1.) * (1.2 if key == '+' else 1/1.2)))
        elif key in {'[', ']', 'left', 'right'}:
            extra['offset'] = max(0, extra.get('offset', 0) + (8 if key in {']', 'right'} else -8))
            route.index = 0
        elif key == 'f' and screen.entries:
            route.target = screen.entries[route.index][1][1]
            route.index = extra['offset'] = 0
        else:
            return False
        return True

    def select_entry(self, key, screen):
        route = self.route
        if isinstance(key, str) and key.startswith('a') and key[1:].isdigit():
            index = int(key[1:]) - 1
            if 0 <= index < len(screen.decisions):
                self.execute(*screen.decisions[index][1])
            return
        if key in {'up', 'down', 'pageup', 'pagedown'}:
            delta = -1 if key in {'up', 'pageup'} else 1
            if key in {'pageup', 'pagedown'}:
                route.scroll = max(0, route.scroll + delta * max(1, self.height - 10))
            elif route.region == 'decisions' and screen.decisions:
                route.decision_index = max(0, min(len(screen.decisions) - 1, route.decision_index + delta))
                route.reveal = True
            elif route.region != 'details' and screen.entries:
                route.index = max(0, min(len(screen.entries) - 1, route.index + delta))
                route.reveal = True
            else:
                route.scroll = max(0, route.scroll + delta)
        elif key == 'enter' and route.region == 'decisions' and screen.decisions:
            self.execute(*screen.decisions[route.decision_index][1])
        elif (key == 'enter' and route.region != 'details') or (isinstance(key, str) and key.isdecimal()):
            index = route.index if key == 'enter' else int(key) - 1
            if 0 <= index < len(screen.entries):
                route.index = index
                kind, target = screen.entries[index][1]
                if kind == 'past':
                    if route.target:
                        self.push('inspect', route.target, at=target)
                    else:
                        self.push('people', at=target)
                else:
                    self.push(kind, target)
