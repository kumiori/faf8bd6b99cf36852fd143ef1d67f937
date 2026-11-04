"""Synthetic matrix arithmetic, invitation authority and dual pathway acceptance."""
from copy import deepcopy
import pytest
from commons_game.expertise import cell, matrix
from commons_game.ecosystem_import import import_snapshot
from commons_game import load_scenario
from test_matrix_navigation import synthetic_snapshot, app


def test_nathalie_catherine_snapshot_score_and_matching_list_are_identical():
    snapshot=synthetic_snapshot()
    # Fictional labels and invented expertise; no private source data in tests.
    person_ids=[]
    for record in snapshot['records']:
        if record['kind']=='person':
            person_ids.append(record['record_id'])
            record['fields']['label']=['Nathalie Example','Catherine Example','Morgan Example'][len(person_ids)-1]
    vocabulary={str(i):'Fictional domain '+str(i) for i in range(1,6)}
    snapshot['expertise']['vocabulary']=vocabulary
    profiles=list(snapshot['expertise']['participants'].values())
    for profile in profiles:
        for observation in profile.values():observation.update(state='answered',codes=[])
    profiles[0]['offer']['codes']=list(vocabulary)
    profiles[1]['need']['codes']=list(vocabulary)[:4]
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot)
    old=matrix(game.get_world());names=[a['label'].split()[0] for a in old['actors']]
    i,j=names.index('Nathalie'),names.index('Catherine')
    assert old['W'][i][j]==4
    # A later source capture may legitimately change a count, never a view of
    # the same immutable prefix. Store and compare both snapshots explicitly.
    snapshot=deepcopy(snapshot);snapshot['captured_at']='2026-11-05T00:00:00+00:00'
    snapshot['expertise']['source_version']='fictional-v2'
    profiles=list(snapshot['expertise']['participants'].values());profiles[1]['need']['codes']=list(vocabulary)
    import_snapshot(game,snapshot)
    ui,_=app(game);current=matrix(ui.world());before=deepcopy(current)
    assert current['W'][i][j]==5 and matrix(game.world_at(event=2))['W'][i][j]==4
    ui.route.row=i;ui.route.column=j
    assert 'Exact matches: 5' in '\n'.join(ui.build_screen().lines)
    ui.handle('enter',ui.build_screen());ui.build_screen()
    assert ui._cell['value']==5==len(ui._cell['matching_codes'])
    assert matrix(ui.world())==before
    for row in range(len(current['actors'])):
        for col in range(len(current['actors'])):
            d=cell(current,row,col)
            assert d['value']==current['W'][row][col]==sum(a*b for a,b in zip(current['O'][row],current['N'][col]))
            assert len(d['matching_codes'])==d['value']


def test_partial_observations_produce_bounds_and_known_zero_annihilates_unknown():
    snapshot=synthetic_snapshot();profiles=list(snapshot['expertise']['participants'].values())
    profiles[0]['offer'].update(state='partial',codes=['x'])
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot)
    p=matrix(game.get_world())
    assert p['O'][0]==[1,None]
    assert p['W'][0][1]==1  # unknown y times known zero is zero
    assert p['W'][0][0] is None
    assert cell(p,0,0)['lower']==0 and cell(p,0,0)['upper']==1
    assert cell(p,0,2)['lower']==0 and cell(p,0,2)['upper']==2
    assert p['W'][2][2]==0  # complete empty offers times missing needs


def command(game, kind, actor, **values):
    return game.submit({'key':f'test-{len(game.project("log"))+1}-{kind}', 'kind':kind,'actor':actor,**values})


def contact(game, sender, recipient, iid='contact-test', **values):
    return command(game,'send_contact',sender,id=iid,recipient_id=recipient,message='Explore a possible collaboration?',**values)


