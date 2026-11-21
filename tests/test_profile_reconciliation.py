from copy import deepcopy
from itertools import count

import pytest

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.curator_access import provision_curator
from commons_game.ecosystem_import import SCHEMA, import_snapshot, source_id
from commons_game.montreal_sources import LAYER, import_montreal_network
from commons_game.profile_claims import issue, verify
from commons_game.profile_sync import NotionFailure, NotionProfiles, sync_one
from game_gamer.runtime.curation import profile
from game_gamer.runtime.curation_requests import records

from test_matrix_navigation import app, world
from test_montreal_network import source_files

SOURCE = 'b16fd7e9-5cd6-4dc0-9d73-d1c403897d00'
PAGE = 'f27b5a19-2329-4cbd-b7c0-a57d2cb17022'


@pytest.fixture
def setup(tmp_path):
    game = world()
    before = game.get_world()
    after = deepcopy(before)
    actors = {actor['label']: actor['id'] for actor in before['actors'].values()}
    alex, casey = (actors[label] for label in ('Alex Example', 'Casey Example'))
    after['actors'][casey]['provenance'].update(record_id=PAGE, data_source_id=SOURCE)
    game._commit(before, after, 'fixture.remote_profile')
    provision_curator(game, 'Alex', enabled=True, reference='Fixture operator')
    sources = source_files(tmp_path, include_isolate=True)
    assert import_montreal_network(game, sources)['ok']
    ids = {names[0]: key for key, names in sources['names'].items()}
    store = SQLiteStore(tmp_path/'world.sqlite', CommonsGame)
    store.initialise(game)
    return store, alex, casey, ids


def commands(store):
    sequence = count(1)

    def submit(actor, kind, **payload):
        return store.submit({'key': f'review-{next(sequence)}', 'kind': kind, 'actor': actor, **payload})
    return submit


def test_curator_decisions_preserve_source_and_project_canonical_ids(setup):
    store, alex, casey, ids = setup
    submit = commands(store)
    before = store.load().get_world()['configuration'][LAYER]
    assert all(row['actor_id'] is None for row in before['identities'].values())

    def reconcile(actor, name, decision, **extra):
        return submit(actor, 'reconcile_source_identity', source_id=ids[name], decision=decision,
                      reference='Reviewed against authorised roster', **extra)

    assert reconcile(casey, 'Casey Example', 'match', target_id=casey)['errors'] == ['curator_required']
    assert reconcile(alex, 'Casey Example', 'create')['errors'] == ['possible_duplicate_profile']
    assert reconcile(alex, 'Casey Example', 'match', target_id=casey)['ok']
    assert reconcile(alex, 'Alex Example', 'match', target_id=casey)['errors'] == ['source_actor_already_bound']
    assert reconcile(alex, 'Morgan Example', 'defer')['ok']
    assert reconcile(alex, 'Morgan Example', 'reject')['ok']
    assert reconcile(alex, 'Morgan Example', 'match', target_id=alex)['errors'] == ['source_review_is_final']
    game = store.load()
    dataset = game.get_world()['configuration'][LAYER]
    assert dataset['connections'] == before['connections'] and dataset['statements'] == before['statements']
    assert dataset['identities'][ids['Morgan Example']]['history'][0]['decision'] == 'defer'
    graph = game.project('network')
    assert any(edge['target_id'] == casey and edge['layer'] == LAYER for edge in graph['edges'])
    assert ids['Morgan Example'] not in {node['id'] for node in graph['nodes']}
    assert game.get_world() == game.replay().get_world()


def test_source_review_is_an_interactive_queue(setup):
    store, alex, _, ids = setup
    ui, _ = app(store.load(), choices=[4], answers=['Keep original source available', 'y'])
    ui.assume_actor(ui.world()['actors'][alex])
    ui.choose_mode()
    ui.handle('U', ui.build_screen())
    queue = ui.build_screen()
    assert len(queue.entries) == 4 and not any(line.startswith('{') for line in queue.lines)
    ui.route.index = next(i for i, (_, key) in enumerate(queue.entries) if key == ids['Zoë Source'])
    ui.handle('enter', queue)
    detail = ui.build_screen()
    assert [key for _, key in detail.entries] == ['match', 'create', 'defer', 'reject']
    ui.route.index = 2
    ui.handle('enter', detail)
    assert ui.world()['configuration'][LAYER]['identities'][ids['Zoë Source']]['review_status'] == 'deferred'


class NotionFixture(NotionProfiles):
    def __init__(self):
        super().__init__('fixture-token', {'data_source_id': SOURCE, 'actor_id_property': 'Commons Actor ID',
                         'properties': {'label': {'name': 'Name', 'type': 'title'}}})
        self.remote = {'Name': {'type': 'title', **self.encode('title', 'Casey Example')}}
        self.created = None
        self.patches = self.posts = 0
        self.fail_update_after_write = self.fail_create_after_write = False

    def response(self, properties):
        return {'object': 'page', 'id': PAGE, 'parent': {'type': 'data_source_id', 'data_source_id': SOURCE},
                'properties': deepcopy(properties)}

    def request(self, method, endpoint, payload=None):
        if endpoint.endswith('/query'):
            return {'results': [self.response(self.created)] if self.created and
                    payload['filter']['property'] == self.marker else []}
        if method == 'POST':
            assert endpoint == 'pages'
            self.posts += 1
            self.created = {name: {'type': next(iter(value)), **value} for name, value in payload['properties'].items()}
            if self.fail_create_after_write:
                raise NotionFailure('notion_transport_failure')
            return self.response(self.created)
        if method == 'PATCH':
            self.patches += 1
            self.remote.update({name: {'type': next(iter(value)), **value} for name, value in payload['properties'].items()})
            if self.fail_update_after_write:
                raise NotionFailure('notion_transport_failure')
        return self.response(self.remote)


