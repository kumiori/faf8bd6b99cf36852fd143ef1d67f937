"""Read-only Montréal explorer using the reconstruction directory and graph widgets."""

from copy import copy
from dataclasses import replace
import json

from game_gamer.projections.participants import ParticipantFilters, ParticipantProfile
from game_gamer.runtime.curation import canonical
from game_gamer.tui.reconstruction import reconstruction_screen, selected_network_edges
from game_gamer.tui.screen import Screen

from .curator import allowed
from .montreal_sources import LAYER
from .reconstruction import EXERCISE, exercise_projection
from .reconstruction_filters import LABELS

EXPLORER = replace(EXERCISE, title='MONTRÉAL NETWORK', subtitle='Explore the connections we created together.')
VIEWS = {'topology': 'Montréal source topology', 'recollections': 'Player recollections',
         'connections': 'Newly established connections'}
EDGE_GROUPS = {LAYER: 'topology', 'recollection': 'recollections', 'corroborated': 'recollections',
               'disputed_recollection': 'recollections', 'connection': 'connections'}
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


def incident_edges(graph, route):
    return [edge for edge in selected_network_edges(graph, route)
            if route.target in (edge['source_id'], edge['target_id'])]


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
                   VIEWS[edge['display_group']], 'Status · '+edge['status']]
        if 'remarks' in edge:
            summary.append('Remarks · '+(edge['remarks'] or 'None supplied'))
        summary += json.dumps(edge, ensure_ascii=False, indent=2).splitlines()
        other = edge['target_id'] if route.target == edge['source_id'] else edge['source_id']
        entries = [('Focus '+names[other], other)] if other in names else []
        return Screen('MONTRÉAL NETWORK / CONNECTION', summary, entries,
                      'Enter Focus counterpart · b Network · PgUp/PgDn Scroll', scroll=route.scroll)
    if route.kind == 'montreal_profile_source':
        lines = json.dumps(provenance.get(route.target, []), ensure_ascii=False, indent=2).splitlines()
        return Screen('MONTRÉAL NETWORK / PROFILE SOURCES', lines, footer='b Network · PgUp/PgDn Scroll', scroll=route.scroll)
    if route.kind == 'montreal_source_review':
        if not allowed(app):
            return Screen('MONTRÉAL NETWORK / SOURCE REVIEW', ['Curator permission required.'])
        unresolved = {key: {'names': dataset['names'][key], **binding}
                      for key, binding in dataset.get('identities', {}).items() if not binding['actor_id']}
        lines = [f'{len(unresolved)} identities awaiting review', 'Use reviewed stable actor IDs with import-montreal-network --identities.']
        lines += json.dumps(unresolved, ensure_ascii=False, indent=2).splitlines()
        return Screen('MONTRÉAL NETWORK / SOURCE REVIEW', lines, footer='b Network · PgUp/PgDn Scroll', scroll=route.scroll)
    route.extra.setdefault('network_explorer', True)
    route.extra.setdefault('graph_groups', ('topology',))
    group = route.extra['graph_groups'][0]
    graph = {**graph, 'reconstruction_label': VIEWS[group]}
    profiles = directory.browse(route.extra.get('filter', ParticipantFilters()))
    edges = selected_network_edges(graph, route)
    summary = [EXPLORER.subtitle, f'{VIEWS[group]} · {len(edges)} connections · {len(directory.profiles)} participants']
    if not dataset:
        summary.append('No Montréal source topology has been imported.')
    context = {key: ('Identity pending review · '+key if key.startswith('montreal-2026:person:') else 'Roster identity · '+key)
               for key in directory.profiles}
    footer = '↑↓ Select · Enter Inspect · / Search · f Filter · L Layer · G Graph · d Source · Tab Regions · b Back'
    if allowed(app):
        footer += ' · U Source review'
    if route.kind == 'montreal_network_graph':
        footer = '↑↓ Connections · Enter Inspect · L Layer · +/- Zoom · r Rotate · v View · [ ] Page · b Back'
    return reconstruction_screen(EXPLORER, route, profiles, graph, None, width=app.width, height=app.height,
                                 plain=app.plain, summary_lines=summary, footer=footer, profile_context=context,
                                 reconstructed_ids={edge[field] for edge in edges for field in ('source_id', 'target_id')})


