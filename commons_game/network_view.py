"""Commons multiplex → Hack raster input. Geometry is disposable presentation."""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import math
import unicodedata

from .presentation import OBJECTS, display_label
from .renderers.hack_terminal import raster, project

PRIORITY = {'invitation':0,'agreement':0,'objective':1,'policy':2,'resource':3,'person':4,'organisation':5,
            'evidence':6,'capacity':7,'need':8}
LAYERS = {'inferred':('#8caac4','dotted'),'documented':('#a3bd95','solid'),
          'declared':('#c4a7e7','solid'),'agreement':('#d88356','solid'),
          'institutional':('#eee8d5','solid'),'invitation':('#e8b65e','dotted'),
          'connection':('#a3bd95','solid')}

CATEGORIES = ('Recorded affiliations','Other documented relationships','Inferred complementarities',
              'Pending invitations','Accepted connections','Proposed agreements','Accepted or active agreements','Verified outcomes')


def edge_category(edge,lookup):
    if edge['layer']=='invitation':
        return 'Pending invitations' if edge.get('status')=='sent' else 'Accepted connections' if edge.get('status')=='accepted' else 'History'
    if edge['layer']=='connection':return 'Accepted connections'
    if edge['layer']=='inferred':return 'Inferred complementarities'
    agreement=next((lookup.get(edge[key],{}) for key in ('source_id','target_id') if lookup.get(edge[key],{}).get('kind')=='agreement'),None)
    if agreement:
        if agreement['outcome_status']=='verified':return 'Verified outcomes'
        return 'Accepted or active agreements' if agreement['status'] in {'accepted','authorized','active','fulfilled'} else 'Proposed agreements'
    if edge['kind']=='affiliated_with':return 'Recorded affiliations'
    return 'Other documented relationships'



def focus_graph(graph, centre, *, related=None, query='', offset=0, limit=12, scope='neighbourhood', categories=None, three_d=False):
    """All incident relations remain available; pages disclose visual reduction.

    Party contracts retain their policy/objective/resources even though those
    are two hops from the actor. Strong inferred matches do not crowd them out.
    """
    full_node_count=len(graph['nodes']); full_edge_count=len(graph['edges'])
    lookup = {n['id']:n for n in graph['nodes']}
    actor_ids = sorted(key for key, node in lookup.items() if node['kind'] in {'person', 'organisation'})
    incident = {e[key] for e in graph['edges'] for key in ('source_id', 'target_id')}
    if categories is not None or scope=='connections':
        edges=[e for e in graph['edges'] if (categories is None or edge_category(e,lookup) in categories)
               and (scope!='connections' or e['layer'] in {'invitation','connection'})]
        ids={e[k] for e in edges for k in ('source_id','target_id')}|{centre}
        graph={'nodes':[n for n in graph['nodes'] if n['id'] in ids],'edges':edges}
    if centre not in lookup:
        return {'nodes':[],'edges':[],'total':0,'offset':0,'centre':centre}
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
    from .presentation import folded
    ordered = sorted((key for key in adjacent if key in lookup and folded(query) in folded(display_label(lookup[key]))),
        key=lambda key:(0 if key==related else 1,PRIORITY.get(lookup[key]['kind'],99),folded(display_label(lookup[key])),key))
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
        colour,pattern = LAYERS.get(layer,('#aaaaaa','solid'))
        epistemic_status=(records[0].get('status','unknown')+' contact invitation') if layer=='invitation' else 'acknowledged contact only' if layer=='connection' else layer
        if kind=='party_to':
            accepted=records[0].get('status') in {'accepted','authorized','active','fulfilled'}
            colour,pattern=('#a3bd95','solid') if accepted else ('#d88356','dotted')
            epistemic_status='accepted agreement party' if accepted else 'proposed or inactive contract party'
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


def _place_labels(lines, nodes, points, labels, plain):
    """Use only clear raster cells. Leave a numbered marker if text cannot fit."""
    height, width = len(lines), len(lines[0])
    for i, node in enumerate(nodes, 1):
        key = node['id']
        if key not in points:
            continue
        x, y = map(round, points[key][:2])
        if not (0 <= x < width and 0 <= y < height):
            continue
        name = (labels or {}).get(key, display_label(node))
        if plain:
            name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
        # Raster coordinates are single-cell. Full names are available in Inspect.
        name = ''.join(c for c in name if c.isprintable() and not unicodedata.combining(c)
                       and unicodedata.east_asian_width(c) not in {'W', 'F'})
        full = f'{i} {name}'.rstrip()
        mark = '~' if plain else '…'
        cap = min(22, max(4, width//3))
        candidates = [(full if len(full) <= cap else full[:cap-1]+mark)]
        if len(full) > 9:
            candidates.append(full[:8]+mark)
        candidates.append(str(i))
        for label in candidates:
            placed = False
            for row, shift in ((y+1,0),(y-1,0),(y,1),(y,-1),(y+2,0),(y-2,0)):
                start = (x+2 if shift == 1 else x-len(label)-1 if shift == -1
                         else max(0,min(width-len(label),x-len(label)//2)))
                if 0 <= row < height and 0 <= start <= width-len(label) and all(
                        cell == ' ' for cell in lines[row][start:start+len(label)]):
                    lines[row][start:start+len(label)] = label
                    placed = True
                    break
            if placed:
                break


def _draw_context(lines, visual, plain):
    """Give the full actor roster stable slots before excluding foreground actors."""
    height, width = len(lines), len(lines[0])
    context = set(visual.get('context_actor_ids', ()))
    isolated = visual.get('isolated_actor_ids', set())
    slots, spans = set(), []
    for actor_id in visual.get('actor_ids', ()):
        if len(slots) == height*width:
            break
        slot = int.from_bytes(sha256(actor_id.encode()).digest()[:8], 'big') % (height*width)
        while slot in slots:
            slot = (slot+1) % (height*width)
        slots.add(slot)
        row, col = divmod(slot, width)
        if actor_id in context and lines[row][col] == ' ':
            lines[row][col] = ('o' if actor_id in isolated else '.') if plain else ('∘' if actor_id in isolated else '·')
            spans.append((row, col, 1, '#465060', None, False))
    return spans


def draw_graph(visual, width, height, *, selected=None, plain=False, angle=0., zoom=1., labels=None,
               yaw=0., pitch=0., margin=None):
    """Fit the foreground; preserve actors' screen-relative context across focus."""
    width, height = max(8, width), max(3, height)
    visual=deepcopy(visual)
    perspective=visual.get('three_d',False)
    if perspective:
        cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
        for node in visual['nodes']:
            x,y,z=node['position'];x,z=cy*x+sy*z,-sy*x+cy*z
            node['position']=[x,cp*y-sp*z,sp*y+cp*z]
        angle=0.
    frame={'changes':{'nodes_added':[],'edges_added':[]}}
    points=project({n['id']:n['position'] for n in visual['nodes']},width,height,
                   perspective=perspective,angle=angle,axis='z')
    points=_fit_points(points,width,height,margin or (min(9,max(2,width//10)),2),zoom,perspective)
    image=raster(frame,width,height,layers=set(LAYERS),selected=selected,ascii_only=plain,
                 visual=visual,projected=points)
    lines=[list(line) for line in image.plain.splitlines()]
    _place_labels(lines,visual['nodes'],points,labels,plain)
    spans=[]
    for offset,length,style in image.spans:
        row,column=divmod(offset,width+1)
        spans.append((row,column,length,style.split()[-1],None,'bold' in style))
    spans.extend(_draw_context(lines,visual,plain))
    return [''.join(line) for line in lines],spans
