"""Responsive exercise screen composed from the shared terminal widgets."""
from dataclasses import dataclass
from itertools import zip_longest
import textwrap

from .network import RECONSTRUCTION_CATEGORIES, draw_graph, focus_graph
from .portrait import generate_portrait
from .screen import Screen
from .text import pad

REGIONS = ('directory', 'profile', 'network')
LAYER_NAMES = {
    **RECONSTRUCTION_CATEGORIES, 'invitation': 'Pending new invitation',
    'connection': 'Accepted new connection', 'inferred': 'Inferred complementarity',
    'declared': 'Declared relationship', 'documented': 'Documented relationship', 'agreement': 'Contract party',
}
FOOTER = 'Up/Down Select  Enter Inspect  c Connect  n Network  / Search  f Filter  o Sort  v View  G Graph  d Provenance  Tab Regions'


@dataclass(frozen=True)
class NetworkReconstructionExercise:
    id: str
    context_id: str
    title: str
    subtitle: str
    introduction: tuple[str, ...]
    historical_date: str | None = None
    opening_seconds: float = 2.5
    show_unconnected: bool = True


def _profile_lines(profile, width, height, plain, *, attributes_first=False):
    if profile is None:
        return ['PERSON SELECTED', 'No matching participant.']
    compact = width < 27 or height < 15
    portrait = generate_portrait(profile.id, profile, size='small' if compact else 'medium', plain=plain)
    def topics(domains, state):
        if domains:
            return ', '.join(domains) + (' (partial record)' if state == 'partial' else '')
        if state == 'answered':
            return 'None declared'
        return 'Not recorded' if state != 'partial' else 'Unknown (partial record)'

    attributes = ['Organisation: ' + (', '.join(profile.organisations) or 'Not recorded'),
                  'Role: ' + (', '.join(profile.roles) or 'Not recorded'),
                  'Motivation: ' + (profile.motivation or 'Not yet recorded'),
                  'Offers: ' + topics(profile.offers, profile.offers_state),
                  'Needs: ' + topics(profile.needs, profile.needs_state)]
    art = [*portrait.lines, portrait.description]
    lines = [profile.name, *(attributes + art if compact or attributes_first else art + attributes)]
    return [part for line in lines for paragraph in line.splitlines()
            for part in (textwrap.wrap(paragraph, width) or [''])]


def selected_network_edges(graph, route):
    layer = route.extra.get('layer')
    groups = route.extra.get('graph_groups', ('reconstruction', 'existing', 'invitations'))
    return [edge for edge in graph['edges'] if edge.get('display_group', 'reconstruction') in groups
            and (layer is None or edge['layer'] == layer)]


def _network_panel(graph, target, width, height, *, route, plain, show_unconnected, reconstructed_ids):
    layer = route.extra.get('layer')
    selected_edges = selected_network_edges(graph, route)
    explorer = route.extra.get('network_explorer')
    view = route.extra.get('graph_view', 'neighbourhood')
    label = (LAYER_NAMES[layer] if layer else graph.get('reconstruction_label', 'Reconstruction')) + ' · '+view.title()
    if not target:
        return [label, 'Select a participant to focus the graph.'], []
    incident = [edge for edge in selected_edges if target in (edge['source_id'], edge['target_id'])]
    names = {node['id']: node.get('display_name', node['label']) for node in graph['nodes']}
    details = []
    for index, edge in enumerate(incident):
        direction = '->' if edge.get('directed') else '--' if edge.get('directed') is False else '?'
        if explorer:
            outgoing = target == edge['source_id']
            counterpart = edge['target_id'] if outgoing else edge['source_id']
            if edge.get('directed'):
                direction = ('->' if outgoing else '<-') if plain else ('→' if outgoing else '←')
            marker = '> ' if route.region == 'network' and index == min(
                route.extra.get('network_detail', 0), len(incident)-1) else '  '
            details.append(f"{marker}{direction} {names[counterpart]}")
        else:
            source, other = names[edge['source_id']], names[edge['target_id']]
            observation = ' ('+edge['observation'].replace('_', ' ')+')' if 'observation' in edge else ''
            details.append(f"{source} {direction} {other} · {LAYER_NAMES.get(edge['layer'], edge['kind'])}{observation}")
    offset = min(route.extra.get('network_detail', 0), max(0, len(details)-1))
    route.extra['network_detail'] = offset
    lines = [label, f'{len(incident)} observations · L Layers · v View · [ ] Page']
    if layer == 'historical_whiteboard' and not selected_edges:
        lines.append('No whiteboard connections have been imported.')
    if not incident:
        lines.append('No observations in this view.')
    if width >= 12 and height >= 8:
        edges = [{**edge, 'layer': 'reconstruction_invitation'} if edge['layer'] == 'invitation' else edge
                 for edge in selected_edges]
        endpoints = {edge[field] for edge in edges for field in ('source_id', 'target_id')}
        nodes = [node for node in graph['nodes'] if node['kind'] == 'person' or node['id'] in endpoints]
        visual = focus_graph({**graph, 'nodes': nodes, 'edges': edges}, target, offset=route.extra.get('network_page', 0),
                             limit=max(8, len(graph['nodes'])) if view == 'collective' and width >= 90 else 5 if width < 60 else 8,
                             scope='whole' if view == 'collective' else 'neighbourhood')
        route.extra['network_page'] = visual['offset']
        visual['isolated_actor_ids'] = set(visual['actor_ids']) - reconstructed_ids
        canvas, spans = draw_graph(visual, width, height-5, selected=target, plain=plain,
                                   background='dim' if show_unconnected else 'hidden',
                                   zoom=route.extra.get('zoom', 1.), angle=route.extra.get('angle', 0.))
        start = len(lines)
        lines += canvas
        lines += (['Enter Connection · +/- Zoom · r Rotate', '[ ] Page · v Local/Collective'] if explorer else
                  ['Dotted: recall · solid: mutual', 'Dashed: invite · ring: no recall'])
        lines += details[offset:offset+2]
        return lines[:height], [(y+start, x, length, fg, bg, bold) for y, x, length, fg, bg, bold in spans]
    return (lines+details[offset:offset+max(1, height-len(lines))])[:height], []


