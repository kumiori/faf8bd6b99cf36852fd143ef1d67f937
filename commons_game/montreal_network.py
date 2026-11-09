"""Read-only Montréal explorer using the reconstruction directory and graph widgets."""

import json
import textwrap
from collections import Counter
from copy import copy
from dataclasses import replace

from game_gamer.projections.participants import ParticipantFilters, ParticipantProfile
from game_gamer.runtime.curation import canonical
from game_gamer.tui.i18n import message_key
from game_gamer.tui.network import draw_graph, focus_graph, object_type_label
from game_gamer.tui.overview import overview, select_scope
from game_gamer.tui.portrait import generate_portrait
from game_gamer.tui.reconstruction import REGIONS, selected_network_edges
from game_gamer.tui.screen import Screen
from game_gamer.tui.text import clip, display_width
from game_gamer.tui.visual import ACTION, NAVIGATION, PRIMARY, SECONDARY, panel_columns, text_span

from .curator import allowed
from .i18n import t
from .montreal_sources import LAYER
from .presentation import status
from .reconstruction import SORT_LABELS, exercise_projection
from .reconstruction_filters import filter_label

VIEWS = {'topology': message_key('network.layers.montreal_topology'), 'recollections': message_key('navigation.montreal_network.layers.recollections'),
          'connections': message_key('navigation.montreal_network.layers.connections')}
EDGE_GROUPS = {LAYER: 'topology', 'recollection': 'recollections', 'corroborated': 'recollections',
               'disputed_recollection': 'recollections', 'connection': 'connections'}
SCOPES = {'local': message_key('montreal_ui.scopes.local'),
          'community': message_key('montreal_ui.scopes.community'),
          'global': message_key('montreal_ui.scopes.global')}
HEADINGS = {'directory': message_key('workshop.directory.who_directory'),
            'profile': message_key('montreal_ui.profile'), 'network': message_key('montreal_ui.network')}
MAIN_ROUTES = {'montreal_network', 'montreal_network_graph'}
ROUTES = MAIN_ROUTES | {'montreal_connection', 'montreal_profile_source', 'montreal_source_review'}


def projection(app):
    key = 'montreal_network'
    if key not in app._projection_cache:
        world = app.world()
        dataset = world['configuration'].get(LAYER, {})
        graph = app.graph_projection()
        directory = copy(exercise_projection(app)[1])
        original = directory.profiles
        graph_nodes = {node['id']: node for node in graph['nodes']}
        provenance = {}
        if dataset:
            directory.profiles = {}
            statements = {}
            for row in dataset['statements']:
                statements.setdefault(row['person_id'], []).append(row)
            for source_id, binding in dataset['identities'].items():
                actor = canonical(world, binding['actor_id']) if binding['actor_id'] else source_id
                if actor not in graph_nodes:
                    continue
                name = dataset['names'][source_id][0]
                profile = directory.profiles.get(actor) or original.get(actor) or ParticipantProfile(actor, name, 'person')
                rows = statements.get(source_id, [])
                motivations = tuple(dict.fromkeys(row['raw']['Pourquoi suis-je ici ?'] for row in rows
                                                  if row['raw']['Pourquoi suis-je ici ?'].strip()))
                organisations = tuple(dict.fromkeys(row['raw']['Organisation'] for row in rows
                                                    if row['raw']['Organisation'].strip()))
                roles = tuple(dict.fromkeys(row['raw']['Titre / fonction'] for row in rows
                                            if row['raw']['Titre / fonction'].strip()))
                curated = world['configuration'].get('curation', {}).get('profiles', {}).get(actor, {}).get('changes', {})
                if 'profile_role' in curated:
                    roles = (curated['profile_role'],) if curated['profile_role'] else ()
                else:
                    roles = roles or profile.roles
                directory.profiles[actor] = replace(
                    profile, name=curated.get('label', name), organisations=organisations or profile.organisations,
                    roles=roles,
                    motivation=profile.motivation if 'motivation' in curated else '\n'.join(motivations) or profile.motivation)
                provenance.setdefault(actor, []).append({'source_id': source_id, 'binding': binding, 'statements': rows})
        ids = directory.profiles.keys()
        edges = [{**edge, 'display_group': EDGE_GROUPS[edge['layer']]} for edge in graph['edges']
                 if edge['layer'] in EDGE_GROUPS and edge['source_id'] in ids and edge['target_id'] in ids]
        nodes = [{**graph_nodes[key], 'display_name': profile.name}
                 for key, profile in directory.profiles.items() if key in graph_nodes]
        app._projection_cache[key] = directory, {'nodes': nodes, 'edges': edges}, provenance, dataset
    return app._projection_cache[key]


