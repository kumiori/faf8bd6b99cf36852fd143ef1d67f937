"""Exercise complete player transitions, engine receipts, feedback and recovery."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.player import ActorSession
from commons_game.reconstruction_transitions import REGISTRY, P, BASE, state_of
from game_gamer.inspection import extract_decisions
from game_gamer.inspection.audit import audit_graph
from game_gamer.inspection.evidence import verified
from game_gamer.transitions import Choice, TraceSession
from test_matrix_navigation import app, world
from test_network_reconstruction import enter_reconstruction

CASES=[('recall','recall_connection','recollection_claim'),
       ('prior_relationship','record_prior_relationship','prior_relationship_claim'),
       ('invite','send_contact','contact_invitation'),
       ('dispute','dispute_recollection','recollection_claim'),
       ('retract','retract_relationship_claim','recollection_claim')]
SECRET='private content must stay out of UI telemetry'


def fixture(tmp_path,action,*,delivery=0):
    store=SQLiteStore(tmp_path/'world.sqlite',CommonsGame);store.initialise(world())
    ui,port=app(game=store.load(),choices=[3])
    ui.store=store;ui.session.store=store
    enter_reconstruction(ui)
    ui.handle('down',ui.build_screen())
    actor,target=ui.playing_actor,ui.route.target
    if action in {'dispute','retract'}:
        author,recipient=(target,actor) if action=='dispute' else (actor,target)
        seed=ActorSession(store.load(),author,store=store)
        assert seed.submit({'kind':'recall_connection','target_id':recipient,'context_id':'montreal-forum','key':'seed'})['ok']
        ui.refresh();ui.build_screen()
    port.choices=iter([lambda option:option.transition_id==P+'connect.'+action,delivery])
    port.answers=iter([SECRET,'','y'] if action=='invite' else ['y'])
    return ui,port,store


def assert_recovery(ui,transition_id):
    if ui.route.kind=='action_result':
        # The positive recovery is an actual rendered button, not a direct back().
        ui.route.index=1
        ui.handle('enter',ui.build_screen())
        assert state_of(ui) in BASE
        assert ui.transition_trace.records[-1]['transition_id']==P+'result.continue'
        verified(P+'result.continue','feedback','recovery','engine_consistency')
    elif ui.route.kind=='inspect':
        ui.handle('b',ui.build_screen())
        assert state_of(ui) in BASE
        assert ui.transition_trace.records[-1]['transition_id']==P+'handoff.return'
    else:
        assert state_of(ui) in BASE
    ui.build_screen()
    verified(transition_id,'recovery')


@pytest.mark.parametrize('name,kind,relation',CASES)
def test_successful_connection_transition_persists_feedback_and_replays(tmp_path,name,kind,relation):
    ui,port,store=fixture(tmp_path,name)
    before=store.load().project('log')
    ui.handle('c',ui.build_screen())
    record=next(r for r in reversed(ui.transition_trace.records) if r['transition_id']==P+'connect.'+name)
    assert record['outcome']=='committed' and not record['contract_violations']
    assert record['requested_action']==kind
    assert record['source_state']==P+'connect.menu'
    assert record['duration_ms']>=0 and record['session_id'] and record['correlation_id']
    events=store.load().project('log')
    assert len(events)==len(before)+1 and events[-1]['command']['kind']==kind
    assert record['engine_results'][0]['commit_id']==events[-1]['commit']['id']
    assert record['engine_results'][0]['mutation_count']>0
    records=[r for r in ui.world()['relationships'].values() if r['kind']==relation]
    assert records
    expected={'dispute':'disputed','retract':'retracted','invite':'sent'}.get(name,'claimed')
    assert records[-1]['status']==expected
    screen=ui.build_screen()
    if name=='invite':
        assert 'INVITATION SENT' in ui.notice
        assert any('Invite' in line or 'Invitation' in line or 'Connect' in line or 'sent' in line.lower() for line in screen.lines)
    else:
        assert screen.title in {'RECOLLECTION RECORDED','ACTION RECORDED'}
        assert any('directed claims' in line for line in screen.lines)
    loaded=store.load()
    assert loaded.get_world()==ui.world()
    assert loaded.replay().get_world()==loaded.get_world()
    for revision in range(1,loaded.revision+1):
        assert loaded.world_at(event=revision)==CommonsGame.from_log(events[:revision]).get_world()
    verified(P+'connect.'+name,'persistence','replay','engine_consistency','feedback')
    assert_recovery(ui,P+'connect.'+name)
    assert SECRET not in json.dumps(list(ui.transition_trace.records))
    assert all(not r['contract_violations'] for r in ui.transition_trace.records)


@pytest.mark.parametrize('name,kind,relation',CASES)
def test_rejected_transition_recovers_after_a_real_concurrent_commit(tmp_path,name,kind,relation):
    ui,port,store=fixture(tmp_path,name)
    original=store.load().project('log')
    original_prompt=port.prompt
    committed=[]
    def prompt(title,lines,context):
        if not committed and ('RECORD THIS CONNECTION?' in title or title.startswith('Continue?')):
            # A second client commits while the first client is confirming its
            # captured revision. No mutation of the UI's payload/engine result.
            def concurrent():
                game=store.load()
                return ActorSession(game,ui.playing_actor,store=store).submit({
                    'kind':'record_prior_relationship','target_id':ui.route.target,
                    'context_id':'concurrent-fixture','key':'concurrent'})
            with ThreadPoolExecutor(max_workers=1) as pool:
                result=pool.submit(concurrent).result()
            assert result['ok'];committed.append(result)
        return original_prompt(title,lines,context)
    port.prompt=prompt
    ui.handle('c',ui.build_screen())
    trace=next(r for r in reversed(ui.transition_trace.records) if r['transition_id']==P+'connect.'+name)
    assert committed and trace['outcome']=='rejected'
    assert trace['reasons']==['stale_version'] and not trace['contract_violations']
    assert trace['engine_results'][0]['mutation_count']==0
    assert not trace['engine_results'][0]['ok']
    after=store.load().project('log')
    assert len(after)==len(original)+1 and after[-1]['command']['key']=='concurrent'
    if name=='invite':
        assert 'stale_version' in ui.notice
    else:
        assert ui.build_screen().title=='ACTION FAILED'
        assert any('stale_version' in line for line in ui.build_screen().lines)
    verified(P+'connect.'+name,'engine_consistency','feedback')
    assert_recovery(ui,P+'connect.'+name)


@pytest.mark.parametrize('name,kind,relation',CASES)
def test_cancelled_transition_preserves_history_and_selection(tmp_path,name,kind,relation):
    ui,port,store=fixture(tmp_path,name)
    before=store.load().project('log');target=ui.route.target
    if name=='invite':
        port.answers=iter([SECRET,'','n'])
    else:
        port.answers=iter(['n'])
    ui.handle('c',ui.build_screen())
    trace=next(r for r in reversed(ui.transition_trace.records) if r['transition_id']==P+'connect.'+name)
    assert trace['outcome']=='cancelled' and not trace['engine_results']
    assert not trace['contract_violations'] and store.load().project('log')==before
    assert ui.route.target==target and state_of(ui) in BASE and 'cancelled' in ui.notice.lower()
    verified(P+'connect.'+name,'engine_consistency','feedback','recovery')


def test_invitation_draft_is_a_declared_distinct_engine_variant(tmp_path):
    ui,port,store=fixture(tmp_path,'invite',delivery=1)
    ui.handle('c',ui.build_screen())
    trace=ui.transition_trace.records[-1]
    assert trace['transition_id']==P+'connect.invite' and trace['requested_action']=='draft_contact'
    assert trace['outcome']=='committed' and not trace['contract_violations']
    invitation=next(r for r in ui.world()['relationships'].values() if r['kind']=='contact_invitation')
    assert invitation['status']=='draft'
    assert store.load().replay().get_world()==ui.world()
    assert 'Invitation saved' in ui.notice
    verified(P+'connect.invite','persistence','replay','engine_consistency','feedback')
    assert_recovery(ui,P+'connect.invite')


def test_menu_guard_cancel_and_recovery_paths_are_executed_not_inferred():
    ui,port=app(choices=[3]);enter_reconstruction(ui)
    # Self-pair is blocked before a menu or authoritative submission.
    ui.build_screen();ui.route.target=ui.playing_actor
    before=ui.current().project('log')
    ui.handle('c',ui.build_screen())
    assert ui.transition_trace.records[-1]['outcome']=='blocked'
    assert ui.transition_trace.records[-1]['reasons']==['eligible_person_pair_required']
    assert ui.current().project('log')==before
    ui.handle('down',ui.build_screen())
    port.choices=iter([lambda choice:choice.transition_id==P+'connect.cancel'])
    ui.handle('c',ui.build_screen())
    assert ui.transition_trace.records[-1]['transition_id']==P+'connect.cancel'
    assert ui.transition_trace.records[-1]['outcome']=='cancelled'
    verified(P+'connect.cancel','feedback','recovery','engine_consistency')
    # Escape from the picker is a separate observed cancellation of menu opening.
    def cancel(*args,**kwargs):
        from game_gamer.tui.screen import Cancelled
        raise Cancelled
    port.choose=cancel
    ui.handle('c',ui.build_screen())
    assert ui.transition_trace.records[-1]['transition_id']==P+'connect.open'
    assert ui.transition_trace.records[-1]['outcome']=='cancelled'
    verified(P+'connect.open','feedback','recovery','engine_consistency')
    ui.handle('b',ui.build_screen())
    assert state_of(ui)==P+'workshop'
    verified(P+'back','recovery','engine_consistency')


def test_result_view_is_a_real_recovery_to_the_network(tmp_path):
    ui,port,store=fixture(tmp_path,'recall')
    ui.handle('c',ui.build_screen());ui.route.index=0
    ui.handle('enter',ui.build_screen())
    assert state_of(ui)==P+'network'
    assert ui.transition_trace.records[-1]['transition_id']==P+'result.view'
    assert any('NETWORK' in line for line in ui.build_screen().lines)
    verified(P+'result.view','feedback','recovery','engine_consistency')


def test_filter_apply_and_cancel_roundtrip_preserves_selection_and_authority():
    ui,port=app(choices=[3]);enter_reconstruction(ui)
    ui.handle('down',ui.build_screen());selected=ui.route.target
    before=ui.current().project('log')
    for cancel in (False,True):
        prior_selection=ui.route.target
        prior_filter=ui.route.extra.get('filter')
        ui.handle('f',ui.build_screen());ui.route.index=2
        ui.handle('enter',ui.build_screen())
        facet=ui.build_screen();ui.route.index=next(i for i,(_,choice) in enumerate(facet.entries) if choice.payload=='Data stewardship')
        ui.handle('enter',facet);ui.handle('b',ui.build_screen())
        ui.route.index=7 if cancel else 5
        ui.handle('enter',ui.build_screen())
        assert state_of(ui) in BASE
        rendered=ui.build_screen()
        if cancel:
            assert ui.route.target==prior_selection and ui.route.extra.get('filter')==prior_filter
        else:
            assert len(rendered.entries)==1 and ui.route.target==rendered.entries[0][1]
        assert ui.current().project('log')==before
        id=P+('filters.cancel' if cancel else 'filters.apply')
        assert ui.transition_trace.records[-1]['transition_id']==id
        verified(id,'engine_consistency','feedback','recovery')


def test_all_registered_ids_are_wording_independent_and_the_ui_uses_them(monkeypatch):
    id=P+'connect.recall';definition=REGISTRY.transitions[id]
    monkeypatch.setattr(definition,'label','Changed displayed wording')
    ui,port=app(choices=[3,lambda choice:choice.transition_id==id],answers=['y'])
    enter_reconstruction(ui);ui.handle('down',ui.build_screen());ui.handle('c',ui.build_screen())
    assert ui.transition_trace.records[-1]['transition_id']==id
    assert ui.transition_trace.records[-1]['requested_action']=='recall_connection'
    graph=extract_decisions(scope='exercise.reconstruct')
    edge=next(e for e in graph['edges'] if e['id']==id)
    assert edge['option']=='Changed displayed wording' and edge['transition_id']==id
    audit=audit_graph(graph)
    assert audit['metrics']['unmapped_options']==0 and audit['metrics']['missing_recovery_paths']==0
    assert audit['metrics']['uninstrumented_transitions']==0


def test_illegal_action_mapping_is_blocked_before_authoritative_submission():
    ui,port=app(choices=[3,0]);enter_reconstruction(ui);ui.handle('down',ui.build_screen())
    chosen=REGISTRY.execute(P+'connect.open',ui)
    before=ui.current().project('log')
    result=REGISTRY.execute(P+'connect.recall',ui,payload={'command':{'kind':'advance_time'},'title':'unused','version':ui.current().revision})
    assert result.outcome=='blocked' and ui.current().project('log')==before
    assert not ui.transition_trace.records[-1]['contract_violations']


def test_claim_author_permission_and_exact_retry_are_preserved(tmp_path):
    ui,port,store=fixture(tmp_path,'retract')
    # Capture a real menu choice, then change the bound simulation actor. The
    # engine must reject the former author's request under the new binding.
    selection=REGISTRY.execute(P+'connect.open',ui)
    choice,revision=selection.value
    old_actor=ui.playing_actor;other=ui.route.target
    ui.assume_actor(ui.world()['actors'][other])
    before=store.load().project('log')
    denied=REGISTRY.execute(P+'connect.retract',ui,payload={'command':choice.payload,'title':choice.label,'version':revision})
    assert denied.outcome=='rejected' and denied.reasons==('claim_author_required',)
    assert store.load().project('log')==before
    assert ui.build_screen().title=='ACTION FAILED'
    verified(P+'connect.retract','engine_consistency','feedback')
    assert_recovery(ui,P+'connect.retract')
    # Retry one already accepted claim request with the exact same command key.
    ui.assume_actor(ui.world()['actors'][old_actor]);ui.route.target=other
    port.choices=iter([lambda c:c.transition_id==P+'connect.prior_relationship'])
    port.answers=iter(['y','y'])
    selection=REGISTRY.execute(P+'connect.open',ui);choice,revision=selection.value
    command={**choice.payload,'key':'stable-client-request'}
    submitted=REGISTRY.execute(choice.transition_id,ui,payload={'command':command,'title':choice.label,'version':revision})
    assert submitted.outcome=='committed'
    accepted=store.load().project('log')
    ui.handle('b',ui.build_screen())
    # This is a retry of an in-flight request, not a newly offered menu branch.
    ui._reconstruction_modal=P+'connect.menu'
    retried=REGISTRY.execute(choice.transition_id,ui,payload={'command':command,'title':choice.label,'version':revision})
    assert retried.outcome=='idempotent'
    assert retried.value['commit_id']==submitted.value['commit_id']
    assert store.load().project('log')==accepted
    assert not ui.transition_trace.records[-1]['contract_violations']
    verified(P+'connect.prior_relationship','idempotency','engine_consistency')


@pytest.mark.parametrize('keys,expected',[
    (['enter'],P+'profile'),(['n'],P+'network'),(['G','G'],P+'directory'),
    (['L','enter','b'],P+'directory'),(['d','pagedown','b'],P+'directory'),
    (['tab','backtab'],P+'directory'),(['v',']','['],P+'directory')])
def test_navigation_families_roundtrip_without_authoritative_changes(keys,expected):
    ui,port=app(choices=[3]);enter_reconstruction(ui)
    before=ui.current().project('log')
    for key in keys:
        ui.handle(key,ui.build_screen())
    assert state_of(ui)==expected and ui.current().project('log')==before
    assert all(not record['contract_violations'] for record in ui.transition_trace.records)


@pytest.mark.parametrize('after_commit',[False,True])
def test_shared_exception_recovery_preserves_the_authoritative_commit_boundary(tmp_path,monkeypatch,after_commit):
    ui,port,store=fixture(tmp_path,'recall')
    original=ui.push
    before=store.load().project('log')
    if after_commit:
        def unavailable(kind,*args,**kwargs):
            if kind=='action_result':raise ValueError('injected renderer route failure')
            return original(kind,*args,**kwargs)
        monkeypatch.setattr(ui,'push',unavailable)
    else:
        def broken_confirm(*args,**kwargs):raise ValueError('injected input failure')
        monkeypatch.setattr(ui,'confirm',broken_confirm)
    ui.handle('c',ui.build_screen())
    trace=ui.transition_trace.records[-1]
    assert trace['transition_id']==P+'connect.recall' and trace['outcome']=='error'
    assert not trace['contract_violations'] and state_of(ui) in BASE
    assert ui._reconstruction_modal is None and 'previous view' in ui.notice
    after=store.load().project('log')
    assert len(after)==len(before)+(1 if after_commit else 0)
    if after_commit:
        assert trace['engine_results'][0]['ok']
        assert after[-1]['commit']['id']==trace['engine_results'][0]['commit_id']
        assert store.load().replay().get_world()==ui.world()
    else:
        assert not trace['engine_results'] and before==after
    verified(P+'connect.recall','error_recovery','engine_consistency','feedback','recovery')


def test_keyboard_interrupt_has_an_observed_exit_without_a_partial_submission(tmp_path,monkeypatch):
    ui,port,store=fixture(tmp_path,'recall')
    before=store.load().project('log')
    def interrupt(*args,**kwargs):raise KeyboardInterrupt
    monkeypatch.setattr(ui,'confirm',interrupt)
    ui.handle('c',ui.build_screen())
    record=ui.transition_trace.records[-1]
    assert record['outcome']=='aborted' and record['destination_state']==P+'quit'
    assert ui.finished and not record['contract_violations']
    assert store.load().project('log')==before
    verified(P+'connect.recall','interruption_recovery','engine_consistency')


def test_retry_classification_uses_the_receipt_when_another_client_advances_history(tmp_path):
    ui,port,store=fixture(tmp_path,'prior_relationship')
    selected=REGISTRY.execute(P+'connect.open',ui);choice,revision=selected.value
    command={**choice.payload,'key':'retry-with-concurrent-client'}
    first=REGISTRY.execute(choice.transition_id,ui,payload={'command':command,'title':choice.label,'version':revision})
    assert first.outcome=='committed'
    ui.handle('b',ui.build_screen())
    ui._reconstruction_modal=P+'connect.menu'
    def confirm(*_):
        def external():
            return ActorSession(store.load(),ui.playing_actor,store=store).submit({
                'kind':'record_prior_relationship','target_id':ui.route.target,
                'context_id':'retry-concurrent-client','key':'other-client'})
        with ThreadPoolExecutor(max_workers=1) as pool:assert pool.submit(external).result()['ok']
        return True
    ui.confirm=confirm
    retried=REGISTRY.execute(choice.transition_id,ui,payload={'command':command,'title':choice.label,'version':revision})
    assert retried.outcome=='idempotent', 'A different client advancing history is not a new commit by this retry'
    assert retried.value['commit_id']==first.value['commit_id']
    events=store.load().project('log')
    assert events[-1]['command']['key']=='other-client'
    assert sum(e.get('command',{}).get('key')=='retry-with-concurrent-client' for e in events if e.get('command'))==1
    assert not ui.transition_trace.records[-1]['contract_violations']
    assert_recovery(ui,P+'connect.prior_relationship')
    verified(P+'connect.prior_relationship','idempotency','engine_consistency')


def test_mode_handoffs_resume_the_actual_remembered_route_without_false_destinations():
    ui,port=app(choices=[3])
    ui.handle('g',ui.build_screen());ui.handle('i',ui.build_screen())
    ui.handle('e',ui.build_screen())
    enter_reconstruction(ui)
    before=ui.current().project('log')
    ui.handle('e',ui.build_screen())
    assert state_of(ui) in BASE
    assert ui.transition_trace.records[-1]['transition_id']==P+'handoff.modes'
    assert not ui.transition_trace.records[-1]['contract_violations']
    ui.handle('g',ui.build_screen())
    assert ui.route.kind=='inbox' and state_of(ui)=='host.inbox'
    assert not ui.transition_trace.records[-1]['contract_violations']
    assert ui.current().project('log')==before


def test_shared_nested_inspection_is_outside_the_return_bridge_until_the_parent_matches(tmp_path):
    ui,port,store=fixture(tmp_path,'invite')
    ui.handle('c',ui.build_screen())
    invitation=ui.route.target
    ui.push('inspect',ui.playing_actor)
    count=len(ui.transition_trace.records)
    ui.handle('b',ui.build_screen())
    assert ui.route.target==invitation and len(ui.transition_trace.records)==count
    ui.handle('b',ui.build_screen())
    assert state_of(ui) in BASE
    assert ui.transition_trace.records[-1]['transition_id']==P+'handoff.return'
    assert not ui.transition_trace.records[-1]['contract_violations']
