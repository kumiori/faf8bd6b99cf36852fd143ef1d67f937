"""Scenarios V1 through the same actor and saved-world boundaries as other play."""

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame, load_scenario
from commons_game.curator_access import provision_curator
from commons_game.ecosystem_import import import_snapshot, source_id
from commons_game.fullscreen import FullScreenTerminal
from commons_game.missions import install_missions
from commons_game.player import ActorSession
from game_gamer.projections.history import HistoryFilters, history_rows
from game_gamer.projections.missions import project_mission
from game_gamer.runtime.missions import CATALOGUE_ID, definitions
from test_matrix_navigation import FakeViewport, synthetic_snapshot, world


def _open(app, target):
    screen = app.build_screen()
    app.route.index = next(i for i, (_, value) in enumerate(screen.entries) if value == target)
    app.handle('enter', screen)


def test_pack_preserves_the_six_source_cards_and_distinguishes_catalogue_ids(tmp_path):
    store = SQLiteStore(tmp_path / 'legacy.sqlite', CommonsGame)
    old = load_scenario('montreal-commons')
    store.initialise(old)
    assert store.transact(install_missions)['changed']
    assert not store.transact(install_missions)['changed']
    game = store.load()
    assert game.project('log')[:-1] == old.project('log')
    assert game.world_at(event=old.revision) == old.get_world()
    assert game.project('missions', at=old.revision) == []
    state = game.get_world()
    pack = state['configuration'][CATALOGUE_ID]
    assert {kind: len(cards) for kind, cards in pack['catalogues'].items()} == {
        'actor': 13, 'means': 30, 'finality': 4, 'result': 8,
    }
    assert not pack['workshop_selections']
    assert set(definitions(state)) == {'S02', 'S03', 'S04', 'S05', 'S08', 'S09'}
    assert all(not mission['players'] and not mission['routes'] for mission in game.project('missions'))
    assert pack['scenario_cards']['S08']['principal_means'] == [
        {'id': 'M25', 'title': 'Preuve de valeur et et émergence d’un marché lisible'},
    ]
    assert pack['catalogues']['means']['M25']['title'] == 'Indicateurs d’impact mutualisés'


def test_fullscreen_mission_play_from_join_to_shared_verified_history(tmp_path):
    game = world()
    store = SQLiteStore(tmp_path / 'montreal.sqlite', CommonsGame)
    store.initialise(game)
    viewport = FakeViewport()
    app = FullScreenTerminal(game, viewport=viewport, store=store, plain=True)
    actors = game.get_world()['actors']
    player, partner = [actor for actor in actors.values() if actor['kind'] == 'person'
                       and actor['provenance']['kind'] == 'notion_snapshot'][:2]
    app.assume_actor(player)
    app.handle('s', app.build_screen())
    assert store.load().project('log')[-1]['kind'] == 'missions.installed'
    for mission_id in ('S02', 'S03', 'S04', 'S05', 'S08', 'S09'):
        _open(app, ('mission', mission_id))
        for section in ('why', 'where', 'who', 'how', 'requirements'):
            _open(app, section)
            assert app.build_screen().lines
            app.back()
        app.back()

    _open(app, ('mission', 'S02'))
    _open(app, 'moves')
    viewport.answers = iter(['y', 'Convene access-rule workshop', 'y', 'Run a sandbox test', 'y',
                             'Discuss how to repeat the test', 'y'])
    viewport.choices = iter([0, 3, 3, 1])
    _open(app, 'mission_join')
    _open(app, 'mission_propose')
    _open(app, 'mission_propose')
    _open(app, 'mission_propose')
    assert app.notice == 'Move recorded in the shared world.'
    _open(app, 'mission_explore')
    assert any('Convene access-rule workshop' in line for line in app.build_screen().lines)
    app.back()

    viewport.answers = iter(['Rules need a narrower trial', 'y', 'Trial in a local sandbox', 'y'])
    viewport.choices = iter([2])
    before = definitions(app.world())['S02']
    _open(app, 'mission_challenge')
    assert definitions(app.world())['S02'] == before

    viewport.answers = iter(['Document test decisions', 'y'])
    viewport.choices = iter([1, lambda ident: ident == partner['id'], 1])
    _open(app, 'mission_commit')
    assert not project_mission(app.world(), 'S03')['shared_commitments']
    app.assume_actor(partner)
    viewport.answers = iter(['y'])
    _open(app, 'mission_accept')
    shared = project_mission(app.world(), 'S03')
    assert shared['shared_commitments'][0]['status'] == 'accepted'
    assert not shared['requirements'][0]['evidence_ids']

    app.assume_actor(actors['simulation-verifier'])
    viewport.answers = iter(['Sandbox access report 001', 'y'])
    _open(app, 'mission_verify')
    app.typed_command('scenarios S03')
    _open(app, 'requirements')
    assert app.build_screen().lines[0].endswith('Verified')
    app.handle('H', app.build_screen())
    viewport.choices = iter([3, lambda ident: ident == 'S03'])
    app.handle('f', app.build_screen())
    assert app.route.extra['history_filters'] == HistoryFilters(mission_id='S03')
    history = app.build_screen()
    assert any('accepted a mission offer' in line for line, _ in history.entries)
    assert any('verified a mission outcome' in line for line, _ in history.entries)
    assert all('challenged a mission definition' not in line for line, _ in history.entries)
    reloaded = store.load()
    assert reloaded.replay().get_world() == reloaded.get_world()
    first, second = project_mission(reloaded.get_world(), 'S02')['routes'][0]['steps']
    assert first['status'] == 'verified' and second['status'] == 'proposed'
    assert second['after_step_id'] == first['id']
    assert len(reloaded.get_world()['evidence']) == len(game.get_world()['evidence']) + 1