def scope_name(route):
    return route.extra.get('scope', 'local')


def scoped_graph(graph, route):
    return select_scope({**graph, 'edges': selected_network_edges(graph, route)},
                        route.target, scope_name(route), actor_type=route.extra.get('actor_type'))


def incident_edges(graph, route):
    return [edge for edge in scoped_graph(graph, route).edges
            if route.target in (edge['source_id'], edge['target_id'])]


def panel_widths(app):
    width = max(1, app.width-2)
    if app.route.kind == 'montreal_network_graph' or width < 66:
        return [('network' if app.route.kind == 'montreal_network_graph' else app.route.region, width)]
    if width < 116:
        directory = width//3
        return [('directory', directory), ('network' if app.route.region == 'network' else 'profile', width-directory-3)]
    directory, profile = width*23//100, width*30//100
    return [('directory', directory), ('profile', profile), ('network', width-directory-profile-6)]


def page_size(width):
    return 5 if width < 60 else 8


def profile_rows(app, profile, width, height, provenance):
    if profile is None:
        return [(t('workshop.directory.no_matching_participant'), SECONDARY)]
    route = app.route
    expanded = route.extra.get('profile_expanded', False)
    portrait = generate_portrait(profile.id, profile, size='small', plain=app.plain)
    art = portrait.lines[1:-1] if height >= 11 else portrait.lines[2:3]
    rows = [(line[1:-1], NAVIGATION) for line in art]

    def add(text, colour=PRIMARY, *, limit=None):
        parts = textwrap.wrap(' '.join(text.split()), width) or ['']
        if limit and len(parts) > limit:
            parts = [*parts[:limit-1], clip(parts[limit-1], max(0, width-1))+'…']
        rows.extend((part, colour) for part in parts)

    add(profile.name)
    identity = ' · '.join((*profile.roles, *profile.organisations))
    if identity:
        add(identity, SECONDARY, limit=None if expanded else 1)
    add(t('montreal_ui.motivation'), SECONDARY)
    add(profile.motivation or t('common.not_recorded'), limit=None if expanded else 3 if height >= 15 else 1)
    for label, values, state in ((t('objects.offers'), profile.offers, profile.offers_state),
                                  (t('objects.need.plural'), profile.needs, profile.needs_state)):
        if values:
            count = str(len(values)) + ('+' if state == 'partial' else '')
        else:
            count = '0' if state == 'answered' else '?'
        add(f'{label} {count}', ACTION)
        if expanded:
            for value in values:
                add('· '+value)
            if not values:
                add(t('workshop.directory.none_declared') if state == 'answered' else t('common.not_recorded'), SECONDARY)
            if state == 'partial':
                add(t('montreal_ui.partial'), SECONDARY)
    if allowed(app):
        if any(not item['binding']['actor_id'] for item in provenance.get(profile.id, [])):
            add(t('navigation.montreal_network.identity_pending_review') + profile.id, SECONDARY)
        else:
            add(t('navigation.montreal_network.roster_identity') + profile.id, SECONDARY)
    offset = min(route.extra.get('profile_scroll', 0), max(0, len(rows)-height))
    route.extra['profile_scroll'] = offset
    return rows[offset:offset+height]


