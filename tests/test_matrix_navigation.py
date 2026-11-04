"""Synthetic evidence for strict matrix semantics and the full-screen player flow."""
import pytest

from commons_game import load_scenario
from commons_game.ecosystem_import import connector_people_snapshot, import_snapshot, source_id
from commons_game.expertise import SCHEMA, cell, matrix
from commons_game.fullscreen import FullScreenTerminal
from commons_game.montreal_capture import declared_topics
from commons_game.trajectory import load_trajectory_yaml, project_trajectory, reconstruct, trajectory_yaml


def synthetic_snapshot():
    snapshot = connector_people_snapshot([
        {'url': 'https://app.notion.com/'+str(i)*32, 'Name': name, 'institution': 'Fictional Organisation'}
        for i, name in enumerate(('Alex Example', 'Casey Example', 'Morgan Example'), 1)],
        captured_at='2026-11-04T00:00:00+00:00', data_source_id='people', database_id='people-db')
    ids = [source_id('person', 'people', str(i)*8+'-'+str(i)*4+'-'+str(i)*4+'-'+str(i)*4+'-'+str(i)*12) for i in (1,2,3)]
    profiles = {}
    for i, (actor, offers, needs) in enumerate(zip(ids, (['x'], ['y'], []), (['y'], ['x'], None)), 1):
        profiles[actor] = {}
        for side, codes in (('offer', offers), ('need', needs)):
            profiles[actor][side] = {'state': 'answered' if codes is not None else 'skipped', 'codes': codes or [],
                'unmapped_count': 0, 'source': {'data_source_id':'responses','record_id':f'response-{i}',
                'field':'knowledge_'+side,'captured_at':snapshot['captured_at']}}
    snapshot['expertise'] = {'schema_version':SCHEMA,'vocabulary':{'x':'Data stewardship','y':'Coalition building'},
                             'participants':profiles,'source_version':'fictional-v1'}
    return snapshot


def world():
    game = load_scenario('montreal-commons')
    assert not import_snapshot(game, synthetic_snapshot())['rejected']
    return game


class FakeViewport:
    def __init__(self, answers=(), choices=()):
        self.answers = iter(answers); self.choices = iter(choices); self.drawn = []

    def prompt(self, title, lines, context):
        self.drawn.append((title, lines, context))
        return next(self.answers)

    def choose(self, title, items, label, context, **kwargs):
        self.drawn.append((title, [label(item) for item in items], context))
        choice = next(self.choices, 0)
        return next(item for item in items if choice(item)) if callable(choice) else items[choice]


def app(game=None, **kwargs):
    viewport = FakeViewport(**kwargs)
    result = FullScreenTerminal(game or world(), viewport=viewport, plain=True)
    result.assume_actor(matrix(result.world())['actors'][0])
    return result, viewport


def test_strict_matrix_matches_independent_product_and_preserves_unknown_and_empty_rows():
    game = world(); before = game.get_world(), game.project('log')
    result = matrix(game.get_world())
    assert result['O'] == [[1,0],[0,1],[0,0]]
    assert result['N'] == [[0,1],[1,0],[None,None]]
    assert result['W'] == [[0,1,None],[1,0,None],[0,0,0]]  # observed empty offers annihilate unknown needs
    assert cell(result,0,1)['matching_domains'] == ['Data stewardship']
    assert cell(result,1,0)['matching_domains'] == ['Coalition building']
    assert cell(result,0,0)['self_pairing']
    assert all(edge['source_id'] != edge['target_id'] for edge in game.derive_possibilities())
    assert len(game.derive_possibilities()) == 2
    assert before == (game.get_world(), game.project('log'))


def test_old_positive_only_import_does_not_establish_a_known_zero_vector():
    snapshot = synthetic_snapshot(); snapshot.pop('expertise')
    game = load_scenario('montreal-commons'); import_snapshot(game,snapshot)
    result = matrix(game.get_world())
    assert not result['mapped'] and result['W'] == [[None]*3 for _ in range(3)]