def test_invitation_acceptance_is_atomic_persistent_idempotent_and_does_not_create_a_contract(tmp_path):
    from commons_engine.store import SQLiteStore
    from commons_game import CommonsGame
    from commons_game.player import ActorSession
    from commons_game.trajectory import project_trajectory,reconstruct,trajectory_yaml,load_trajectory_yaml,simulate_branch
    ui,_=app();g=ui.game;a,b,c=[p['id'] for p in matrix(g.get_world())['actors']]
    store=SQLiteStore(tmp_path/'world.sqlite',CommonsGame);store.initialise(g)
    payload={'key':'stable-invite','kind':'send_contact','id':'i-1','recipient_id':b,'message':'Explore data stewardship?'}
    sender=ActorSession(g,a,store=store);recipient=ActorSession(g,b,store=store)
    result=sender.submit(payload);assert result['ok']
    assert sender.submit(payload)==result
    assert recipient.inbox_records()[0]['id']=='i-1'
    before=store.load().get_world()
    assert command(store.load(),'respond_contact',c,invitation_id='i-1',response='accept')['errors']==['recipient_required']
    assert store.load().get_world()==before
    assert recipient.submit({'kind':'respond_contact','invitation_id':'i-1','response':'accept'})['ok']
    g=store.load();world=g.get_world()
    assert not world['agreements'] and world['relationships']['i-1']['status']=='accepted'
    assert world['relationships']['acknowledged:i-1']['directed'] is False
    event=g.project('log')[-1]
    assert event['kind']=='invitation.accepted'
    assert event['mutations'] and len([m for m in event['mutations'] if m['entity_type']=='relationship'])==2
    graph=g.project('network')
    assert any(e['kind']=='acknowledged_connection' for e in graph['edges'])
    assert any(n['kind']=='invitation' and n['id']=='i-1' for n in graph['nodes'])
    assert g.replay().get_world()==world
    document=project_trajectory(g)
    assert reconstruct(load_trajectory_yaml(trajectory_yaml(document))).get_world()==world
    before_bytes=(tmp_path/'world.sqlite').read_bytes()
    branch=simulate_branch(g,parent_sequence=3,commands=[{'key':'branch','kind':'withdraw_contact','actor':a,'invitation_id':'i-1'}],branch_id='alternative')
    assert branch['events'][-1]['kind']=='invitation.withdrawn'
    assert store.load().get_world()==world and (tmp_path/'world.sqlite').read_bytes()==before_bytes


def test_contact_decline_withdraw_draft_and_expiry_are_distinct_from_gathering():
    ui,_=app();g=ui.game;a,b,c=[p['id'] for p in matrix(g.get_world())['actors']]
    assert contact(g,a,b)['ok']
    assert command(g,'respond_contact',b,invitation_id='contact-test',response='decline',response_message='Another time')['ok']
    assert g.get_world()['relationships']['contact-test']['status']=='declined'
    assert contact(g,a,b,'i-2')['ok']
    assert command(g,'withdraw_contact',b,invitation_id='i-2')['errors']==['sender_required']
    assert command(g,'withdraw_contact',a,invitation_id='i-2')['ok']
    assert command(g,'respond_contact',b,invitation_id='i-2',response='accept')['errors']==['pending_contact_invitation_required']
    assert command(g,'draft_contact',a,id='draft',recipient_id=b,message='An editable local draft')['ok']
    from commons_game.player import ActorSession
    assert not any(i['id']=='draft' for i in ActorSession(g,b).inbox_records())
    assert command(g,'publish_contact',a,invitation_id='draft')['ok']
    assert contact(g,a,b,'expires',expires_at='2026-11-05T00:00:00+00:00')['ok']
    facilitator=next(p['id'] for p in g.get_world()['actors'].values() if 'facilitator' in p['roles'])
    assert command(g,'advance_time',facilitator,time='2026-11-06T00:00:00+00:00')['ok']
    assert g.get_world()['relationships']['expires']['status']=='expired'
    assert command(g,'respond_contact',b,invitation_id='expires',response='accept')['errors']==['invitation_expired']
    assert not g.get_world()['agreements']
    assert g.replay().get_world()==g.get_world()


def test_partial_matrix_bounds_equal_enumerated_completions():
    from itertools import product
    from commons_game.projections import complementarity
    for row in product((0,1,None),repeat=2):
        for col in product((0,1,None),repeat=2):
            p=complementarity([list(row)],[list(col)])['W'][0][0]
            possible=[]
            for complete in product((0,1),repeat=sum(v is None for v in row+col)):
                remaining=iter(complete);a,b=([next(remaining) if x is None else x for x in r] for r in (row,col))
                possible.append(sum(x*y for x,y in zip(a,b)))
            assert p['lower']==min(possible) and p['upper']==max(possible)
            assert p['value']==(possible[0] if len(set(possible))==1 else None)


