"""Actual wheel installation without a sibling Hube or trajectory package."""
import os
from pathlib import Path
import subprocess
import sys
import venv


def test_core_wheel_installs_and_launches_without_neighbouring_projects(tmp_path):
    root=Path(__file__).resolve().parents[1];wheels=tmp_path/'wheels'
    result=subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),str(root)],
                          capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    environment=tmp_path/'isolated';venv.EnvBuilder(with_pip=True).create(environment)
    python=environment/'bin/python'
    install=subprocess.run([str(python),'-m','pip','install','--no-deps','--no-index',str(next(wheels.glob('commons_game-*.whl')))],
                           capture_output=True,text=True,timeout=30)
    assert install.returncode==0,install.stderr
    env={**os.environ,'SADDLE_DATA_DIR':str(tmp_path/'data'),'PYTHONPATH':''}
    probe=subprocess.run([str(python),'-I','-c',
        'import importlib.util; from commons_game import load_scenario; assert importlib.util.find_spec("game") is None; '
        'assert importlib.util.find_spec("trajectory_engine") is None; '
        'g=load_scenario("montreal-commons"); assert g.replay().get_world()==g.get_world()'],
        cwd=tmp_path,capture_output=True,text=True,env=env,timeout=15)
    assert probe.returncode==0,probe.stderr
    start=subprocess.run([str(environment/'bin/saddle-pathways')],input='q\n',text=True,capture_output=True,cwd=tmp_path,env=env,timeout=15)
    assert start.returncode==0,start.stderr
    assert 'SADDLE PATHWAYS' in start.stdout and 'WORLD / COMMONS IS THE DEFAULT' in start.stdout