def handle(app, key, screen):
    route = app.route
    if route.kind == 'montreal_connection' and key == 'enter' and screen.entries:
        target = screen.entries[0][1]
        app.back()
        parent = app.route
        parent.target = target
        directory = projection(app)[0]
        if target not in {profile.id for profile in directory.browse(parent.extra.get('filter', ParticipantFilters()))}:
            parent.extra['filter'] = ParticipantFilters()
            app.notice = 'Cleared filters to focus the selected counterpart.'
        parent.extra.update(profile_scroll=0, network_detail=0, network_page=0)
        return True
    if route.kind not in MAIN_ROUTES:
        return False
    directory, graph, _, _ = projection(app)
    if key in {'tab', 'backtab'} and route.kind == 'montreal_network':
        regions = ('directory', 'profile', 'network')
        route.region = regions[(regions.index(route.region)+(1 if key == 'tab' else -1)) % len(regions)]
    elif key in {'up', 'down', 'pageup', 'pagedown'}:
        step = (-1 if key in {'up', 'pageup'} else 1) * (1 if key in {'up', 'down'} else max(1, app.height-14))
        if route.region == 'directory' and screen.entries:
            index = min(max(0, route.index+step), len(screen.entries)-1)
            route.target = screen.entries[index][1]
            route.extra.update(profile_scroll=0, network_page=0, network_detail=0)
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
                app.notice = 'No connections for this participant in the selected layer.'
        else:
            route.region = 'profile' if route.region == 'directory' else 'directory'
    elif key == 'L':
        group = app.choose('MONTRÉAL NETWORK / LAYERS', list(VIEWS), VIEWS.__getitem__)
        route.extra.update(graph_groups=(group,), network_detail=0, network_page=0)
    elif key == 'G' and route.kind == 'montreal_network':
        app.push('montreal_network_graph', route.target, **{**route.extra, 'graph_view': 'collective', 'network_page': 0})
        app.route.region = 'network'
    elif key == 'v':
        view = 'collective' if route.extra.get('graph_view', 'neighbourhood') == 'neighbourhood' else 'neighbourhood'
        route.extra.update(graph_view=view, network_page=0)
    elif key == 'n':
        route.region = 'network'
    elif key in {'[', ']'}:
        panel_width = (app.width-8)//3 if app.width >= 118 else (app.width-5)//2 if app.width >= 68 else app.width-2
        if route.kind == 'montreal_network_graph':
            panel_width = app.width-2
        page_size = 5 if panel_width < 60 else 8
        route.extra['network_page'] = max(0, route.extra.get('network_page', 0)+(page_size if key == ']' else -page_size))
    elif key in {'+', '-'}:
        route.extra['zoom'] = max(.4, min(2., route.extra.get('zoom', 1.)*(1.2 if key == '+' else 1/1.2)))
    elif key == 'r':
        route.extra['angle'] = route.extra.get('angle', 0.)+.3
    elif key == '/':
        query = app.read('Search participant names (blank clears)')
        route.extra['filter'] = replace(route.extra.get('filter', ParticipantFilters()), query=query)
    elif key == 'f':
        field = app.choose('MONTRÉAL NETWORK / FILTER', ['organisations', 'roles', 'offers', 'needs', 'clear'],
                           lambda item: LABELS.get(item, 'Clear filters'))
        filters = route.extra.get('filter', ParticipantFilters())
        facets = dict(filters.facets)
        if field == 'clear':
            facets.clear()
        else:
            choices = dict(directory.facet_values(field, filters))
            value = app.choose('MONTRÉAL NETWORK / '+LABELS[field].upper(), [None, *choices],
                               lambda item: 'Any' if item is None else f'{LABELS.get(item, item)} ({choices[item]})')
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