def test_matrix_switching_search_inspection_and_context_have_one_snapshot():
    ui,port=app();p=matrix(ui.world());before=ui.world(),ui.current().project('log')
    ui.route.column=1
    ui.handle('O',ui.build_screen());s=ui.build_screen();assert 'OFFERS O' in s.title
    ui.handle('right',s);ui.handle('enter',ui.build_screen())
    assert ui.route.kind=='incidence' and 'Coalition building' in '\n'.join(ui.build_screen().lines)
    ui.back();ui.handle('N',ui.build_screen());assert 'NEEDS N' in ui.build_screen().title
    port.answers=iter(['steward']);ui.handle('/',ui.build_screen())
    assert ui.route.column==p['domains'].index('x')
    ui.handle('W',ui.build_screen());assert ui.route.column==1
    ui.handle('enter',ui.build_screen());s=ui.build_screen()
    text='\n'.join(s.lines)
    assert 'captured ' not in text and 'response-' not in text
    assert 'provider' in ' '.join(label.lower() for label,_ in s.entries)
    assert any(isinstance(value,tuple) and value[0]=='invite_to' for _,value in s.entries)
    ui.handle('d',s);assert 'responses' in '\n'.join(ui.build_screen().lines)
    ui.back();ui.back()
    assert ui.route.column==1 and before==(ui.world(),ui.current().project('log'))


def test_both_gameplay_pathways_and_unique_actionable_inbox():
    snapshot=synthetic_snapshot();profiles=list(snapshot['expertise']['participants'].values())
    profiles[2]['need'].update(state='answered',codes=['x'])
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot)
    ui,port=app(game);roster=matrix(ui.world())['actors'];a,b,c=[p['id'] for p in roster]
    ui.route.column=1;ui.handle('enter',ui.build_screen());ui.build_screen()
    original_relation=ui.focused_relation
    port.answers=iter(['Explore shared stewardship?','Learn together','y'])
    ui.handle('j',ui.build_screen());iid=ui.route.target
    assert ui.world()['relationships'][iid]['status']=='sent'
    assert not ui.world()['agreements']
    ui.assume_actor(roster[1]);ui.refresh();ui.push('inbox');s=ui.build_screen()
    assert len(s.entries)==1 and s.entries[0][1]==iid
    ui.handle('enter',s);port.answers=iter(['Happy to explore','y']);ui.handle('y',ui.build_screen())
    assert ui.world()['relationships'][iid]['status']=='accepted'
    assert ui.playing_actor==b and ui.focused_relation==original_relation
    ui.open_network();s=ui.build_screen()
    assert 'Showing ' in '\n'.join(s.lines)
    assert any(e['kind']=='acknowledged_connection' and e['directed'] is False for e in ui._network['edges'])
    ui.back();port.answers=iter(['Learning exchange','Learn together','Offer a workshop','Review a data policy','','y'])
    ui.propose_to(a);ui.build_screen();gid=next(iter(ui.world()['agreements']))
    assert ui.world()['agreements'][gid]['interaction_context']['invitation_id']==iid
    ui.push('inspect',gid)
    # Explicit individual acceptance, amendment clears all previous receipts.
    port.answers=iter(['y']);ui.handle('y',ui.build_screen())
    assert 'y Accept' not in ui.build_screen().footer
    ui.assume_actor(roster[0]);ui.refresh()
    port.answers=iter(['A negotiated purpose','Review a policy','Deliver a workshop','Review before sharing','y'])
    ui.handle('j',ui.build_screen())
    assert ui.world()['agreements'][gid]['current_version']==2
    assert not ui.world()['agreements'][gid]['versions'][-1]['acceptances']
    for actor in roster[:2]:
        ui.assume_actor(actor);ui.refresh();port.answers=iter(['y']);ui.handle('y',ui.build_screen())
    assert ui.world()['agreements'][gid]['status']=='accepted'
    assert ui.world()['agreements'][gid]['outcome_status']=='unverified'
    ui.push('inbox');assert [key for _,key in ui.build_screen().entries].count(gid)==1
    assert any(item['id']==gid for item in ui.session.inbox_records('Agreements in progress'))
    # An independent match is actionable without any invitation to that actor.
    ui.switch_mode('ecosystem');ui.assume_actor(roster[0]);ui.refresh();ui.route.row=0;ui.route.column=2
    ui.handle('enter',ui.build_screen());ui.build_screen()
    port.answers=iter(['Direct exchange','A second purpose','Offer a review','Review the proposal','','y'])
    ui.handle('k',ui.build_screen());ui.build_screen()
    second=next(a for a in ui.world()['agreements'].values() if a['id']!=gid)
    assert c in second['parties'] and second['interaction_context']['invitation_id'] is None
    assert not any(r['target_id']==c for r in ui.world()['relationships'].values() if r['kind']=='contact_invitation')
    ui.push('inspect',second['id'])
    for actor in (roster[0],roster[2]):
        ui.assume_actor(actor);ui.refresh();port.answers=iter(['y']);ui.handle('y',ui.build_screen())
    assert ui.world()['agreements'][second['id']]['status']=='accepted'
    assert len(ui.session.inbox_records())==1
    ui.push('history',second['id']);s=ui.build_screen();assert len(s.entries)==3
    ui.handle('enter',s);before=ui.world(),ui.current().project('log');ui.handle('y',ui.build_screen())
    assert before==(ui.world(),ui.current().project('log'))
    assert ui.game.replay().get_world()==ui.world()