def network_rows(app, scoped, width, height):
    route = app.route
    scope = scope_name(route)
    incident = [edge for edge in scoped.edges if route.target in (edge['source_id'], edge['target_id'])]
    offset = min(route.extra.get('network_detail', 0), max(0, len(incident)-1))
    route.extra['network_detail'] = offset
    if not scoped.nodes:
        return [t('montreal_ui.empty_scope')], []
    rows, styles = [], []
    if scope != 'local':
        rows.append(t('montreal_ui.shape', components=len(scoped.components), isolates=len(scoped.isolates)))
    else:
        rows.append(t('montreal_ui.local_links', count=len(incident)))
    graph_height = height-len(rows)-min(2, max(1, len(incident)))
    if len(scoped.nodes) <= 4:
        graph_height = min(graph_height, 9)
    if width >= 12 and graph_height >= 3:
        zoom, angle = route.extra.get('zoom', 1.), route.extra.get('angle', 0.)
        if scope == 'local':
            visual = focus_graph({'nodes': list(scoped.nodes.values()), 'edges': scoped.edges}, route.target,
                                 limit=page_size(width), offset=route.extra.get('network_page', 0))
            route.extra['network_page'] = visual['offset']
            if visual['total'] > page_size(width) and graph_height >= 4:
                rows.append(t('montreal_ui.local_page', first=visual['offset']+1,
                              last=min(visual['offset']+page_size(width), visual['total']), total=visual['total']))
                graph_height -= 1
            canvas, raster = draw_graph(visual, width, graph_height, selected=route.target,
                                        plain=app.plain, zoom=zoom, angle=angle, background='hidden')
        else:
            visual = overview(scoped, width, graph_height, selected=route.target)
            canvas, raster = draw_graph(visual, width, graph_height, selected=visual['centre'], plain=app.plain,
                                        zoom=min(1., zoom), angle=angle, background='hidden', show_labels=False)
        styles.extend((row+len(rows), x, length, fg, bg, bold) for row, x, length, fg, bg, bold in raster)
        rows.extend(canvas)
    for index, edge in enumerate(incident[offset:offset+min(2, max(0, height-len(rows)))], offset):
        outgoing = route.target == edge['source_id']
        counterpart = edge['target_id'] if outgoing else edge['source_id']
        direction = ('>' if outgoing else '<') if edge.get('directed') else '=' if edge.get('directed') is False else '?'
        if not app.plain:
            direction = {'>': '→', '<': '←', '=': '↔', '?': '?'}[direction]
        selected = route.region == 'network' and index == offset
        line = ('> ' if selected else '  ') + direction + ' ' + scoped.nodes[counterpart]['display_name']
        if selected:
            styles.append(text_span(len(rows), 0, line, NAVIGATION, bold=True))
        rows.append(line)
    if not incident and len(rows) < height:
        rows.append(t('navigation.montreal_network.no_connections_for_this_participant'))
    if rows:
        styles.insert(0, text_span(0, 0, rows[0], SECONDARY))
    return rows, styles


