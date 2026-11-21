from copy import deepcopy
from dataclasses import replace

import pytest

from game_gamer import ActionSubmission, Collective, SimulationBinding
from test_extensions import lantern


def submit(game, actor, kind, **payload):
    action = ActionSubmission(action_id=f'{kind}-{game.revision}', actor_id=actor, scope_id=game.scope_id,
                              expected_revision=game.revision, action_type=kind,
                              target_id=payload.get('mission_id'), payload=payload)
    return game.submit(action, binding=SimulationBinding(actor_id=actor, scope_id=game.scope_id))


def world():
    definition = lantern.definition()
    definition['actors'][0]['roles'].append('curator')
    definition['actors'].append({'id': 'pat', 'label': 'Pat', 'roles': ['verifier']})
    return definition


def mission():
    return {'mission_id': 'reading', 'title': 'Open reading room', 'rationale': 'Neighbours need a reading space',
            'target': 'A documented public reading', 'criteria': {'reading-confirmed': 'Reading independently observed'},
            'governance': {'adopters': ['lee', 'kim'], 'verifiers': ['pat'], 'operators': ['lee']}}


def test_world_can_act_then_propose_contest_adopt_verify_complete_and_reopen(tmp_path):
    game = Collective.start(world(), extension=lantern.EXTENSION, path=tmp_path/'world.sqlite')
    assert game.project('missions') == []
    assert game.submit(lantern.visit(game), binding=SimulationBinding(actor_id='lee', scope_id=game.scope_id))['ok']
    assert submit(game, 'lee', 'mission_create', **mission())['ok']
    proposed = game.project('missions')[0]
    assert proposed['status'] == 'proposed' and not proposed['complete']
    assert submit(game, 'lee', 'mission_adopt', mission_id='reading', version=1)['ok']
    assert submit(game, 'lee', 'mission_join', mission_id='reading')['errors'] == ['adopt_mission_first']
    assert submit(game, 'kim', 'mission_challenge', mission_id='reading', field='rationale',
                  reason='Narrow the purpose', replacement='Trial a small neighbourhood reading')['ok']
    challenge = game.project('missions')[0]['contributions'][-1]
    assert game.project('missions')[0]['rationale'] == proposed['rationale']
    assert submit(game, 'lee', 'mission_revise', mission_id='reading', contribution_id=challenge['id'])['ok']
    revised = game.project('missions')[0]
    assert revised['version'] == 2 and revised['status'] == 'proposed' and revised['acceptances'] == {}
    assert revised['versions'][0] == proposed['versions'][0]
    assert submit(game, 'kim', 'mission_adopt', mission_id='reading', version=1)['errors'] == ['mission_version_conflict']
    for actor in ('lee', 'kim'):
        assert submit(game, actor, 'mission_adopt', mission_id='reading', version=2)['ok']
    branch_point = game.revision
    assert submit(game, 'lee', 'mission_join', mission_id='reading')['ok']
    assert submit(game, 'lee', 'mission_commit', mission_id='reading', requirement_id='reading-confirmed',
                  description='Host a reading', recipient_id='kim')['ok']
    contribution = game.project('missions')[0]['contributions'][-1]['id']
    assert submit(game, 'lee', 'mission_accept', mission_id='reading', contribution_id=contribution)['errors'] == ['mission_recipient_required']
    assert submit(game, 'kim', 'mission_accept', mission_id='reading', contribution_id=contribution)['ok']
    assert not game.project('missions')[0]['criteria_satisfied']
    assert submit(game, 'pat', 'mission_verify_outcome', mission_id='reading', version=2,
                  reference='Too early')['errors'] == ['mission_criteria_unverified']
    assert submit(game, 'pat', 'mission_verify', mission_id='reading', contribution_id=contribution,
                  reference='Observed the reading')['ok']
    assert game.project('missions')[0]['criteria_satisfied'] and not game.project('missions')[0]['complete']
    assert submit(game, 'lee', 'mission_verify_outcome', mission_id='reading', version=2,
                  reference='My own report')['errors'] == ['independent_mission_verifier_required']
    assert submit(game, 'pat', 'mission_verify_outcome', mission_id='reading', version=2,
                  reference='All completion criteria checked')['ok']
    assert submit(game, 'lee', 'mission_complete', mission_id='reading', version=2)['ok']
    assert game.project('missions')[0]['complete']
    complete = game.history()
    branch = game.fork(at=branch_point, branch_id='abandon')
    assert submit(branch, 'lee', 'mission_abandon', mission_id='reading', version=2, reason='Different plan')['ok']
    assert branch.project('missions')[0]['status'] == 'abandoned'
    assert game.history() == complete
    assert submit(game, 'lee', 'mission_reopen', mission_id='reading', version=2, reason='Run another iteration')['ok']
    assert game.project('missions')[0]['status'] == 'proposed' and game.project('missions')[0]['version'] == 3
    assert Collective.from_history(game.history(), extension=lantern.EXTENSION).project() == game.project()
    assert Collective.from_history(branch.history(), extension=lantern.EXTENSION).project() == branch.project()
    assert Collective.open(tmp_path/'world.sqlite', scope_id=game.scope_id, extension=lantern.EXTENSION).project() == game.project()


def test_target_lock_is_a_configuration_of_the_same_world_engine():
    definition = world()
    seed = mission()
    seed['id'] = seed.pop('mission_id')
    seed['proposed_by'] = 'lee'
    definition['missions'] = [seed]
    definition['gameplay'] = {'mode': 'target_locked', 'mission_id': 'reading',
                              'allowed_actions': ['record_visit', 'mission_adopt', 'mission_explore',
                                                  'mission_abandon', 'mission_reopen']}
    game = Collective.start(definition, extension=lantern.EXTENSION)
    assert submit(game, 'lee', 'mission_create', **{**mission(), 'mission_id': 'other'})['errors'] == ['target_locked_action']
    assert submit(game, 'lee', 'mission_explore', mission_id='other')['errors'] == ['target_locked_mission']
    assert game.submit(lantern.visit(game), binding=SimulationBinding(actor_id='lee', scope_id=game.scope_id))['ok']
    assert submit(game, 'lee', 'mission_abandon', mission_id='reading', version=1, reason='Pause this game')['ok']
    assert game.submit(lantern.visit(game, key='closed'), binding=SimulationBinding(actor_id='lee', scope_id=game.scope_id))['errors'] == ['target_locked_game_closed']
    assert submit(game, 'lee', 'mission_reopen', mission_id='reading', version=1, reason='Resume')['ok']
    assert Collective.from_history(game.history(), extension=lantern.EXTENSION).project() == game.project()


@pytest.mark.parametrize('ident', ['mission-catalogues', 'curation', 'game-gamer:gameplay',
                                   'mission_contribution_000004', 'evidence_000005'])
def test_mission_names_cannot_replace_runtime_configuration_or_generated_records(ident):
    game = Collective.start(world())
    before = game.history()
    result = submit(game, 'lee', 'mission_create', **{**mission(), 'mission_id': ident})
    assert result['errors'] == ['reserved_mission_id']
    assert game.history() == before