@pytest.mark.parametrize('payload,state', [({},'invalid'),(None,'invalid'),([], 'answered'),
                                        ({'selected':[]},'answered'),(['__empty__'],'answered'),
                                        (['__empty__','x'],'invalid')])
def test_malformed_and_explicit_empty_answers_are_distinct(payload,state):
    selected, actual = declared_topics({'payload':{'answers':{'knowledge_offer':payload}}},'knowledge_offer',{'x':'X'})
    assert actual == state and selected == []


def test_skipped_stale_values_and_unmapped_selections_do_not_become_expertise():
    envelope = {'payload':{'answers':{'knowledge_offer':['x']},'states':{'knowledge_offer':'skipped'}}}
    assert declared_topics(envelope,'knowledge_offer',{'x':'X'}) == ([], 'skipped')
    envelope = {'payload':{'answers':{'knowledge_offer':['x','other','unreviewed']}}}
    assert declared_topics(envelope,'knowledge_offer',{'x':'X'},details=True) == (['x'],'answered',2)


def test_invalid_source_mapping_cannot_partially_modify_the_authoritative_world():
    game = world(); before = game.get_world(), game.project('log')
    snapshot = synthetic_snapshot()
    snapshot['expertise']['participants']['unresolved'] = next(iter(snapshot['expertise']['participants'].values()))
    with pytest.raises(ValueError, match='unresolved_expertise_actor'):
        import_snapshot(game,snapshot)
    assert before == (game.get_world(), game.project('log'))


def test_matrix_selection_back_mode_switch_and_player_switch_preserve_state():
    ui, port = app(choices=[1]); before = ui.world(), ui.current().project('log')
    ui.route.row, ui.route.column = 0,1
    screen = ui.build_screen()
    assert '* Your row/column' in '\n'.join(screen.lines)
    ui.handle('enter',screen); assert ui.route.kind == 'cell'
    ui.build_screen(); ui.route.scroll = 7
    ui.push('inspect',matrix(ui.world())['actors'][1]['id'])
    ui.back(); assert ui.route.kind == 'cell' and ui.route.scroll == 7
    ui.back(); assert ui.route.row == 0 and ui.route.column == 1
    ui.switch_mode('gathering'); assert 'No gathering objective' in '\n'.join(ui.build_screen().lines)
    ui.switch_mode('scenarios'); assert 'not implemented' in '\n'.join(ui.build_screen().lines)
    ui.switch_mode('ecosystem'); assert ui.route.column == 1
    ui.select_actor(); assert ui.session.actor == matrix(ui.world())['actors'][1]['id']
    ui.handle('o',ui.build_screen()); assert ui.route.row == 1
    ui.handle('n',ui.build_screen()); assert ui.route.column == 1
    assert before == (ui.world(), ui.current().project('log'))