def explorer_screen(app, directory, graph, provenance, dataset):
    route = app.route
    route.extra.setdefault('graph_groups', ('topology',))
    groups = route.extra['graph_groups']
    filters = route.extra.get('filter', ParticipantFilters())
    sort = route.extra.get('sort', 'name')
    profiles = directory.browse(filters, sort=sort if sort != 'connections' else 'name')
    if sort == 'connections':
        counts = Counter(edge[field] for edge in selected_network_edges(graph, route)
                         for field in ('source_id', 'target_id'))
        profiles.sort(key=lambda profile: -counts[profile.id])
    if route.target not in {profile.id for profile in profiles}:
        route.target = profiles[0].id if profiles else None
        route.extra.update(profile_scroll=0, profile_expanded=False, network_page=0, network_detail=0)
    route.index = next((index for index, profile in enumerate(profiles) if profile.id == route.target), 0)
    profile = profiles[route.index] if profiles else None
    if route.region not in REGIONS:
        route.region = 'directory'
    scoped = scoped_graph(graph, route)
    layer = t(VIEWS[groups[0]]) if len(groups) == 1 else t('terminal.all_layers')
    scope_labels = [t(label) for label in SCOPES.values()]
    active = tuple(SCOPES).index(scope_name(route))
    scope_labels[active] = '['+scope_labels[active]+']'
    scopes = '  '.join(scope_labels) + '  ·  S'
    scope_column = display_width('  '.join(scope_labels[:active])) + (2 if active else 0)
    actor_type = route.extra.get('actor_type')
    if actor_type:
        scopes += '  ·  '+object_type_label(actor_type)
    stats = t('montreal_ui.stats_compact' if app.width < 70 else 'navigation.montreal_network.connections_participants',
              views=layer, edges_count=len(scoped.edges), profiles_count=len(scoped.nodes))
    summary = [scopes, stats]
    if not dataset and groups == ('topology',) and app.height >= 22:
        summary.append(t('navigation.montreal_network.no_montreal_source_topology_has'))
    if app.height < 13:
        summary = summary[:1]
    height = max(0, app.height-7-len(summary))
    panels = []
    for name, width in panel_widths(app):
        focused = route.region == name
        heading = ('> ' if focused else '  ')+t(HEADINGS[name])
        available = max(0, height-1)
        if name == 'directory':
            visible = max(0, available-1)
            start = min(route.extra.get('directory_start', 0), max(0, len(profiles)-visible))
            start = max(0, min(start, route.index))
            if visible and route.index >= start+visible:
                start = route.index-visible+1
            route.extra['directory_start'] = start
            meta = t('montreal_ui.directory_stats', count=len(profiles), sort=t(SORT_LABELS[sort]))
            if filters.query or filters.facets:
                meta += ' · '+t('montreal_ui.filtered')
            content = [(meta, SECONDARY)]
            content.extend((('> ' if p.id == route.target else '  ')+p.name,
                            NAVIGATION if p.id == route.target else PRIMARY)
                           for p in profiles[start:start+visible])
            if not profiles:
                content.append((t('workshop.directory.no_matching_participant'), SECONDARY))
        elif name == 'profile':
            content = profile_rows(app, profile, width, available, provenance)
        else:
            lines, styles = network_rows(app, scoped, width, available)
            panels.append((width, [heading, *lines][:height],
                           [text_span(0, 0, heading, NAVIGATION if focused else SECONDARY, bold=True),
                            *((row+1, *rest) for row, *rest in styles if row+1 < height)]))
            continue
        content = [(heading, NAVIGATION if focused else SECONDARY), *content[:available]][:height]
        panels.append((width, [line for line, _ in content],
                       [text_span(row, 0, line, colour, bold=row == 0 or colour in {NAVIGATION, ACTION})
                        for row, (line, colour) in enumerate(content)]))
    body, styles = panel_columns(panels, row_offset=len(summary))
    styles += [text_span(row, 0, line, SECONDARY) for row, line in enumerate(summary)]
    styles.append(text_span(0, scope_column, scope_labels[active], NAVIGATION, bold=True))
    if route.region == 'network':
        has_links = any(route.target in (edge['source_id'], edge['target_id']) for edge in scoped.edges)
        if not scoped.nodes:
            footer = t('montreal_ui.keys.network_no_actors')
        elif app.width < 70:
            footer = t('montreal_ui.keys.network_compact')
        else:
            footer = t('montreal_ui.keys.network' if has_links else 'montreal_ui.keys.network_empty')
        if route.kind == 'montreal_network':
            footer = t('montreal_ui.keys.panels')+'  '+footer
    elif route.region == 'profile':
        footer = t('montreal_ui.keys.profile_less' if route.extra.get('profile_expanded') else 'montreal_ui.keys.profile')
    else:
        footer = t('montreal_ui.keys.directory_compact' if app.width < 70 else 'montreal_ui.keys.directory')
    lines = summary+body
    return Screen(t('navigation.montreal_network.title'), lines, [(p.name, p.id) for p in profiles], footer,
                  route.index, show_entries=False, styles=styles, fixed_rows=set(range(len(lines))),
                  refresh_interval_ms=1500)


