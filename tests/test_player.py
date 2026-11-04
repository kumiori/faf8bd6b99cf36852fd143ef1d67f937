import pytest

from commons_engine.store import SQLiteStore
from commons_game import CommonsGame, load_scenario
from commons_game.player import ActorSession
from commons_game.scenario import definition


def test_fixed_session_cannot_accept_for_another_actor_or_silently_switch():
    game=load_scenario()
    mira=ActorSession(game,'researcher')
    atlas=ActorSession(game,'custodian')
    assert mira.submit({'kind':'propose',**definition('bilateral-logs')['proposal']})['ok']
    before=game.get_world(),game.project('log')
    forged=mira.submit({'kind':'accept','actor':'custodian','agreement_id':'agreement-main','version':1})
    assert forged['errors']==['actor_mismatch']
    assert before==(game.get_world(),game.project('log'))
    with pytest.raises(ValueError,match='hot_seat_required'):
        mira.switch('custodian')
    assert atlas.submit({'kind':'accept','agreement_id':'agreement-main','version':1})['ok']
    assert list(game.project('agreements')[0]['versions'][0]['acceptances'])==['custodian']


def test_available_actions_are_read_only_and_probe_evidence_never_escapes():
    game=load_scenario()
    session=ActorSession(game,'researcher')
    before=game.get_world(),game.project('log')
    version,actions=session.available_actions()
    assert version==1 and actions==[{'kind':'propose'}]
    assert before==(game.get_world(),game.project('log'))
    assert session.submit({'kind':'propose',**definition('bilateral-logs')['proposal']})['ok']
    _,actions=session.available_actions()
    assert any(a['kind']=='accept' for a in actions)
    assert not any(a['kind']=='authorize' for a in actions)
    assert all(set(a)<= {'kind','agreement_id','version'} for a in actions)


def test_explicit_hot_seat_and_stale_store_submission_remain_separate(tmp_path):
    game=load_scenario()
    store=SQLiteStore(tmp_path/'world.sqlite',CommonsGame)
    store.initialise(game)
    session=ActorSession(game,'researcher',store=store,hot_seat=True)
    assert session.submit({'kind':'propose',**definition('bilateral-logs')['proposal']},expected_version=1)['ok']
    session.switch('custodian')
    assert session.submit({'kind':'accept','agreement_id':'agreement-main','version':1},expected_version=1)['errors']==['stale_version']
    assert session.submit({'kind':'accept','agreement_id':'agreement-main','version':1},expected_version=2)['ok']
    assert store.load().project('agreements')[0]['versions'][0]['acceptances']['custodian']['actor_id']=='custodian'
