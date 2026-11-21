"""Prepare and render a focused view of a read-only collective graph."""

import math
import unicodedata
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256

from .i18n import message_key, t
from .objects import OBJECTS
from .renderers.hack_terminal import project, raster
from .text import display_width, folded
from .text import label as node_label
from .visual import NAVIGATION, SECONDARY

OBJECT_TYPES = {
    'All types': None, 'People': 'person', 'Organisations': 'organisation',
    'Resources': 'resource', 'Relationships': 'relationships', 'Agreements': 'agreement',
    'Capacities': 'capacity', 'Needs': 'need', 'Evidence': 'evidence',
    'Objectives': 'objective', 'Policies': 'policy', 'Invitations': 'invitation',
}

OBJECT_TYPE_MESSAGES = {
    None: message_key('network.object_types.all'),
    'person': message_key('objects.person.plural'),
    'organisation': message_key('objects.organisation.plural'),
    'resource': message_key('objects.resource.plural'),
    'relationships': message_key('network.object_types.relationships'),
    'agreement': message_key('network.object_types.agreements'),
    'capacity': message_key('objects.capacity.plural'),
    'need': message_key('objects.need.plural'),
    'evidence': message_key('objects.evidence.label'),
    'objective': message_key('objects.objective.plural'),
    'policy': message_key('network.object_types.policies'),
    'invitation': message_key('objects.invitation.plural'),
}

PRIORITY = {'invitation':0,'agreement':0,'objective':1,'policy':2,'resource':3,'person':4,'organisation':5,
            'evidence':6,'capacity':7,'need':8}
LAYERS = {'inferred':('#71889f','dotted'),'documented':('#a3bd95','solid'),
          'declared':('#c4a7e7','solid'),'agreement':('#d88356','solid'),
          'institutional':('#eee8d5','solid'),'invitation':('#e8b65e','dotted'),
          'connection':('#a3bd95','solid'),
          'historical_whiteboard':('#a7b6ff','solid'), 'recollection':('#c4a7e7','dotted'),
          'corroborated':('#78d8ba','solid'), 'disputed_recollection':('#e38a76','dotted'),
          'prior_relationship':('#d7b494','solid'), 'reconstruction_invitation':('#e8b65e','dashed')}

RECONSTRUCTION_CATEGORIES = {
    'historical_whiteboard': message_key('network.layers.whiteboard'), 'recollection': message_key('network.layers.one_sided'),
    'corroborated': message_key('network.layers.mutual'), 'disputed_recollection': message_key('network.layers.disputed'),
    'prior_relationship': message_key('network.layers.prior_relationship'),
}

# Historical category values are stable graph filter inputs.
_CATEGORY_IDS = {
    message_key('network.layers.affiliations'): 'Recorded affiliations',
    message_key('network.layers.documented'): 'Other documented relationships',
    message_key('network.layers.inferred'): 'Inferred complementarities',
    message_key('network.layers.pending_invitations'): 'Pending invitations',
    message_key('network.layers.accepted_connections'): 'Accepted connections',
    message_key('network.layers.proposed_agreements'): 'Proposed agreements',
    message_key('network.layers.accepted_agreements'): 'Accepted or active agreements',
    message_key('network.layers.verified_outcomes'): 'Verified outcomes',
    message_key('network.layers.whiteboard'): 'Whiteboard evidence',
    message_key('network.layers.one_sided'): 'One-sided recollection',
    message_key('network.layers.mutual'): 'Mutual recollection',
    message_key('network.layers.disputed'): 'Disputed recollection',
    message_key('network.layers.prior_relationship'): 'Prior relationship declaration',
    message_key('history.title'): 'History',
}
_CATEGORY_KEYS = {category: key for key, category in _CATEGORY_IDS.items()}
CATEGORIES = tuple(category for category in _CATEGORY_KEYS if category != 'History')