def test_propose_negotiate_accept_graph_policy_history_inbox_and_trajectory():
    ui, port = app(answers=['Stewardship exchange','Share stewardship experience','Offer a review',
                            'Suggest a discussion','','y'],choices=[0])
    ui.route.column = 1; ui.handle('enter',ui.build_screen()); ui.build_screen()
    ui.act(ui.build_screen()); assert ui.route.kind == 'cell'
    screen=ui.build_screen();target=screen.entries[ui.route.index][1]
    ui.handle('enter',screen);assert ui.route.kind=='inspect'
    agreement = ui.world()['agreements'][target]
    assert agreement['label'] == 'Stewardship exchange' and agreement['status'] == 'proposed'
    assert agreement['versions'][0]['acceptances'] == {}
    assert agreement['versions'][0]['terms']['responsibilities'][0]['description'] == 'Offer a review'
    assert agreement['versions'][0]['terms']['responsibilities'][1]['description'] == 'Suggest a discussion'
    assert ui.session.inbox_groups()['Proposals received'] == []
    assert ui.session.inbox_groups()['My proposals'][0]['contract_id'] == target
    assert ui.session.inbox()[0]['reasons'] == ['Your proposal awaiting your acceptance']
    screen = ui.build_screen(); text = '\n'.join(screen.lines)
    assert 'Proposed by: Alex' in text and 'Governing policy' in text
    policy_id = ui.world()['agreements'][target]['versions'][0]['policy_id']
    assert any(entry[1] == policy_id for entry in screen.entries)
    ui.push('inspect',policy_id)
    assert 'RULE ENFORCED' in '\n'.join(ui.build_screen().lines)
    ui.back()
    ui.assume_actor(matrix(ui.world())['actors'][1]); ui.refresh()
    assert ui.session.inbox_groups()['Proposals received'][0]['contract_id'] == target
    port.answers=iter(['Revised purpose','Offer a review','A negotiated workshop','','y'])
    port.choices=iter([lambda item:item['kind']=='amend'])
    ui.act(ui.build_screen())
    agreement=ui.world()['agreements'][target]
    assert agreement['current_version']==2 and agreement['status']=='negotiating'
    assert agreement['versions'][1]['acceptances']=={}
    assert agreement['versions'][1]['terms']['responsibilities'][1]['description']=='A negotiated workshop'
    for actor in matrix(ui.world())['actors'][:2]:
        ui.assume_actor(actor);ui.refresh();port.answers=iter(['y']);port.choices=iter([lambda item:item['kind']=='accept'])
        ui.act(ui.build_screen())
    agreement=ui.world()['agreements'][target]
    assert agreement['status']=='accepted' and agreement['outcome_status']=='unverified'
    ui.push('history',target);screen=ui.build_screen()
    assert len(screen.entries)==4
    ui.handle('enter',screen);assert ui.route.extra['at']==3
    ui.act(ui.build_screen());assert 'read-only' in ui.notice
    ui.back();ui.back()
    game=ui.current();document=project_trajectory(game)
    assert reconstruct(load_trajectory_yaml(trajectory_yaml(document))).get_world()==game.get_world()
    assert game.replay().project('network')==game.project('network')


def test_self_pair_actions_and_third_party_cell_do_not_imply_authority():
    ui,_=app();before=ui.world(),ui.current().project('log')
    ui.handle('enter',ui.build_screen());ui.act(ui.build_screen())
    assert 'Self-pairing' in ui.notice
    ui.back();ui.route.row=1;ui.route.column=2
    ui.handle('enter',ui.build_screen());ui.act(ui.build_screen())
    assert 'your own row or column' in ui.notice
    assert before==(ui.world(),ui.current().project('log'))


def test_matrix_viewport_narrow_dimensions_and_ascii_identifiers_remain_optional():
    ui,_=app();ui.width=40;ui.height=16
    screen=ui.build_screen();text='\n'.join(screen.lines)
    assert 'notion:' not in text and 'STATE ' not in text and 'Example' not in text
    assert '? Unknown' in text and '- Self' in text
    ui.route.row=2;ui.route.column=2
    assert 'Rows 3' in '\n'.join(ui.build_screen().lines)


def test_synthetic_scenario_template_is_reviewed_as_proposed_contributions():
    game=load_scenario();ui,port=app(game,answers=['A specific agreement','A specific purpose',
        'A proposed research contribution','A proposed counterparty contribution','','y'])
    ui.assume_actor(game.get_world()['actors']['researcher'])
    payload=ui.collect_action({'kind':'propose'},game)
    assert payload['label']=='A specific agreement'
    assert payload['terms']['purpose']=='A specific purpose'
    assert {r['description'] for r in payload['terms']['responsibilities']}=={
        'A proposed research contribution','A proposed counterparty contribution'}
    assert ui.session.submit(payload)['ok']
    assert next(iter(game.get_world()['agreements'].values()))['versions'][0]['acceptances']=={}


def test_invalid_historical_reference_preserves_the_preceding_screen():
    ui,_=app();route=ui.route;before=ui.world(),ui.current().project('log')
    with pytest.raises(ValueError):
        ui.push('inspect',matrix(ui.world())['actors'][0]['id'],at=999)
    assert ui.route is route and before==(ui.world(),ui.current().project('log'))