def reconstruction_screen(exercise, route, profiles, graph, counts, *, width, height,
                          plain=False, reconstructed_ids=(), summary_lines=None, footer=FOOTER,
                          profile_context=None):
    """Use columns when readable and expose every panel through Tab at any width."""
    width = max(1, width-2)
    actor_ids = {p.id for p in profiles}
    if route.target not in actor_ids:
        route.target = profiles[0].id if profiles else None
    route.index = next((i for i, p in enumerate(profiles) if p.id == route.target), 0)
    profile = profiles[route.index] if profiles else None
    summary = summary_lines if summary_lines is not None else [
        exercise.subtitle,
        f"{counts['participants']} people · {counts['pairs']} recalled pairs · {counts['claims']} directed claims · {counts['contributors']} contributors",
        f"{counts['corroborated']} corroborated · {counts['unilateral']} unilateral · {counts['disputed']} disputed · Your claims {counts['own']}",
        f"{counts['invitations']} pending invitations · {counts['accepted_connections']} accepted new connections",
    ]
    if summary_lines is None and width < 66:
        compact = [exercise.subtitle, f"{counts['pairs']} recalled pairs · {counts['claims']} claims",
                   f"{counts['corroborated']} mutual · {counts['unilateral']} unilateral · {counts['disputed']} disputed",
                   f"{counts['contributors']} contributors · {counts['own']} yours · {counts['invitations']} pending invites"]
        summary = compact if route.region == 'network' and height >= 20 else compact[:2]
    if height < 13:
        summary = summary[:1]
    panel_height = max(1, height-7-len(summary))
    if route.region not in REGIONS:
        route.region = 'directory'
    markers = {name: (' >' if route.region == name else '') for name in REGIONS}
    show = REGIONS if width >= 116 else (
        ('directory', 'network' if route.region == 'network' else 'profile') if width >= 66 else (route.region,))
    if route.kind in {'reconstruction_graph', 'montreal_network_graph'}:
        show = ('network',)
    gutter = 3
    panel_width = (width - gutter*(len(show)-1)) // len(show)
    columns, styles = [], []
    for column, name in enumerate(show):
        heading = {'directory': 'WHO / DIRECTORY', 'profile': 'WHY / PROFILE', 'network': 'CONNECTIONS / NETWORK'}[name]+markers[name]
        if name == 'directory':
            visible = max(0, panel_height-2)
            start = max(0, min(route.extra.get('directory_start', 0), max(0, len(profiles)-visible)))
            if route.index < start:
                start = route.index
            elif visible and route.index >= start+visible:
                start = route.index-visible+1
            route.extra['directory_start'] = start
            rows = [heading, f'{len(profiles)} matches · / Search · f Filter']
            rows += [('> ' if p.id == route.target else '  ')+p.name for p in profiles[start:start+visible]]
        elif name == 'profile':
            lines = _profile_lines(profile, panel_width, panel_height, plain,
                                   attributes_first=bool(route.extra.get('network_explorer')))
            if profile and profile_context and profile.id in profile_context:
                lines[1:1] = textwrap.wrap(profile_context[profile.id], panel_width)
            offset = min(route.extra.get('profile_scroll', 0), max(0, len(lines)-panel_height+1))
            route.extra['profile_scroll'] = offset
            rows = [heading, *lines[offset:offset+panel_height-1]]
        else:
            rows, spans = _network_panel(graph, route.target, panel_width, panel_height-1, route=route,
                                          plain=plain, show_unconnected=exercise.show_unconnected,
                                          reconstructed_ids=set(reconstructed_ids))
            rows.insert(0, heading)
            styles.extend((y+len(summary)+1, x+column*(panel_width+gutter), length, fg, bg, bold)
                          for y, x, length, fg, bg, bold in spans)
        columns.append(rows[:panel_height])
    lines = summary + [(' '*gutter).join(pad(value, panel_width) for value in row)
                       for row in zip_longest(*columns, fillvalue='')]
    return Screen(exercise.title, lines, [(p.name, p.id) for p in profiles], footer,
                  route.index, show_entries=False, styles=styles, fixed_rows=set(range(len(lines))),
                  navigation_text='m Paths | H History | e Ecosystem | g Gathering | s Scenarios | C Contracts | i Inbox | p Player',
                  refresh_interval_ms=1500)