def _category_key(edge, lookup):
    if edge['layer'] in RECONSTRUCTION_CATEGORIES:
        return RECONSTRUCTION_CATEGORIES[edge['layer']]
    if edge['layer'] == 'reconstruction_invitation':
        return message_key('network.layers.pending_invitations')
    if edge['layer']=='invitation':
        return message_key('network.layers.pending_invitations') if edge.get('status')=='sent' else message_key('network.layers.accepted_connections') if edge.get('status')=='accepted' else message_key('history.title')
    if edge['layer']=='connection':return message_key('network.layers.accepted_connections')
    if edge['layer']=='inferred':return message_key('network.layers.inferred')
    agreement=next((lookup.get(edge[key],{}) for key in ('source_id','target_id') if lookup.get(edge[key],{}).get('kind')=='agreement'),None)
    if agreement:
        if agreement['outcome_status']=='verified':return message_key('network.layers.verified_outcomes')
        return message_key('network.layers.accepted_agreements') if agreement['status'] in {'accepted','authorized','active','fulfilled'} else message_key('network.layers.proposed_agreements')
    if edge['kind']=='affiliated_with':return message_key('network.layers.affiliations')
    return message_key('network.layers.documented')



def object_type_label(kind):
    return t(OBJECT_TYPE_MESSAGES[kind])


def edge_category(edge, lookup, *, layer_categories=None):
    if layer_categories and edge['layer'] in layer_categories:
        return layer_categories[edge['layer']]
    return _CATEGORY_IDS[_category_key(edge, lookup)]


def category_label(category):
    key = _CATEGORY_KEYS.get(category)
    return t(key) if key else category