def test_observer_never_gets_contact_or_direct_contract_actions_for_someone_elses_pair():
    ui,_=app();ui.route.row=1;ui.route.column=2;ui.handle('enter',ui.build_screen());s=ui.build_screen()
    assert not any(isinstance(v,tuple) and v[0] in {'invite_to','propose_to'} for _,v in s.entries)
    before=ui.world(),ui.current().project('log');ui.handle('j',s);ui.handle('k',s)
    assert before==(ui.world(),ui.current().project('log'))


def test_network_scopes_layer_filters_coverage_and_real_3d_are_read_only():
    from commons_game.network_view import focus_graph,draw_graph
    ui,port=app();g=ui.game;a,b,c=[p['id'] for p in matrix(ui.world())['actors']]
    assert contact(g,a,b)['ok'];ui.refresh();graph=ui.graph_projection();before=deepcopy(graph),g.get_world()
    visual=focus_graph(graph,a,scope='connections')
    assert visual['full_node_count']==len(graph['nodes'])
    assert visual['rendered_relationship_count']==3
    assert all(e['layer']=='invitation' for e in visual['edges'])
    whole=focus_graph(graph,a,scope='whole',limit=2)
    assert whole['total']==len(graph['nodes'])-1 and len(whole['nodes'])==3
    ids=set()
    for start in range(0,whole['total'],2):ids.update(n['id'] for n in focus_graph(graph,a,scope='whole',limit=2,offset=start)['nodes'])
    assert ids=={n['id'] for n in graph['nodes']}
    three=focus_graph(graph,a,scope='whole',three_d=True,limit=20)
    assert len({n['position'][2] for n in three['nodes']})>2
    one,_=draw_graph(three,90,25,yaw=0.,pitch=0.)
    two,_=draw_graph(three,90,25,yaw=.5,pitch=.7)
    assert one!=two
    ui.open_network();s=ui.build_screen();port.choices=iter([0]);ui.handle('S',s)
    s=ui.build_screen();assert 'Whole graph' in '\n'.join(s.lines)
    port.choices=iter([4]);ui.handle('L',s);assert ui.route.extra['categories']==['Pending invitations']
    ui.handle('3',ui.build_screen());ui.handle('}',ui.build_screen());ui.handle('r',ui.build_screen())
    assert ui.route.extra['pitch'] and ui.route.extra['yaw']
    assert before==(ui.graph_projection(),g.get_world())


def test_inbox_badges_wrap_in_a_narrow_monochrome_terminal(monkeypatch):
    import curses
    from commons_game.fullscreen import CursesViewport,Screen
    monkeypatch.setattr(curses,'curs_set',lambda *args:None)
    monkeypatch.setattr(curses,'has_colors',lambda:False)
    class Window:
        rows={}
        def keypad(self,*args):pass
        def getmaxyx(self):return 18,52
        def erase(self):self.rows={}
        def addnstr(self,row,col,text,length,*args):self.rows[row]=self.rows.get(row,'')+text[:length]
        def refresh(self):pass
    window=Window();viewport=CursesViewport(window,plain=True)
    screen=Screen('INBOX',['One entry per object'],[('K-001 · Data exchange · Proposed by you · Your acceptance pending · Rebecca’s acceptance pending · Outcome unverified','contract')],wrap_entries=True)
    viewport.draw(screen)
    text=' '.join(window.rows.values())
    assert 'Outcome unverified' in text and 'acceptance pending' in text
    assert sum('[1]' in line for line in window.rows.values())==1
    assert all(ord(c)<128 for c in text)


def test_direct_contract_does_not_allow_a_third_party_to_forge_execution_or_verification():
    ui,port=app(answers=['An exchange','A purpose','Offer a review','Review the offer','','y'])
    roster=matrix(ui.world())['actors'];a,b,c=[p['id'] for p in roster]
    ui.propose_to(b);g=ui.game;gid=next(iter(g.get_world()['agreements']))
    for actor in (a,b):assert command(g,'accept',actor,agreement_id=gid,version=1)['ok']
    before=g.get_world(),g.project('log')
    assert command(g,'accept',c,agreement_id=gid,version=1)['errors']==['party_required']
    assert command(g,'fulfill',c,agreement_id=gid,version=1,reference='Invented report',criteria=['Invented'])['ok'] is False
    assert command(g,'verify','simulation-verifier',agreement_id=gid,version=1,reference='No party evidence')['errors']==['invalid_transition']
    assert command(g,'declare',c,table='evidence',record={'reference':'Invented'})['errors']==['invalid_declaration_table']
    assert before==(g.get_world(),g.project('log'))