def build(app):
    route = app.route
    directory, graph, provenance, dataset = projection(app)
    if route.kind == 'montreal_connection':
        edge = route.extra['edge']
        names = {key: profile.name for key, profile in directory.profiles.items()}
        direction = ' → ' if edge.get('directed') else ' ↔ ' if edge.get('directed') is False else ' ? '
        source = names.get(edge['source_id'], edge.get('source_name', edge['source_id']))
        target = names.get(edge['target_id'], edge.get('target_name', edge['target_id']))
        summary = [source+direction+target,
                   t(VIEWS[edge['display_group']]), t('navigation.montreal_network.status')+status(edge['status'])]
        if 'remarks' in edge:
            summary.append(t('navigation.montreal_network.remarks')+(edge['remarks'] or t('navigation.montreal_network.none_supplied')))
        if route.extra.get('show_source') or allowed(app):
            summary += json.dumps(edge, ensure_ascii=False, indent=2).splitlines()
        other = edge['target_id'] if route.target == edge['source_id'] else edge['source_id']
        entries = [(t('navigation.montreal_network.focus')+names[other], other)] if other in names else []
        return Screen(t('navigation.montreal_network.headings.connection', title=t('navigation.montreal_network.title')), summary, entries,
                      t('montreal_ui.keys.connection'), scroll=route.scroll)
    if route.kind == 'montreal_profile_source':
        lines = json.dumps(provenance.get(route.target, []), ensure_ascii=False, indent=2).splitlines()
        return Screen(t('navigation.montreal_network.headings.profile_sources', title=t('navigation.montreal_network.title')), lines, footer=t('navigation.montreal_network.b_network_pgup_pgdn_scroll'), scroll=route.scroll)
    if route.kind == 'montreal_source_review':
        if not allowed(app):
            return Screen(t('navigation.montreal_network.headings.source_review', title=t('navigation.montreal_network.title')), [t('curation.permission_required')])
        unresolved = {key: {'names': dataset['names'][key], **binding}
                      for key, binding in dataset.get('identities', {}).items() if not binding['actor_id']}
        lines = [t('navigation.montreal_network.identities_awaiting_review', unresolved_count=len(unresolved)), t('navigation.montreal_network.use_reviewed_stable_actor_ids')]
        lines += json.dumps(unresolved, ensure_ascii=False, indent=2).splitlines()
        return Screen(t('navigation.montreal_network.headings.source_review', title=t('navigation.montreal_network.title')), lines, footer=t('navigation.montreal_network.b_network_pgup_pgdn_scroll'), scroll=route.scroll)
    return explorer_screen(app, directory, graph, provenance, dataset)


def focus_participant(app, target, directory):
    route = app.route
    route.target = target
    if target not in {p.id for p in directory.browse(route.extra.get('filter', ParticipantFilters()))}:
        route.extra['filter'] = ParticipantFilters()
        app.notice = t('navigation.montreal_network.cleared_filters_to_focus_the')
    route.extra.update(profile_scroll=0, profile_expanded=False, network_detail=0, network_page=0)


