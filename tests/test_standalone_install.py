"""Actual wheel installation without a sibling Hube or trajectory package."""
import os
import hashlib
import json
import shutil
import subprocess
import sys
import venv
from pathlib import Path


def test_core_wheel_installs_and_launches_without_neighbouring_projects(tmp_path):
    root=Path(__file__).resolve().parents[1];wheels=tmp_path/'wheels'
    release_check = subprocess.run([sys.executable, '-B', str(root/'tools/build_game_gamer_release.py'), '--check'],
                                   capture_output=True, text=True)
    assert release_check.returncode == 0, release_check.stderr
    result=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),str(root),str(root / "game-gamer/examples/lantern-club"),"wcwidth>=0.2.12,<1","PyYAML>=6,<7"],
                          capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    lock=json.loads((root/'config/game-gamer-release.json').read_text())
    release=root/lock['wheel']
    assert hashlib.sha256(release.read_bytes()).hexdigest()==lock['sha256']
    shutil.copy2(release,wheels/release.name)
    environment=tmp_path/'isolated';venv.EnvBuilder(with_pip=True).create(environment)
    python=environment/'bin/python'
    fictional_install=subprocess.run([str(python),'-m','pip','install','--no-index','--find-links',str(wheels),
                                       'lantern-club==0.1.0'],capture_output=True,text=True,timeout=30)
    assert fictional_install.returncode==0,fictional_install.stderr
    env={**os.environ,'SADDLE_DATA_DIR':str(tmp_path/'data'),'PYTHONPATH':''}
    core_only=subprocess.run([str(python),'-I','-c',
        'import importlib.util; from lantern_club import main; '
        'assert importlib.util.find_spec("commons_game") is None; '
        'assert importlib.util.find_spec("yaml") is None; main()'],
        cwd=tmp_path,capture_output=True,text=True,env=env,timeout=15)
    assert core_only.returncode==0,core_only.stderr
    install=subprocess.run([str(python),'-m','pip','install','--no-index','--find-links',str(wheels),str(next(wheels.glob('commons_game-*.whl')))],
                           capture_output=True,text=True,timeout=30)
    assert install.returncode==0,install.stderr
    probe=subprocess.run([str(python),'-I','-c',
        'import importlib.util; from commons_game import load_scenario; assert importlib.util.find_spec("game") is None; '
        'assert importlib.util.find_spec("trajectory_engine") is None; '
        'g=load_scenario("montreal-commons"); assert g.replay().get_world()==g.get_world()'],
        cwd=tmp_path,capture_output=True,text=True,env=env,timeout=15)
    assert probe.returncode==0,probe.stderr
    start=subprocess.run([str(environment/'bin/saddle-pathways')],input='q\n',text=True,capture_output=True,cwd=tmp_path,env=env,timeout=15)
    assert start.returncode==0,start.stderr
    assert 'SADDLE PATHWAYS' in start.stdout and 'WORLD / COMMONS IS THE DEFAULT' in start.stdout

    fictional = subprocess.run([str(environment/'bin/lantern-club')], cwd=tmp_path, capture_output=True,
                               text=True, env=env, timeout=15)
    assert fictional.returncode == 0, fictional.stderr
    assert '\"visits\": 1' in fictional.stdout
    acceptance = r"""
import json
from pathlib import Path
from importlib.metadata import version
import game_gamer, commons_game
from game_gamer import Collective, DomainError, SimulationBinding
from lantern_club import EXTENSION, definition, visit
assert version('game-gamer') == '0.3.0'
assert 'site-packages' in game_gamer.__file__ and 'site-packages' in commons_game.__file__
path=Path('independent.sqlite')
game=Collective.start(definition(),path=path,extension=EXTENSION)
binding=SimulationBinding(scope_id=game.scope_id,actor_id='lee')
action=visit(game)
assert game.submit(action,binding=binding)['ok']
history=game.history()
assert game.submit(action,binding=binding)['ok'] and game.history()==history
reopened=Collective.open(path,scope_id=game.scope_id,extension=EXTENSION)
assert reopened.project('visit_count')==1
assert Collective.from_history(json.loads(json.dumps(history)),extension=EXTENSION).project()==game.project()
fork=game.fork(at=1,branch_id='possible')
assert fork.submit(visit(fork),binding=SimulationBinding(scope_id=fork.scope_id,actor_id='lee'))['ok']
assert game.history()==history
assert Collective.from_history(fork.history(),extension=EXTENSION).project()==fork.project()
try:
 Collective.open(path,scope_id=game.scope_id)
except DomainError as error:
 assert str(error)=='extension_unavailable'
else:
 raise AssertionError('Required application extension was silently dropped')
"""
    independent = subprocess.run([str(python), '-I', '-c', acceptance], cwd=tmp_path,
                                 capture_output=True, text=True, env=env, timeout=20)
    assert independent.returncode == 0, independent.stderr
    restart = subprocess.run([str(python), '-I', '-c',
        "from game_gamer import Collective; from lantern_club import EXTENSION; "
        "assert Collective.open('independent.sqlite',scope_id='lantern-club',extension=EXTENSION).project('visit_count')==1"],
        cwd=tmp_path, capture_output=True, text=True, env=env, timeout=15)
    assert restart.returncode == 0, restart.stderr
