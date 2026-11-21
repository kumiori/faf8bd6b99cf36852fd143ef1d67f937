"""Keep the installed-package gate runnable without granting write authority."""
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_pr_revalidation_uses_the_required_check_name_and_read_only_token():
    workflow = yaml.safe_load((ROOT/'.github/workflows/game-gamer-compatibility.yml').read_text())
    assert workflow['permissions'] == {'contents': 'read'}
    events = workflow.get('on', workflow.get(True))
    assert events['pull_request'] is None  # Required checks must run on every new PR commit.
    job = workflow['jobs']['compatibility']
    assert job['name'] == 'Game-Gamer compatibility'
    validation = next(step for step in job['steps'] if step.get('name') == 'Validate checked-in upgrade')
    assert validation['env']['GH_TOKEN'] == '${{ github.token }}'
    assert '-m release.compatibility' in validation['run']


def test_consumer_bootstrap_tools_match_the_reviewed_source():
    for source in (ROOT/'game-gamer/release').glob('*.py'):
        assert source.read_bytes() == (ROOT/'.github/game-gamer/release'/source.name).read_bytes()
    assert (ROOT/'game-gamer/config/consumers.json').read_bytes() == (ROOT/'.github/game-gamer/consumers.json').read_bytes()