def handle(app, key, screen):
    route = app.route
    if route.kind == 'montreal_connection' and key == 'd':
        route.extra['show_source'] = True
        route.scroll = 0
        return True
    if route.kind == 'montreal_connection' and key == 'enter' and screen.entries:
        app.back()
        focus_participant(app, screen.entries[0][1], projection(app)[0])
        return True
    if route.kind not in MAIN_ROUTES:
        return False
    directory, graph, _, _ = projection(app)
    if key in {'tab', 'backtab'} and route.kind == 'montreal_network':
        route.region = REGIONS[(REGIONS.index(route.region)+(1 if key == 'tab' else -1)) % len(REGIONS)]
    elif key in {'up', 'down', 'pageup', 'pagedown'}:
        step = (-1 if key in {'up', 'pageup'} else 1) * (1 if key in {'up', 'down'} else max(1, app.height-14))
        if route.region == 'directory' and screen.entries:
            index = min(max(0, route.index+step), len(screen.entries)-1)
            route.target = screen.entries[index][1]
            route.extra.update(profile_scroll=0, profile_expanded=False, network_page=0, network_detail=0)
        elif route.region in {'profile', 'network'}:
            field = 'profile_scroll' if route.region == 'profile' else 'network_detail'
            route.extra[field] = max(0, route.extra.get(field, 0)+step)
    elif key == 'enter':
        if route.region == 'network':
            incident = incident_edges(graph, route)
            if incident:
                index = min(route.extra.get('network_detail', 0), len(incident)-1)
                app.push('montreal_connection', route.target, edge=incident[index])
            else:
                app.notice = t('navigation.montreal_network.no_connections_for_this_participant')
        else:
            route.region = 'profile' if route.region == 'directory' else 'directory'
    elif key == 'L':
        group = app.choose(t('navigation.montreal_network.headings.layers', title=t('navigation.montreal_network.title')),
                           [*VIEWS, None], lambda item: t(VIEWS[item]) if item else t('terminal.all_layers'))
        route.extra.update(graph_groups=(group,) if group else tuple(VIEWS), network_detail=0, network_page=0)
    elif key == 'T':
        counts = Counter(node['kind'] for node in graph['nodes'])
        kinds = sorted({'person', 'organisation', *counts})
        actor_type = app.choose(t('montreal_ui.actor_types'), [None, *kinds],
                                lambda kind: f'{object_type_label(kind)} ({counts[kind]})' if kind else object_type_label(None))
        route.extra.update(actor_type=actor_type, network_detail=0, network_page=0)
        route.region = 'network'
    elif key == 'G' and route.kind == 'montreal_network':
        app.push('montreal_network_graph', route.target, **{**route.extra, 'scope': 'global', 'network_page': 0})
        app.route.region = 'network'
    elif key in {'S', 'v'}:
        scopes = tuple(SCOPES)
        scope = (scopes[(scopes.index(scope_name(route))+1) % len(scopes)] if key == 'S'
                 else 'global' if scope_name(route) == 'local' else 'local')
        route.extra.update(scope=scope, network_detail=0, network_page=0)
        if key == 'S':
            route.region = 'network'
    elif key == 'F':
        scoped = scoped_graph(graph, route)
        if scoped.nodes:
            target = app.choose(t('montreal_ui.focus_title'),
                                [p.id for p in directory.browse() if p.id in scoped.nodes],
                                lambda key: scoped.nodes[key]['display_name'])
            focus_participant(app, target, directory)
            route.extra['scope'] = 'local'
            route.region = 'network'
    elif key == 'D' and route.kind == 'montreal_network' and route.target:
        route.extra.update(profile_expanded=not route.extra.get('profile_expanded', False), profile_scroll=0)
        route.region = 'profile'
    elif key == 'o':
        sort = app.choose(t('montreal_ui.sort_title'), ['name', 'organisation', 'connections'],
                          lambda item: t(SORT_LABELS[item]))
        route.extra.update(sort=sort, directory_start=0)
        if route.kind == 'montreal_network':
            route.region = 'directory'
    elif key == 'n':
        route.region = 'network'
    elif key in {'[', ']'}:
        width = dict(panel_widths(app)).get('network', app.width-2)
        step = page_size(width) * (1 if key == ']' else -1)
        route.extra['network_page'] = max(0, route.extra.get('network_page', 0)+step)
    elif key in {'+', '-'}:
        route.extra['zoom'] = max(.4, min(2., route.extra.get('zoom', 1.)*(1.2 if key == '+' else 1/1.2)))
    elif key == 'r':
        route.extra['angle'] = route.extra.get('angle', 0.)+.3
    elif key == '/':
        query = app.read(t('navigation.montreal_network.search_participant_names_blank_clears'))
        route.extra['filter'] = replace(route.extra.get('filter', ParticipantFilters()), query=query)
    elif key == 'f':
        field = app.choose(t('navigation.montreal_network.headings.filter', title=t('navigation.montreal_network.title')), ['organisations', 'roles', 'offers', 'needs', 'clear'],
                           lambda item: t('navigation.montreal_network.clear_filters') if item == 'clear' else filter_label(item))
        filters = route.extra.get('filter', ParticipantFilters())
        facets = dict(filters.facets)
        if field == 'clear':
            facets.clear()
        else:
            choices = dict(directory.facet_values(field, filters))
            value = app.choose(t('navigation.montreal_network.headings.facet', title=t('navigation.montreal_network.title'), field=filter_label(field).upper()), [None, *choices],
                               lambda item: t('navigation.montreal_network.any') if item is None else f'{filter_label(item)} ({choices[item]})')
            if value is None:
                facets.pop(field, None)
            else:
                facets[field] = (value,)
        route.extra['filter'] = replace(filters, facets=tuple(facets.items()))
    elif key == 'd' and route.target:
        app.push('montreal_profile_source', route.target)
    elif key == 'U' and allowed(app):
        app.push('montreal_source_review')
    else:
        return False
    return True
