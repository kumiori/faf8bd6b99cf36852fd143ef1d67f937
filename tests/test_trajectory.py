from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip('trajectory_engine', reason='Install the trajectory extra for package integration tests')

from commons_game import load_scenario
from commons_game.engine import digest
from commons_game.model import DomainError
from commons_game.scenario import run_demo, demo_commands
from commons_game.trajectory import (LOCK, SCHEMA, frames, load_trajectory_yaml,
                                     package_api, project_trajectory, reconstruct,
                                     simulate_branch, trajectory_yaml)


def alternatives(game):
    return [simulate_branch(game, parent_sequence=3, branch_id=kind, commands=[{
        'key':'alternative-'+kind, 'actor':'custodian', 'kind':kind,
        'agreement_id':'agreement-main', 'version':2,
        **({'reason':'Hypothetical rejection of the terms.'} if kind=='reject' else {})
    }]) for kind in ('accept','reject')]


def test_real_pinned_package_represents_sequence_without_artificial_coordinates():
    api = package_api()
    assert api.__version__ == LOCK['version'] == '0.2.0'
    game = run_demo()
    before = game.get_world(), game.project('log')
    document = project_trajectory(game)
    assert document['schema_version'] == api.SCHEMA_VERSION
    assert document['primitives'] == document['uncertainty'] == document['planning_objects'] == []
    envelope = document['plan']['commons_trajectory']
    assert envelope['schema_version'] == SCHEMA
    assert envelope['events'] == game.project('log')
    assert envelope['access'] == 'read_only_projection'
    assert before == (game.get_world(), game.project('log'))
    assert reconstruct(document).get_world() == game.get_world()
    assert project_trajectory(game) == document


def test_native_serialization_preserves_ids_order_provenance_and_all_mutations():
    game = run_demo()
    document = project_trajectory(game, branches=alternatives(game))
    encoded = trajectory_yaml(document)
    # The actual package, not a Commons YAML reimplementation, reads this format.
    native = package_api().load_trajectory_yaml(encoded)
    decoded = load_trajectory_yaml(encoded)
    assert native['plan']['commons_trajectory'] == document['plan']['commons_trajectory']
    assert decoded['plan']['commons_trajectory'] == document['plan']['commons_trajectory']
    events = decoded['plan']['commons_trajectory']['events']
    assert [e['id'] for e in events] == [e['id'] for e in game.project('log')]
    assert events == game.project('log')
    assert 'synthetic_simulation' in encoded and 'hypothetical_simulation' in encoded
    assert reconstruct(decoded).get_world() == game.get_world()


def test_contract_lifecycle_and_partial_acceptances_stay_distinct():
    document = project_trajectory(run_demo())
    states = {frame['sequence']:frame for frame in frames(document)}
    assert states[2]['kind'] == 'propose'
    assert states[4]['kind'] == states[5]['kind'] == 'accept'
    assert states[4]['agreements'][0]['status'] == 'negotiating'
    assert states[5]['agreements'][0]['status'] == 'accepted'
    assert states[6]['kind'] == 'authorize'
    assert states[8]['kind'] == 'initiate'
    assert states[11]['agreements'][0] == {'id':'agreement-main','current_version':2,
                                        'status':'fulfilled','outcome_status':'unverified'}
    assert states[12]['kind'] == 'verify'
    assert states[12]['agreements'][0]['outcome_status'] == 'verified'
    assert all(frame['world_kind'] == 'synthetic_simulation' for frame in states.values())
    assert all(frame['time_kind'] == 'commons_logical_transaction_time' for frame in states.values())


def test_alternative_branches_do_not_change_authoritative_memory_or_sqlite(tmp_path):
    from commons_engine.store import SQLiteStore
    from commons_game import CommonsGame
    game = run_demo()
    store = SQLiteStore(tmp_path/'authoritative.sqlite',CommonsGame)
    store.initialise(game)
    before = game.get_world(),game.project('log'),store.path.read_bytes()
    branches = alternatives(game)
    document = project_trajectory(game, branches=branches)
    rejected = reconstruct(document,branch_id='reject')
    accepted = reconstruct(document,branch_id='accept')
    assert rejected.project('agreements')[0]['status']=='rejected'
    assert accepted.project('agreements')[0]['status']=='negotiating'
    assert game.project('agreements')[0]['outcome_status']=='verified'
    assert before == (game.get_world(),game.project('log'),store.path.read_bytes())
    branch_frames=list(frames(document,branch_id='reject'))
    assert branch_frames[-1]['history_kind']=='hypothetical'
    assert branch_frames[-1]['state_id'].startswith('reject:')
    assert branch_frames[2]['state_hash']==list(frames(document))[2]['state_hash']


