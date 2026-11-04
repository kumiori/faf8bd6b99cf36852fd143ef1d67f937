from io import StringIO
from pathlib import Path
import subprocess
import sys

import pytest

from commons_game import CommonsGame, load_scenario
from commons_game.tui import run_play

ROOT=Path(__file__).resolve().parents[1]


def test_terminal_is_actor_bound_and_invalid_navigation_does_not_run_demo():
    game=load_scenario()
    output=StringIO()
    run_play(game,actor='researcher',source=StringIO('s\n5\n1\nb\nq\n'),output=output)
    assert 'Identity switching requires --hot-seat' in output.getvalue()
    assert 'ACTOR custodian' in output.getvalue()  # inspection, not an identity change
    assert 'Actor: researcher' in output.getvalue()
    assert len(game.project('log'))==1
    assert game.project('agreements')==[]


def test_cancelled_and_invalid_contract_forms_never_partially_write():
    game=load_scenario()
    before=game.get_world(),game.project('log')
    output=StringIO()
    # invalid action selection retries; cancellation occurs inside the form.
    run_play(game,actor='researcher',source=StringIO('3\na\nnot-a-choice\n1\n0\nb\nq\n'),output=output)
    assert 'Invalid input; please try again.' in output.getvalue()
    assert 'Cancelled; no incomplete action was submitted.' in output.getvalue()
    assert before==(game.get_world(),game.project('log'))


def test_entered_hot_seat_commands_complete_contract_and_show_actual_trajectory():
    pytest.importorskip('trajectory_engine',reason='Install the trajectory extra for package integration tests')
    game=load_scenario()
    source=(ROOT/'tests/scenarios/subtle_bilateral.stdin').read_text()
    output=StringIO()
    run_play(game,actor='researcher',hot_seat=True,source=StringIO(source),output=output)
    assert game.project('agreements')[0]['current_version']==2
    assert game.project('agreements')[0]['outcome_status']=='verified'
    assert game.project('objectives')[0]['status']=='verified'
    assert len(game.project('log'))==12
    assert 'Outcome independently verified' in output.getvalue()
    assert 'STATE 012 [recorded]' in output.getvalue()
    assert 'REPLAY CONSISTENT: True' in output.getvalue()
    assert game.replay().get_world()==game.get_world()
    assert all('availability probe' not in str(e).lower() for e in game.project('log'))


def test_real_cli_play_persists_resumes_and_rejects_wrong_world(tmp_path):
    pytest.importorskip('trajectory_engine',reason='Install the trajectory extra for package integration tests')
    path=tmp_path/'terminal.sqlite'
    prefix=[sys.executable,'-B','-m','commons_game','--db',str(path)]
    source=(ROOT/'tests/scenarios/subtle_bilateral.stdin').read_text()
    result=subprocess.run(prefix+['play','bilateral-logs','--actor','researcher','--hot-seat'],
                          input=source,cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    saved=CommonsGame.load(path)
    assert saved.project('objectives')[0]['status']=='verified'
    original=path.read_bytes()
    result=subprocess.run(prefix+['play','--actor','verifier'],input='4\nr\nb\nq\n',
                          cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==0 and 'REPLAY CONSISTENT: True' in result.stdout
    assert path.read_bytes()==original
    result=subprocess.run(prefix+['play','montreal-geneva'],input='',cwd=ROOT,capture_output=True,text=True,timeout=20)
    assert result.returncode==1 and 'world_scenario_mismatch' in result.stderr
    assert path.read_bytes()==original


def test_terminal_hypothetical_branch_never_changes_history():
    pytest.importorskip('trajectory_engine',reason='Install the trajectory extra for package integration tests')
    from commons_game.scenario import demo_commands
    game=load_scenario()
    for command in demo_commands()[:2]:
        assert game.submit(command)['ok']
    before=game.get_world(),game.project('log')
    # History → branch at negotiated state → accept as current actor → inspect.
    output=StringIO()
    run_play(game,actor='custodian',source=StringIO('4\ns\n3\n1\ny\nb\nq\n'),output=output)
    assert 'HYPOTHETICAL ONLY. Authoritative history unchanged.' in output.getvalue()
    assert '[hypothetical]' in output.getvalue()
    assert before==(game.get_world(),game.project('log'))


def test_cli_scenario_and_actor_selection_can_exit_without_creating_world(tmp_path):
    path=tmp_path/'never-started.sqlite'
    result=subprocess.run([sys.executable,'-B','-m','commons_game','--db',str(path),'play'],
                          input='q\n',cwd=ROOT,capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and not path.exists()
