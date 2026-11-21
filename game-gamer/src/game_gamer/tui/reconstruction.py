"""Responsive exercise screen composed from the shared terminal widgets."""

import textwrap
from dataclasses import dataclass

from .i18n import message_key, t
from .navigation import navigation_bar
from .network import RECONSTRUCTION_CATEGORIES, draw_graph, focus_graph
from .portrait import generate_portrait
from .screen import Screen
from .visual import NAVIGATION, SECONDARY, graph_pages, panel_columns, text_span

REGIONS = ('directory', 'profile', 'network')
LAYER_NAMES = {
    **RECONSTRUCTION_CATEGORIES, 'invitation': message_key('workshop.directory.layers.invitation'),
    'connection': message_key('workshop.directory.layers.connection'), 'inferred': message_key('workshop.directory.layers.inferred'),
    'declared': message_key('workshop.directory.layers.declared'), 'documented': message_key('workshop.directory.layers.documented'), 'agreement': message_key('workshop.directory.layers.agreement'),
}


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


def _profile_lines(profile, width, height, plain):
    if profile is None:
        return [t('workshop.directory.person_selected'), t('workshop.directory.no_matching_participant')]
    compact = width < 27 or height < 15
    portrait = generate_portrait(profile.id, profile, size='small' if compact else 'medium', plain=plain)
    def topics(domains, state):
        if domains:
            return ', '.join(domains) + (t('workshop.directory.partial_record') if state == 'partial' else '')
        if state == 'answered':
            return t('workshop.directory.none_declared')
        return t('common.not_recorded') if state != 'partial' else t('workshop.directory.unknown_partial_record')

    attributes = [t('workshop.directory.organisation') + (', '.join(profile.organisations) or t('common.not_recorded')),
                  t('workshop.directory.role') + (', '.join(profile.roles) or t('common.not_recorded')),
                  t('workshop.directory.motivation') + (profile.motivation or t('workshop.directory.not_yet_recorded')),
                  t('workshop.directory.offers') + topics(profile.offers, profile.offers_state),
                  t('workshop.directory.needs') + topics(profile.needs, profile.needs_state)]
    art = [*portrait.lines, portrait.description]
    lines = [profile.name, *(attributes + art if compact else art + attributes)]
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
    view = route.extra.get('graph_view', 'neighbourhood')
    view_label = t('network.view.collective') if view == 'collective' else t('network.view.neighbourhood')
    label = (t(LAYER_NAMES[layer]) if layer else graph.get('reconstruction_label', t('workshop.directory.reconstruction'))) + ' · '+view_label
    if not target:
        return [label, t('workshop.directory.select_a_participant_to_focus')], []
    incident = [edge for edge in selected_edges if target in (edge['source_id'], edge['target_id'])]
    names = {node['id']: node.get('display_name', node['label']) for node in graph['nodes']}
    details = []
    for edge in incident:
        direction = '->' if edge.get('directed') else '--' if edge.get('directed') is False else '?'
        source, other = names[edge['source_id']], names[edge['target_id']]
        observation = ' ('+edge['observation'].replace('_', ' ')+')' if 'observation' in edge else ''
        layer_key = LAYER_NAMES.get(edge['layer'])
        layer_name = t(layer_key) if layer_key else edge['kind']
        details.append(f"{source} {direction} {other} · {layer_name}{observation}")
    offset = min(route.extra.get('network_detail', 0), max(0, len(details)-1))
    route.extra['network_detail'] = offset
    lines = [label, t('workshop.directory.observations_l_layers_v_view', incident_count=len(incident))]
    if layer == 'historical_whiteboard' and not selected_edges:
        lines.append(t('workshop.directory.no_whiteboard_connections_have_been'))
    if not incident:
        lines.append(t('workshop.directory.no_observations_in_this_view'))
    if width >= 12 and height >= 8:
        edges = [{**edge, 'layer': 'reconstruction_invitation'} if edge['layer'] == 'invitation' else edge
                 for edge in selected_edges]
        endpoints = {edge[field] for edge in edges for field in ('source_id', 'target_id')}
        nodes = [node for node in graph['nodes'] if node['kind'] == 'person' or node['id'] in endpoints]
        limit = max(8, len(graph['nodes'])) if view == 'collective' and width >= 90 else 5 if width < 60 else 8
        visual = focus_graph({**graph, 'nodes': nodes, 'edges': edges}, target, offset=route.extra.get('network_page', 0),
                             limit=limit,
                             scope='whole' if view == 'collective' else 'neighbourhood')
        route.extra['network_page'] = visual['offset']
        visual['isolated_actor_ids'] = set(visual['actor_ids']) - reconstructed_ids
        page = graph_pages(visual['offset'], visual['total'], limit, arrows=False)
        if page:
            lines.append(page)
        canvas, spans = draw_graph(visual, width, height-5-bool(page), selected=target, plain=plain,
                                   background='dim' if show_unconnected else 'hidden',
                                   zoom=route.extra.get('zoom', 1.), angle=route.extra.get('angle', 0.))
        start = len(lines)
        lines += canvas
        lines += [t('workshop.directory.dotted_recall_solid_mutual'), t('workshop.directory.dashed_invite_ring_no_recall')]
        lines += details[offset:offset+2]
        return lines[:height], [(y+start, x, length, fg, bg, bold) for y, x, length, fg, bg, bold in spans]
    return (lines+details[offset:offset+max(1, height-len(lines))])[:height], []