def test_revision_checks_permissions_stale_definitions_and_idempotent_retries(tmp_path):
    game = world()
    install_missions(game)
    editor, reviewer, other = [actor['id'] for actor in game.get_world()['actors'].values()
                               if actor['kind'] == 'person' and actor['provenance']['kind'] == 'notion_snapshot']
    provision_curator(game, editor, enabled=True, reference='Simulation test')
    provision_curator(game, reviewer, enabled=True, reference='Simulation test')
    store = SQLiteStore(tmp_path / 'world.sqlite', CommonsGame)
    store.initialise(game)
    editor, reviewer, other = (ActorSession(game, actor, store=store) for actor in (editor, reviewer, other))
    base = {'mission_id': 'S09'}
    command = {'key': 'join-once', 'kind': 'mission_join', **base}
    version = store.revision()
    assert editor.submit(command, expected_version=version) == editor.submit(command, expected_version=version)
    assert editor.submit({**command, 'mission_id': 'S04'})['errors'] == ['key_conflict']
    assert other.submit({'kind': 'mission_propose', **base, 'proposal_type': 'initiative',
                         'description': 'Run a session'})['errors'] == ['join_mission_first']

    challenges = []
    for replacement in ('First proposed target', 'Second proposed target'):
        result = editor.submit({'kind': 'mission_challenge', **base, 'field': 'target',
                                'reason': 'Clarify the scope', 'replacement': replacement})
        assert result['ok']
        challenges.append(next(ident for ident in result['affected_entities'] if ident.startswith('mission_contribution_')))
    review = {'kind': 'mission_revise', **base, 'contribution_id': challenges[0]}
    before = store.load().get_world()
    assert editor.submit(review)['errors'] == ['independent_mission_curator_required']
    assert other.submit(review)['errors'] == ['independent_mission_curator_required']
    assert store.load().get_world() == before
    assert reviewer.submit(review, expected_version=version)['errors'] == ['stale_version']
    assert reviewer.submit(review)['ok']
    assert reviewer.submit({**review, 'contribution_id': challenges[1]})['errors'] == ['mission_version_conflict']
    current = store.load()
    active = definitions(current.get_world())['S09']
    assert active['version'] == 2 and active['target'] == 'First proposed target'
    assert current.get_world()['configuration'][CATALOGUE_ID] == before['configuration'][CATALOGUE_ID]
    assert definitions(current.world_at(event=current.revision - 1))['S09'] == definitions(before)['S09']
    assert history_rows(current.project('log'), HistoryFilters(mission_id='S09'))[-1]['action'] == 'mission_revise'


def test_resource_offers_require_control_and_acceptance_without_allocating_inventory():
    game = load_scenario('montreal-commons')
    install_missions(game)
    snapshot = synthetic_snapshot()
    people = [source_id('person', row['data_source_id'], row['record_id'])
              for row in snapshot['records'] if row['kind'] == 'person']
    owner, partner, other = people
    resource = source_id('resource', 'fixture-resources', 'room')
    snapshot['records'].append({'kind': 'resource', 'data_source_id': 'fixture-resources',
                                'record_id': 'room', 'fields': {'owner_id': owner, 'label': 'Workshop room',
                                                                'quantity': 2, 'unit': 'hour'}})
    assert not import_snapshot(game, snapshot)['rejected']
    owner, partner, other = (ActorSession(game, actor) for actor in people)
    verifier = ActorSession(game, 'simulation-verifier')
    mission = {'mission_id': 'S09'}
    for player in (owner, other):
        assert player.submit({'kind': 'mission_join', **mission})['ok']
    baseline = game.get_world()
    offer = {'kind': 'mission_commit', **mission, 'requirement_id': 'mentoring-network',
             'description': 'Offer space for practice', 'resource_id': resource, 'quantity': 1}
    assert owner.submit(offer)['errors'] == ['mission_resource_recipient_required']
    offer['recipient_id'] = partner.actor
    assert other.submit(offer)['errors'] == ['mission_resource_owner_required']
    assert owner.submit({**offer, 'quantity': 3})['errors'] == ['invalid_quantity']
    assert game.get_world() == baseline

    result = owner.submit(offer)
    assert result['ok']
    ident = next(ident for ident in result['affected_entities'] if ident.startswith('mission_contribution_'))
    target = {**mission, 'contribution_id': ident}
    verify = {'kind': 'mission_verify', **target, 'reference': 'Mentoring session report'}
    assert verifier.submit(verify)['errors'] == ['reviewable_mission_offer_required']
    assert other.submit({'kind': 'mission_accept', **target})['errors'] == ['mission_recipient_required']
    assert partner.submit({'kind': 'mission_accept', **target})['ok']
    assert partner.submit(verify)['errors'] == ['independent_mission_verifier_required']
    state = game.get_world()
    assert state['resources'] == baseline['resources']
    assert state['reservations'] == baseline['reservations']