def focus_graph(graph, centre, *, related=None, query='', offset=0, limit=12, scope='neighbourhood', categories=None, three_d=False, labeler=node_label, object_type=None, layer_styles=None, layer_categories=None):
    """All incident relations remain available; pages disclose visual reduction.

    Party contracts retain their policy/objective/resources even though those
    are two hops from the actor. Strong inferred matches do not crowd them out.
    """
    styles = {**LAYERS, **(layer_styles or graph.get('layer_styles', {}))}
    layer_categories = layer_categories or graph.get('layer_categories', {})
    full_node_count=len(graph['nodes']); full_edge_count=len(graph['edges'])
    lookup = {n['id']:n for n in graph['nodes']}
    actor_ids = sorted(key for key, node in lookup.items() if node['kind'] in {'person', 'organisation'})
    incident = {e[key] for e in graph['edges'] for key in ('source_id', 'target_id')}
    if categories is not None or scope=='connections':
        edges=[e for e in graph['edges'] if (categories is None or edge_category(e, lookup, layer_categories=layer_categories) in categories)
               and (scope!='connections' or e['layer'] in {'invitation','connection'})]
        ids={e[k] for e in edges for k in ('source_id','target_id')}|{centre}
        graph={'nodes':[n for n in graph['nodes'] if n['id'] in ids],'edges':edges}
    if centre not in lookup:
        return {'nodes':[],'edges':[],'total':0,'offset':0,'centre':centre}
    if object_type == 'relationships':
        relational = [edge for edge in graph['edges'] if edge['layer'] not in {'institutional', 'agreement'}]
        graph = {**graph, 'edges': relational}
    adjacent = {e['target_id'] if e['source_id']==centre else e['source_id'] for e in graph['edges']
                if centre in (e['source_id'],e['target_id'])}
    contracts = {key for key in adjacent if lookup.get(key,{}).get('kind')=='agreement'}
    contracts.update(e['target_id'] for e in graph['edges'] if e['kind']=='party_to'
                     and e['source_id'] in {centre,related})
    for edge in graph['edges']:
        if edge['source_id'] in contracts or edge['target_id'] in contracts:
            adjacent.update((edge['source_id'],edge['target_id']))
    if scope in {'whole','connections'}:adjacent={n['id'] for n in graph['nodes']}
    adjacent.discard(centre)
    if object_type and object_type != 'relationships':
        adjacent = {key for key in adjacent if lookup.get(key, {}).get('kind') == object_type}
    ordered = sorted((key for key in adjacent if key in lookup and folded(query) in folded(labeler(lookup[key]))),
        key=lambda key:(0 if key==related else 1,PRIORITY.get(lookup[key]['kind'],99),folded(labeler(lookup[key])),key))
    offset = min(max(0,offset),max(0,((len(ordered)-1)//limit)*limit))
    chosen = [centre,*ordered[offset:offset+limit]]
    ids = set(chosen)
    # Inferred domain edges are bundled visually, with every original assertion
    # retained in the bundle. No authoritative edge, status or direction changes.
    groups = defaultdict(list)
    for edge in graph['edges']:
        if edge['source_id'] in ids and edge['target_id'] in ids:
            groups[(edge['source_id'],edge['target_id'],edge['kind'],edge['layer'],edge.get('directed'))].append(deepcopy(edge))
    edges = []
    for i, ((source,target,kind,layer,directed), records) in enumerate(groups.items()):
        # Structural ownership and contract links have explicit direction in the
        # Commons projection; unknown source relation direction stays unknown.
        if 'directed' not in records[0] and layer in {'agreement','institutional'}:
            directed = True
        colour,pattern = styles.get(layer,('#aaaaaa','solid'))
        epistemic_status=(records[0].get('status','unknown')+t('network.contact_invitation')) if layer=='invitation' else t('network.acknowledged_contact_only') if layer=='connection' else layer
        if kind=='party_to':
            accepted=records[0].get('status') in {'accepted','authorized','active','fulfilled'}
            colour,pattern=('#a3bd95','solid') if accepted else ('#d88356','dotted')
            epistemic_status=t('network.accepted_agreement_party') if accepted else t('network.proposed_or_inactive_contract_party')
        edges.append({'id':str(i),'source':source,'target':target,'visual_source':source,'visual_target':target,
            'kind':kind,'layer':layer,'directed':directed,'weight':len(records),
            'colour':colour,'pattern':pattern,'records':records,'epistemic_status':epistemic_status,
            'unknown_marker':directed is None})
    nodes=[]
    for i,key in enumerate(chosen):
        node=deepcopy(lookup[key]);style=OBJECTS.get(node['kind'],OBJECTS['evidence'])
        angle=2*math.pi*max(0,i-1)/max(1,len(chosen)-1)
        if len(chosen) == 3 and i:
            # Keep a three-object neighbourhood from collapsing onto one line.
            angle = (2*i-1)*math.pi/4
        node.update(visual_id=key,entity_type='participant' if node['kind']=='person' else node['kind'],
            position=([0.,0.,0.] if i==0 else [5.5*math.sin(math.acos(1-2*i/len(chosen)))*math.cos(i*2.399963229728653),
                      2.7*math.sin(math.acos(1-2*i/len(chosen)))*math.sin(i*2.399963229728653),3.5*(1-2*i/len(chosen))]) if three_d else
                     ([0.,0.,-1.] if i==0 else [7.0*math.cos(angle),3.0*math.sin(angle),0.]),
            symbol=style.symbol,ascii_symbol=style.plain[1] if len(style.plain)>2 else '?',colour=style.colour)
        nodes.append(node)
    return {'nodes':nodes,'edges':edges,'total':len(ordered),'offset':offset,'centre':centre,
            'full_node_count':full_node_count,'full_relationship_count':full_edge_count,
            'rendered_relationship_count':sum(len(e['records']) for e in edges),
            'scope':scope,'three_d':three_d, 'actor_ids':actor_ids,
            'context_actor_ids':[key for key in actor_ids if key not in ids],
            'isolated_actor_ids':set(actor_ids)-incident}


def _fit_points(points, width, height, margin, zoom, perspective):
    """Fit projected bounds, then apply intentional zoom about the canvas centre."""
    if not points:
        return {}
    x_margin, y_margin = margin
    x0, x1 = min(p[0] for p in points.values()), max(p[0] for p in points.values())
    y0, y1 = min(p[1] for p in points.values()), max(p[1] for p in points.values())
    def scale(span, size, padding):
        padding = min(max(0, padding), max(0, (size-3)//2))
        return (size-1-2*padding)/span if span > 1e-9 else math.inf
    sx, sy = scale(x1-x0, width, x_margin), scale(y1-y0, height, y_margin)
    if perspective:
        sx = sy = min(sx, sy)
    sx, sy = (factor*zoom if math.isfinite(factor) else 1. for factor in (sx, sy))
    return {key: ((width-1)/2+(x-(x0+x1)/2)*sx,
                  (height-1)/2+(y-(y0+y1)/2)*sy, depth)
            for key, (x, y, depth) in points.items()}


def _place_labels(lines, nodes, points, labels, plain, labeler, *, numbered=False, selected=None, show_numbers=True, selected_only=False):
    """Use only clear raster cells. Leave a numbered marker if text cannot fit."""
    height, width = len(lines), len(lines[0])
    placements = []
    for i, node in enumerate(nodes, 1):
        key = node['id']
        if key not in points or selected_only and key != selected:
            continue
        x, y = map(round, points[key][:2])
        if not (0 <= x < width and 0 <= y < height):
            continue
        name = '' if numbered and key != selected else (labels or {}).get(key, labeler(node))
        if plain:
            name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        # Raster coordinates are single-cell. Full names are available in Inspect.
        name = ''.join(c for c in name if c.isprintable() and not unicodedata.combining(c)
                       and display_width(c) == 1)
        full = (f'{i} {name}' if show_numbers else name).rstrip()
        if not full:
            continue
        mark = '~' if plain else '…'
        cap = min(22, max(4, width//3))
        candidates = [(full if len(full) <= cap else full[:cap-1]+mark)]
        if len(full) > 9:
            candidates.append(full[:8]+mark)
        if show_numbers:
            candidates.append(str(i))
        for label in candidates:
            placed = False
            for row, shift in ((y+1,0),(y-1,0),(y,1),(y,-1),(y+2,0),(y-2,0)):
                start = (x+2 if shift == 1 else x-len(label)-1 if shift == -1
                         else max(0,min(width-len(label),x-len(label)//2)))
                if 0 <= row < height and 0 <= start <= width-len(label) and all(
                        cell == ' ' for cell in lines[row][start:start+len(label)]):
                    lines[row][start:start+len(label)] = label
                    placements.append((row, start, len(label), key))
                    placed = True
                    break
            if placed:
                break
    return placements


def _draw_context(lines, visual, plain, mode):
    """Stable sparse slots; use hashed density bins if the roster exceeds the canvas."""
    if mode == 'hidden':
        return []
    height, width = len(lines), len(lines[0])
    actors = visual.get('actor_ids', ())
    context = set(visual.get('context_actor_ids', ()))
    isolated = visual.get('isolated_actor_ids', set())
    bins = defaultdict(list)
    for actor_id in actors:
        slot = int.from_bytes(sha256(actor_id.encode()).digest()[:8], 'big') % (height*width)
        if len(actors) <= height*width:
            while slot in bins:
                slot = (slot+1) % (height*width)
        bins[slot].append(actor_id)
    spans = []
    for slot, occupants in bins.items():
        visible = [actor for actor in occupants if actor in context]
        row, col = divmod(slot, width)
        if not visible or lines[row][col] != ' ':
            continue
        if len(visible) > 1:
            glyph = str(len(visible)) if len(visible) < 10 else '+'
        elif visible[0] in isolated:
            glyph = 'o' if plain else '∘'
        else:
            glyph = ('.' if plain else '·') if mode == 'dim' else ('o' if plain else '●')
        lines[row][col] = glyph
        spans.append((row, col, 1, '#465060' if mode == 'dim' else '#c4a7e7', None, False))
    return spans


@dataclass(frozen=True)
class GraphLayout:
    width: int
    height: int
    points: dict[str, tuple[float, float, float]]

    def hit_test(self, row, column):
        hits = [key for key, (x, y, _) in self.points.items() if (round(y), round(x)) == (row, column)]
        return min(hits, key=lambda key: self.points[key][2]) if hits else None


def layout_graph(visual, width, height, *, angle=0., zoom=1., yaw=0., pitch=0., margin=None):
    """Project the same graph data onto planar or perspective coordinates."""
    width, height = max(8, width), max(3, height)
    coordinates = {node['id']: node['position'] for node in visual['nodes']}
    perspective=visual.get('three_d',False)
    if perspective:
        cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
        for key, (x, y, z) in coordinates.items():
            x, z = cy*x+sy*z, -sy*x+cy*z
            coordinates[key] = (x, cp*y-sp*z, sp*y+cp*z)
        angle=0.
    points=project(coordinates,width,height,
                   perspective=perspective,angle=angle,axis='z')
    points=_fit_points(points,width,height,margin or (min(9,max(2,width//10)),2),zoom,perspective)
    return GraphLayout(width, height, points)


def draw_graph(visual, width, height, *, selected=None, plain=False, angle=0., zoom=1., labels=None,
               yaw=0., pitch=0., margin=None, background='dim', labeler=node_label, edge_renderer='braille',
               show_labels=True, show_numbers=None, edge_annotations=True, selected_only=False,
               emphasise=False):
    if background not in {'hidden', 'dim', 'full'}:
        raise ValueError('unknown_graph_background')
    layout = layout_graph(visual, width, height, angle=angle, zoom=zoom, yaw=yaw, pitch=pitch, margin=margin)
    width, height, points = layout.width, layout.height, layout.points
    if emphasise or not edge_annotations:
        edges = []
        for edge in visual['edges']:
            edge = dict(edge)
            if emphasise and selected is not None:
                incident = selected in (edge['visual_source'], edge['visual_target'])
                edge.update(colour=NAVIGATION if incident else '#465060', highlighted=incident)
            if not edge_annotations:
                edge.update(directed=False, unknown_marker=False)
            edges.append(edge)
        nodes = visual['nodes']
        if emphasise and selected is not None:
            neighbours = {edge[field] for edge in edges if edge['highlighted']
                          for field in ('visual_source', 'visual_target')}
            nodes = [{**node, 'colour': NAVIGATION if node['id'] in neighbours else '#636b75'}
                     for node in nodes]
        visual = {**visual, 'edges': edges, 'nodes': nodes}
    frame = {'changes': {'nodes_added': [], 'edges_added': []}}
    image=raster(frame,width,height,layers=set(LAYERS),selected=selected,ascii_only=plain,
                 visual=visual,projected=points,edge_renderer=edge_renderer)
    lines=[list(line) for line in image.plain.splitlines()]
    legacy = show_numbers is None
    spans = []
    if show_labels or show_numbers:
        placements = _place_labels(lines, visual['nodes'], points, labels, plain, labeler,
                                   numbered=not show_labels or legacy and zoom < .85,
                                   selected=selected if show_labels else None,
                                   show_numbers=legacy or show_numbers, selected_only=selected_only)
        if emphasise and selected is not None:
            spans.extend((row, column, length, NAVIGATION if key == selected else SECONDARY, None, key == selected)
                         for row, column, length, key in placements)
    for offset,length,style in image.spans:
        row,column=divmod(offset,width+1)
        spans.append((row,column,length,style.split()[-1],None,'bold' in style))
    spans.extend(_draw_context(lines,visual,plain,background))
    return [''.join(line) for line in lines],spans