def reconstruction_screen(exercise, route, profiles, graph, counts, *, width, height,
                          plain=False, reconstructed_ids=(), footer=None):
    """Use columns when readable and expose every panel through Tab at any width."""
    width = max(1, width-2)
    actor_ids = {p.id for p in profiles}
    if route.target not in actor_ids:
        route.target = profiles[0].id if profiles else None
    route.index = next((i for i, p in enumerate(profiles) if p.id == route.target), 0)
    profile = profiles[route.index] if profiles else None
    summary = [
        exercise.subtitle,
        t('workshop.directory.people_recalled_pairs_directed_claims', participants=counts['participants'], pairs=counts['pairs'], claims=counts['claims'], contributors=counts['contributors']),
        t('workshop.directory.corroborated_unilateral_disputed_your_claims', corroborated=counts['corroborated'], unilateral=counts['unilateral'], disputed=counts['disputed'], own=counts['own']),
        t('workshop.directory.pending_invitations_accepted_new_connections', invitations=counts['invitations'], accepted_connections=counts['accepted_connections']),
    ]
    if width < 66:
        compact = [exercise.subtitle, t('workshop.directory.recalled_pairs_claims', pairs=counts['pairs'], claims=counts['claims']),
                   t('workshop.directory.mutual_unilateral_disputed', corroborated=counts['corroborated'], unilateral=counts['unilateral'], disputed=counts['disputed']),
                   t('workshop.directory.contributors_yours_pending_invites', contributors=counts['contributors'], own=counts['own'], invitations=counts['invitations'])]
        summary = compact if route.region == 'network' and height >= 20 else compact[:2]
    if height < 13:
        summary = summary[:1]
    panel_height = max(1, height-7-len(summary))
    if route.region not in REGIONS:
        route.region = 'directory'
    markers = {name: (' >' if route.region == name else '') for name in REGIONS}
    show = REGIONS if width >= 116 else (
        ('directory', 'network' if route.region == 'network' else 'profile') if width >= 66 else (route.region,))
    if route.kind == 'reconstruction_graph':
        show = ('network',)
    gutter = 3
    panel_width = (width - gutter*(len(show)-1)) // len(show)
    panels = []
    for name in show:
        spans = []
        heading = {'directory': t('workshop.directory.who_directory'), 'profile': t('workshop.directory.why_profile'), 'network': t('workshop.directory.connections_network')}[name]+markers[name]
        if name == 'directory':
            visible = max(0, panel_height-2)
            start = max(0, min(route.extra.get('directory_start', 0), max(0, len(profiles)-visible)))
            if route.index < start:
                start = route.index
            elif visible and route.index >= start+visible:
                start = route.index-visible+1
            route.extra['directory_start'] = start
            rows = [heading, t('workshop.directory.matches_search_f_filter', profiles_count=len(profiles))]
            rows += [('> ' if p.id == route.target else '  ')+p.name for p in profiles[start:start+visible]]
        elif name == 'profile':
            lines = _profile_lines(profile, panel_width, panel_height, plain)
            offset = min(route.extra.get('profile_scroll', 0), max(0, len(lines)-panel_height+1))
            route.extra['profile_scroll'] = offset
            rows = [heading, *lines[offset:offset+panel_height-1]]
        else:
            rows, spans = _network_panel(graph, route.target, panel_width, panel_height-1, route=route,
                                          plain=plain, show_unconnected=exercise.show_unconnected,
                                          reconstructed_ids=set(reconstructed_ids))
            rows.insert(0, heading)
            spans = [(row+1, *rest) for row, *rest in spans if row+1 < panel_height]
        spans.append(text_span(0, 0, heading, NAVIGATION if name == route.region else SECONDARY, bold=True))
        panels.append((panel_width, rows[:panel_height], spans))
    body, styles = panel_columns(panels, row_offset=len(summary), gutter=gutter)
    lines = summary + body
    return Screen(exercise.title, lines, [(p.name, p.id) for p in profiles], t('workshop.directory.footer') if footer is None else footer,
                  route.index, show_entries=False, styles=styles, fixed_rows=set(range(len(lines))),
                  navigation_text=navigation_bar(contracts_key='C'),
                  refresh_interval_ms=1500)