def test_partial_capture_and_known_absence_are_distinct_from_missing_and_empty():
    from commons_game.montreal_capture import declared_topics
    assert declared_topics({'payload':{'answers':{'knowledge_offer':['x']},'states':{'knowledge_offer':'partial'}}},'knowledge_offer',{'x':'X'})==(['x'],'partial')
    snapshot=synthetic_snapshot();profile=next(iter(snapshot['expertise']['participants'].values()))
    profile['offer'].update(state='partial',codes=['x'],observed_absent_codes=['y'])
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot)
    p=matrix(game.get_world());assert p['O'][0]==[1,0]
    assert p['observations'][p['actors'][0]['id']]['offer']['state']=='partial'
    assert p['W'][0][0]==0


def test_duplicate_first_names_are_distinct_and_consistent_across_matrix_inspector_and_graph():
    from commons_game.catalogue import people
    from commons_game.presentation import display_label
    snapshot=synthetic_snapshot();people_records=[r for r in snapshot['records'] if r['kind']=='person']
    for record,name in zip(people_records,('Nathalie ExampleA','Nathalie ExampleB','Catherine Example')):
        record['fields']['label']=name
    vocabulary={str(i):'Fictional domain '+str(i) for i in range(1,6)}
    snapshot['expertise']['vocabulary']=vocabulary
    profiles=list(snapshot['expertise']['participants'].values())
    for profile in profiles:
        for observation in profile.values():observation.update(state='answered',codes=[])
    profiles[0]['offer']['codes']=list(vocabulary)
    profiles[1]['offer']['codes']=list(vocabulary)[:4]
    profiles[2]['need']['codes']=list(vocabulary)
    game=load_scenario('montreal-commons');import_snapshot(game,snapshot);original=game.get_world()
    ui,_=app(game);p=matrix(ui.world());labels=[display_label(a) for a in p['actors']]
    assert len(labels)==len(set(labels))
    assert {'Nathalie (1)','Nathalie (2)','Catherine'}==set(labels)
    for name,count in [('Nathalie (1)',5),('Nathalie (2)',4)]:
        i,j=labels.index(name),labels.index('Catherine')
        assert p['W'][i][j]==count
        ui.route.row,ui.route.column=i,j
        ui.handle('enter',ui.build_screen());screen=ui.build_screen()
        assert ui._cell['value']==count==len(ui._cell['matching_codes'])
        assert name in '\n'.join(screen.lines)
        ui.back()
    for actor in people(original):
        label=display_label(actor)
        assert ui.label(actor['id'])==label
        assert display_label(ui.node(actor['id']))==label
    assert game.get_world()==original


def test_player_can_save_then_send_a_draft_without_delivering_it_early():
    ui,port=app(answers=['Explore stewardship?','','y'],choices=[1])
    roster=matrix(ui.world())['actors'];ui.contact_to(roster[1]['id']);iid=ui.route.target
    assert ui.world()['relationships'][iid]['status']=='draft'
    from commons_game.player import ActorSession
    assert not ActorSession(ui.game,roster[1]['id']).inbox_records()
    s=ui.build_screen();assert any(value[0]=='decision' and value[1]['kind']=='publish_contact' for _,value in s.entries if isinstance(value,tuple))
    port.answers=iter(['y']);ui.handle('enter',s)
    assert ui.world()['relationships'][iid]['status']=='sent'


def test_collision_labels_are_not_reassigned_by_new_source_people_or_sort_order():
    from commons_game.presentation import person_labels
    ui,_=app();w=ui.world();people_ids=[a['id'] for a in matrix(w)['actors']]
    for i,key in enumerate(people_ids[:2]):w['actors'][key]['label']='Amira Fictional'+str(i)
    before=person_labels(w)
    later=deepcopy(w);later['actors']['000-later']={**deepcopy(w['actors'][people_ids[0]]),'id':'000-later','label':'Amira Another'}
    labels=person_labels(later)
    assert all(labels[key]==before[key] for key in people_ids[:2])
    later['actors'][people_ids[0]]['status']='inactive'
    assert person_labels(later)[people_ids[1]]==before[people_ids[1]]
