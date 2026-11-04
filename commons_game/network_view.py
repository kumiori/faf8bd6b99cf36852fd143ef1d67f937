"""Commons multiplex → Hack raster input. Geometry is disposable presentation."""
from collections import defaultdict
from copy import deepcopy
import math

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
        node.update(visual_id=key,entity_type='participant' if node['kind']=='person' else node['kind'],
            position=([0.,0.,0.] if i==0 else [5.5*math.sin(math.acos(1-2*i/len(chosen)))*math.cos(i*2.399963229728653),
                      2.7*math.sin(math.acos(1-2*i/len(chosen)))*math.sin(i*2.399963229728653),3.5*(1-2*i/len(chosen))]) if three_d else
                     ([0.,0.,-1.] if i==0 else [7.0*math.cos(angle),3.0*math.sin(angle),0.]),
            symbol=style.symbol,ascii_symbol=style.plain[1] if len(style.plain)>2 else '?',colour=style.colour)
        nodes.append(node)
    return {'nodes':nodes,'edges':edges,'total':len(ordered),'offset':offset,'centre':centre,
            'full_node_count':full_node_count,'full_relationship_count':full_edge_count,
            'rendered_relationship_count':sum(len(e['records']) for e in edges),
            'scope':scope,'three_d':three_d}


def draw_graph(visual, width, height, *, selected=None, plain=False, angle=0., zoom=1., labels=None, yaw=0., pitch=0.):
    """Use the extracted camera and raster, then add readable node labels."""
    visual=deepcopy(visual)
    perspective=visual.get('three_d',False)
    if perspective:
        cy,sy,cp,sp=math.cos(yaw),math.sin(yaw),math.cos(pitch),math.sin(pitch)
        for node in visual['nodes']:
            x,y,z=node['position'];x,z=cy*x+sy*z,-sy*x+cy*z
            node['position']=[x,cp*y-sp*z,sp*y+cp*z]
        angle=0.
    frame={'changes':{'nodes_added':[],'edges_added':[]}}
    scale=min(width/20,height/9)
    fit=max(.05,min(1.,(width/2-10)/max(.01,14*scale),(height/2-2)/max(.01,3*scale)))
    zoom*=fit
    image=raster(frame,width,height,layers=set(LAYERS),selected=selected,ascii_only=plain,
                 visual=visual,perspective=perspective,angle=angle,zoom=zoom,axis='z')
    lines=[list(line) for line in image.plain.splitlines()]
    points=project({n['id']:n['position'] for n in visual['nodes']},width,height,perspective=perspective,angle=angle,zoom=zoom,axis='z')
    for i,node in enumerate(visual['nodes']):
        if node['id'] not in points:continue
        x,y,_=points[node['id']];x,y=int(round(x)),int(round(y))
        label=f'{i+1} '+(labels or {}).get(node['id'],display_label(node))[:18]
        start=max(0,min(width-len(label),x-len(label)//2));row=y+1 if y+1<height else y-1
        if 0<=row<height:
            for k,char in enumerate(label[:width]):
                if 0<=start+k<width:lines[row][start+k]=char
    spans=[]
    for offset,length,style in image.spans:
        row,column=divmod(offset,width+1)
        spans.append((row,column,length,style.split()[-1],None,'bold' in style))
    return [''.join(line) for line in lines],spans
