"""Open or refresh a review-only upgrade PR and publish its validation status."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from release.consumer import gh, require


def propose(root, proposal, validation):
    root = Path(root).resolve()
    report = json.loads((validation/'compatibility.json').read_text())
    version = proposal['version']
    branch = 'codex/game-gamer-'+version
    repository = os.environ['GITHUB_REPOSITORY']
    require(repository in {item['repository'] for item in json.loads(
        (Path(__file__).parents[1]/'consumers.json').read_text())['consumers']}, 'Consumer is not registered')
    body = validation/'compatibility.md'
    relative_report = 'docs/upgrades/game-gamer-'+version
    (root/relative_report).mkdir(parents=True, exist_ok=True)
    for name in ('compatibility.json', 'compatibility.md'):
        (root/relative_report/name).write_bytes((validation/name).read_bytes())
    paths = [*proposal['paths'], relative_report]
    subprocess.run(['git', 'checkout', '-b', branch], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], cwd=root, check=True)
    subprocess.run(['git', 'add', '--', *paths], cwd=root, check=True)
    subprocess.run(['git', 'commit', '-m', 'Propose Game-Gamer '+version], cwd=root, check=True)
    # No force update: an existing proposal is never overwritten behind its reviewer.
    existing = json.loads(gh('pr', 'list', '--repo', repository, '--head', branch, '--state', 'all', '--json', 'url'))
    if existing:
        print('Existing proposal retained: '+existing[0]['url'])
        return
    subprocess.run(['gh', 'auth', 'setup-git'], check=True)
    subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/'+branch], cwd=root, check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    state = 'success' if report['compatible'] else 'failure'
    gh('api', '--method', 'POST', f'repos/{repository}/statuses/{commit}', '-f', 'state='+state,
       '-f', 'context=Game-Gamer compatibility', '-f', 'description=Review required; no world migration',
       '-f', 'target_url='+os.environ['GITHUB_SERVER_URL']+'/'+repository+'/actions/runs/'+os.environ['GITHUB_RUN_ID'])
    subprocess.run(['gh', 'pr', 'create', '--repo', repository, '--head', branch, '--draft',
                    '--title', 'Upgrade Game-Gamer to '+version, '--body-file', str(body)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    args = parser.parse_args()
    propose(args.root, json.loads(args.proposal.read_text()), args.validation)