def test_approved_correction_sync_retries_without_resending_a_completed_patch(setup):
    store, alex, casey, _ = setup
    submit = commands(store)
    assert submit(alex, 'correct_profile', target_id=casey, reference='Bypass',
                  changes={'label': 'Renamed'})['errors'] == ['profile_review_required']
    assert submit(casey, 'request_curation', target_id=casey, request_type='correction',
                  reason='Correct spelling', proposed_changes={'label': 'Casey Corrected'})['ok']
    ident = next(iter(records(store.load().get_world())))
    assert submit(alex, 'review_curation_request', request_id=ident, decision='approve', reason='Evidence reviewed')['ok']
    assert profile(store.load().get_world(), casey)['label'] == 'Casey Example'
    client = NotionFixture()
    client.remote['Name']['title'] = client.encode('title', 'Externally edited')['title']
    assert sync_one(store, ident, client)['error'] == 'notion_profile_conflict' and client.patches == 0
    client.remote['Name']['title'] = client.encode('title', 'Casey Example')['title']
    client.fail_update_after_write = True
    assert sync_one(store, ident, client)['status'] == 'pending'
    assert profile(store.load().get_world(), casey)['label'] == 'Casey Example'
    assert sync_one(store, ident, client)['status'] == 'synced'
    assert client.patches == 1
    game = store.load()
    world = game.get_world()
    assert profile(world, casey)['label'] == 'Casey Corrected'
    assert world['actors'][casey]['label'] == 'Casey Example'
    audit = world['configuration']['curation']['profiles'][casey]
    assert audit['actor_id'] == alex and audit['previous'] == {'label': 'Casey Example'}
    assert game.replay().get_world() == world


def test_provisional_creation_and_claim_recover_without_duplicate_post(setup):
    store, alex, casey, ids = setup
    submit = commands(store)
    assert submit(alex, 'reconcile_source_identity', source_id=ids['Zoë Source'], decision='create',
                  reference='Source validated')['ok']
    game = store.load()
    target = game.get_world()['configuration'][LAYER]['identities'][ids['Zoë Source']]['actor_id']
    assert game.get_world()['actors'][target]['status'] == 'provisional'
    assert submit(target, 'request_curation', target_id=target, request_type='profile_review',
                           reason='Attempt to play')['errors'] == ['inactive_actor']
    client = NotionFixture()
    # Distinguish the newly created remote identity from the fixture's existing page.
    old_response = client.response
    client.response = lambda props: {**old_response(props), 'id': '28b8ea80-7562-4d18-8646-5453b0111199'}
    client.fail_create_after_write = True
    assert sync_one(store, target, client)['status'] == 'pending'
    assert sync_one(store, target, client)['status'] == 'synced' and client.posts == 1
    record_id = '28b8ea80-7562-4d18-8646-5453b0111199'
    captured_id = source_id('person', SOURCE, record_id)
    snapshot = {'schema_version': SCHEMA, 'captured_at': '2026-11-10T00:00:00+00:00', 'records': [
        {'kind': 'person', 'record_id': record_id, 'data_source_id': SOURCE, 'fields': {'label': 'Zoë Source'}},
        {'kind': 'capacity', 'record_id': 'related-capacity', 'data_source_id': SOURCE,
         'fields': {'actor_id': captured_id, 'domain': 'Stewardship', 'quantity': 1, 'unit': 'hour'}},
    ]}
    report = store.transact(lambda game: import_snapshot(game, snapshot))
    assert not report['rejected']
    captured = store.load().get_world()
    assert captured_id not in captured['actors'] and captured['actors'][target]['status'] == 'provisional'
    assert any(item['actor_id'] == target for item in captured['capacities'].values())
    invitation = store.transact(lambda game: issue(game, target, curator=alex, provider='institution',
                                                   subject='subject-007', reference='Verified channel'))
    token = invitation['token']
    with pytest.raises(ValueError, match='profile_claim_identity_mismatch'):
        store.transact(lambda game: verify(game, token, curator=alex, provider='institution',
                                           subject='different-subject', reference='Verification'))
    assert store.transact(lambda game: verify(game, token, curator=alex, provider='institution',
                                             subject='subject-007', reference='Institution verified subject'))['ok']
    with pytest.raises(ValueError, match='profile_claim_unavailable'):
        store.transact(lambda game: verify(game, token, curator=alex, provider='institution',
                                           subject='subject-007', reference='Repeated verification'))
    game = store.load()
    assert token not in str(game.project('log'))
    assert game.get_world()['actors'][target]['status'] == 'active'
    assert game.replay().get_world() == game.get_world()


def test_rejected_notion_post_can_retry_but_unconfirmed_post_stays_reserved(setup):
    store, alex, _, ids = setup
    assert commands(store)(alex, 'reconcile_source_identity', source_id=ids['Zoë Source'], decision='create',
                           reference='Source validated')['ok']
    target = store.load().get_world()['configuration'][LAYER]['identities'][ids['Zoë Source']]['actor_id']
    client = NotionFixture()
    post_errors = iter(('notion_http_403', 'notion_transport_failure'))
    request = client.request

    def failing_post(method, endpoint, payload=None):
        if method == 'POST' and endpoint == 'pages':
            client.posts += 1
            raise NotionFailure(next(post_errors))
        return request(method, endpoint, payload)

    client.request = failing_post
    assert sync_one(store, target, client)['error'] == 'notion_http_403'
    assert sync_one(store, target, client)['error'] == 'notion_transport_failure'
    assert sync_one(store, target, client)['error'] == 'notion_create_unconfirmed'
    assert client.posts == 2