def test_rejected_hypothetical_action_is_diagnostic_and_creates_no_transition():
    game=run_demo()
    branch=simulate_branch(game,parent_sequence=3,branch_id='invalid',commands=[{
        'key':'wrong-approval','actor':'custodian','kind':'authorize',
        'agreement_id':'agreement-main','version':2}])
    assert branch['events']==[]
    assert branch['attempts'][0]['ok'] is False
    assert branch['attempts'][0]['errors']==['invalid_transition']
    document=load_trajectory_yaml(trajectory_yaml(project_trajectory(game,branches=[branch])))
    assert reconstruct(document,branch_id='invalid').get_world()==game.world_at(event=3)


def test_loaded_package_document_is_detached_and_inspection_cannot_write_back():
    game=run_demo()
    document=project_trajectory(game)
    decoded=load_trajectory_yaml(trajectory_yaml(document))
    detached=reconstruct(decoded)
    detached._world['actors']['researcher']['label']='Only the detached projection'
    assert game.get_world()['actors']['researcher']['label']!='Only the detached projection'
    assert decoded['plan']['commons_trajectory']['events']==game.project('log')


def test_serialized_state_hashes_and_event_order_are_validated_by_commons():
    game=run_demo()
    document=project_trajectory(game)
    envelope=document['plan']['commons_trajectory']
    envelope['events'][1],envelope['events'][2]=envelope['events'][2],envelope['events'][1]
    envelope['history_digest']=digest(envelope['events'])
    with pytest.raises(ValueError,match='invalid_log_sequence'):
        reconstruct(document)


def test_branch_parent_and_resolved_diagnostics_cannot_be_silently_reassigned():
    game=run_demo()
    document=project_trajectory(game,branches=alternatives(game))
    document['plan']['commons_trajectory']['branches'][0]['parent_state_hash']='wrong'
    with pytest.raises(DomainError,match='branch_parent_mismatch'):
        trajectory_yaml(document)
    document=project_trajectory(game,branches=alternatives(game))
    document['plan']['commons_trajectory']['branches'][0]['attempts'][0]['ok']=False
    with pytest.raises(DomainError,match='branch_resolution_mismatch'):
        trajectory_yaml(document)


def test_unsupported_adapter_version_fails_and_unknown_record_fields_are_retained():
    game=run_demo()
    document=project_trajectory(game)
    document['plan']['commons_trajectory']['schema_version']='subtle-trajectory/v99'
    with pytest.raises(DomainError,match='unsupported_commons_trajectory_schema'):
        trajectory_yaml(document)
    document=project_trajectory(game)
    envelope=document['plan']['commons_trajectory']
    envelope['events'][0]['external_observation']={'source':'synthetic','uncertainty':'unknown','observed_at':None}
    envelope['history_digest']=digest(envelope['events'])
    imported=load_trajectory_yaml(trajectory_yaml(document))
    assert imported['plan']['commons_trajectory']['events'][0]['external_observation']==envelope['events'][0]['external_observation']


def test_actual_cli_demonstration_exports_then_inspects_without_a_live_database(tmp_path):
    root=Path(__file__).resolve().parents[1]
    output=tmp_path/'trajectory.yaml'
    result=subprocess.run([sys.executable,'-B','-m','commons_game','trajectory-demo',
                           'bilateral-logs','--export',str(output)],cwd=root,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert 'REPLAY CONSISTENT: True' in result.stdout
    assert 'ALTERNATIVES LEFT AUTHORITATIVE WORLD UNCHANGED: True' in result.stdout
    assert 'Outcome independently verified' in result.stdout
    assert 'HYPOTHETICAL BRANCH reject' in result.stdout
    imported=subprocess.run([sys.executable,'-B','-m','commons_game','inspect-trajectory',str(output),'--branch','reject'],
                            cwd=root,text=True,capture_output=True,timeout=20)
    assert imported.returncode==0,imported.stderr
    assert 'rejected / outcome=unverified' in imported.stdout
