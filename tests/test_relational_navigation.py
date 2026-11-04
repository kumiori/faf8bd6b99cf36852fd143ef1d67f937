"""Heatmap, extracted-renderer parity and agency-safe relational navigation."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

from commons_game import load_scenario
from commons_game.expertise import matrix
from commons_game.fullscreen import Screen
from commons_game.heatmap import BANDS, band, mark
from commons_game.network_view import focus_graph, draw_graph
from commons_game.renderers.hack_terminal import project, raster
from commons_game.scenario_catalogue import catalogue, scenarios_for
from commons_game.gathering import conditions
from commons_game.scenario import demo_commands
from test_matrix_navigation import app, world


def proposed():
    ui,port=app(answers=['Specific agreement','A shared purpose','Offer a review','Request a workshop','','y'],choices=[0])
    ui.route.column=1;ui.handle('enter',ui.build_screen());ui.act(ui.build_screen())
    target=next(iter(ui.world()['agreements']))
    return ui,target


@pytest.mark.parametrize('count,maximum',[(0,0),(1,1),(2,3),(3,3),(4,6),(6,6),(7,10),(10,10),(11,None),(17,None),(99,None)])
def test_fixed_absolute_heatmap_scale(count,maximum):
    assert band(count).maximum==maximum
    assert mark(count,numeric=True)==str(count)
    assert mark(count,plain=True)==band(count).ascii
    assert mark(None)=='?' and mark(count,diagonal=True)=='-'


def test_heatmap_toggle_changes_only_presentation_and_keeps_full_axes_reachable():
    ui,_=app();before=ui.world(),ui.current().project('log');screen=ui.build_screen()
    assert 'HEATMAP' in screen.title and screen.styles
    ui.handle('z',screen);assert 'NUMERIC' in ui.build_screen().title
    assert not ui.build_screen().styles
    ui.handle('z',ui.build_screen());ui.width=42;ui.height=18
    ui.route.row=2;ui.route.column=2
    text='\n'.join(ui.build_screen().lines)
    assert 'Rows 3' in text and 'Columns' in text and 'Morg' in text
    assert before==(ui.world(),ui.current().project('log'))


def test_player_focus_relation_breadcrumbs_and_back_are_separate_contexts():
    ui,_=app();playing=ui.playing_actor;ids=[a['id'] for a in matrix(ui.world())['actors']]
    ui.route.column=1;ui.handle('enter',ui.build_screen());screen=ui.build_screen()
    assert 'Reverse: Casey' in '\n'.join(screen.lines)
    assert 'Data stewardship' in '\n'.join(screen.lines) and 'Coalition building' in '\n'.join(screen.lines)
    ui.route.index=1;ui.handle('enter',screen)
    assert ui.focused_actor==ids[1] and ui.playing_actor==playing
    assert ui.focused_relation==(ids[0],ids[1])
    assert 'Alex → Casey' in ui.breadcrumbs() and ui.breadcrumbs().endswith('Casey')
    ui.back();assert ui.route.kind=='cell' and ui.route.index==1
    assert ui.playing_actor==playing and ui.focused_relation==(ids[0],ids[1])


def test_observation_only_cell_never_promotes_focus_to_agency():
    ui,_=app();ids=[a['id'] for a in matrix(ui.world())['actors']]
    ui.route.row=1;ui.route.column=2;ui.handle('enter',ui.build_screen())
    before=ui.world(),ui.current().project('log');screen=ui.build_screen()
    assert 'OBSERVATION ONLY' in '\n'.join(screen.lines)
    ui.act(screen);assert 'your own row or column' in ui.notice
    ui.route.index=1;ui.handle('enter',screen)
    assert ui.focused_actor==ids[2] and ui.playing_actor==ids[0]
    assert before==(ui.world(),ui.current().project('log'))


def test_new_contract_returns_to_same_relation_and_network_reaches_policy_objective_and_party():
    ui,target=proposed();playing=ui.playing_actor
    assert ui.route.kind=='cell' and ui.focused_relation is not None
    screen=ui.build_screen();assert screen.entries[ui.route.index][1]==target
    ui.open_network();screen=ui.build_screen()
    assert 'HACK RENDERER' in screen.title and not screen.show_entries and screen.styles
    assert any(value==target for _,value in screen.entries)
    visual=ui._network;ids={n['id'] for n in visual['nodes']}
    agreement=ui.world()['agreements'][target];version=agreement['versions'][0]
    assert {target,agreement['objective_id'],version['policy_id'],*agreement['parties']}<=ids
    assert any(e['epistemic_status']=='proposed or inactive contract party' for e in visual['edges'])
    before=ui.world(),ui.current().project('log')
    ui.route.index=next(i for i,(_,value) in enumerate(screen.entries) if value==target)
    ui.handle('enter',screen);screen=ui.build_screen()
    assert 'Proposed by: Alex' in '\n'.join(screen.lines)
    assert all(any(value==p for _,value in screen.entries) for p in agreement['parties'])
    objective=agreement['objective_id'];ui.push('inspect',objective);screen=ui.build_screen()
    entry=next((i,value) for i,(_,value) in enumerate(screen.entries) if isinstance(value,tuple) and value[0]=='scenario')
    ui.route.index=entry[0];ui.handle('enter',screen)
    assert ui.route.kind=='scenario' and 'SOURCE MATERIAL' in '\n'.join(ui.build_screen().lines)
    for _ in range(3):ui.back()
    assert ui.route.kind=='network' and ui.playing_actor==playing
    ui.back();assert ui.route.kind=='cell'
    assert before==(ui.world(),ui.current().project('log'))


def test_network_keeps_related_counterparty_contracts_and_unknown_direction_without_invented_links():
    ui,target=proposed();graph=ui.graph_projection();before=deepcopy(graph)
    actors=matrix(ui.world())['actors'];third=actors[2]['id'];partner=actors[1]['id']
    visual=focus_graph(graph,third,related=partner)
    # Third has no offer match, but its missing need is not promoted to an edge.
    assert target in {n['id'] for n in visual['nodes']}
    for edge in visual['edges']:
        for record in edge['records']:assert record in graph['edges']
    assert any(e['directed'] is None and e['unknown_marker'] for e in visual['edges'])
    assert graph==before
    lines,styles=draw_graph(visual,70,14,selected=third,plain=True)
    assert len(lines)==14 and all(len(line)==70 for line in lines)
    assert styles and '?' in '\n'.join(lines) and '@' in '\n'.join(lines)


def test_network_paging_rotation_zoom_and_centring_preserve_canonical_state():
    ui,target=proposed();ui.open_network();screen=ui.build_screen();before=ui.world(),ui.current().project('log')
    ui.handle('tab',screen);screen=ui.build_screen();selected=screen.entries[ui.route.index][1]
    ui.handle('r',screen);ui.handle('+',screen)
    assert ui.route.extra['angle'] and ui.route.extra['zoom']>1
    ui.handle('f',screen);assert ui.route.target==selected
    ui.handle(']',ui.build_screen());ui.handle('[',ui.build_screen())
    assert ui.playing_actor!=None and before==(ui.world(),ui.current().project('log'))


def test_workshop_catalogue_uses_source_material_and_never_relabels_generic_objective_as_scenario():
    game=world();before=game.get_world(),game.project('log');records=catalogue(game.get_world())
    assert not any(r['id']=='montreal-commons' for r in records)
    workshop=next(r for r in records if r['id']=='montreal-geneva-workshop')
    assert workshop['provenance']['kind']=='authored_workshop_scenario'
    assert workshop['provenance']['revision']==5 and workshop['source_review']
    assert 'coalition' in {o['source_code'] for o in workshop['possible_objectives']}
    assert scenarios_for('montreal-collaboration',game.get_world())==[workshop]
    assert all('synthetic' in r['title'] for r in records if r['id'].startswith('fixture:'))
    assert before==(game.get_world(),game.project('log'))


def test_gathering_attendance_gate_remains_separate_from_verified_outcome():
    game=load_scenario('commons-gathering')
    for command in demo_commands('commons-gathering')[:5]:assert game.submit(command)['ok']
    w=game.get_world();objective=next(iter(w['objectives'].values()));before=deepcopy(w),game.project('log')
    text='\n'.join(conditions(w,objective))
    assert 'Accepted invitations: 2' in text and 'including proposer): 3/3' in text
    assert 'outcome: unverified' in text and 'not verified realisation' in text
    assert objective['status']=='open' and before==(game.get_world(),game.project('log'))


def test_observer_can_only_create_their_own_explicit_profile_agreement_context():
    ui,port=app(answers=['My own agreement','A review','Offer a review','Request discussion','','y'],choices=[0])
    ids=[a['id'] for a in matrix(ui.world())['actors']]
    ui.route.row=1;ui.route.column=2;ui.handle('enter',ui.build_screen())
    screen=ui.build_screen();ui.route.index=1;ui.handle('enter',screen)
    assert ui.focused_relation==(ids[1],ids[2]) and ui.playing_actor==ids[0]
    ui.act(ui.build_screen());assert ui.route.kind=='cell'
    ui.build_screen();assert ui.focused_relation==(ids[0],ids[2])
    agreement=next(iter(ui.world()['agreements'].values()))
    assert agreement['created_by']==ids[0] and set(agreement['parties'])=={ids[0],ids[2]}
    assert agreement['versions'][0]['acceptances']=={}


def test_extracted_hack_camera_and_raster_match_the_inspected_upstream(monkeypatch):
    pytest.importorskip('numpy');pytest.importorskip('rich')
    root=Path(__file__).resolve().parents[1]
    manifest=json.loads((root/'docs/hack-renderer-source.json').read_text())
    source=root.parent/'app_protocol_hack'/manifest['source_module']
    if not source.exists():pytest.skip('Optional original Hack renderer parity requires its checkout')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256']
    stub=types.ModuleType('temporal_graph.visualization.adapter');stub.STYLES={};stub.view=lambda *a,**k:None
    monkeypatch.setitem(sys.modules,'temporal_graph.visualization.adapter',stub)
    spec=importlib.util.spec_from_file_location('hack_reference_raster',source);upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
    coordinates={'a':[1.,2.,3.],'b':[-2.,.75,-19.],'c':[3.,-2.,1.]}
    for axis in ('x','y','z'):
        for perspective in (True,False):
            expected=upstream.project(coordinates,82,25,angle=.71,axis=axis,zoom=.8,perspective=perspective)
            actual=project(coordinates,82,25,angle=.71,axis=axis,zoom=.8,perspective=perspective)
            assert actual.keys()==expected.keys()
            for key in actual:assert actual[key]==pytest.approx(expected[key])
    visual={'nodes':[{'id':key,'visual_id':key,'entity_type':'participant','position':value} for key,value in coordinates.items()],
            'edges':[{'id':'ab','visual_source':'a','visual_target':'c','layer':'organizational','directed':True,'weight':1}]}
    frame={'changes':{'edges_added':[],'nodes_added':[]}}
    for ascii_only in (True,False):
        assert raster(frame,82,25,layers=[],visual=visual,ascii_only=ascii_only).plain==upstream.raster(
            frame,82,25,layers=[],visual=visual,ascii_only=ascii_only).plain
