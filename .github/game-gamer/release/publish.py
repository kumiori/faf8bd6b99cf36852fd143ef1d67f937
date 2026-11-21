"""Publish a new fully populated draft, then require GitHub immutability."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from release.bundle import REPOSITORY
from release.consumer import gh, require, verify_bundle


def publish(directory):
    directory = Path(directory)
    record = json.loads((directory/'release.json').read_text())
    tag = record['tag']
    verify_bundle(directory, {'immutable': True, 'draft': False, 'prerelease': False,
                             'tag_name': tag, 'resolved_commit': record['source_commit']})
    setting = json.loads(gh('api', f'repos/{REPOSITORY}/immutable-releases'))
    require(setting['enabled'], 'Enable immutable releases in the upstream repository first')
    existing = subprocess.run(['gh', 'release', 'view', tag, '--repo', REPOSITORY], capture_output=True)
    require(existing.returncode != 0, 'Release already exists; never replace published assets')
    subprocess.run(['gh', 'release', 'create', tag, '--repo', REPOSITORY, '--verify-tag', '--draft',
                    '--title', 'Game-Gamer '+record['version'], '--notes-file', str(directory/'CHANGELOG.md')], check=True)
    subprocess.run(['gh', 'release', 'upload', tag, '--repo', REPOSITORY,
                    *[str(path) for path in sorted(directory.iterdir())]], check=True)
    subprocess.run(['gh', 'release', 'edit', tag, '--repo', REPOSITORY, '--draft=false'], check=True)
    release = json.loads(gh('api', f'repos/{REPOSITORY}/releases/tags/{tag}'))
    require(release['immutable'] is True, 'Published release is not immutable')
    print(release['html_url'])
    registry = Path(__file__).parents[1]/'config/consumers.json'
    environment = dict(os.environ)
    if environment.get('CONSUMER_DISPATCH_TOKEN'):
        environment['GH_TOKEN'] = environment['CONSUMER_DISPATCH_TOKEN']
    for consumer in json.loads(registry.read_text())['consumers']:
        result = subprocess.run(['gh', 'workflow', 'run', consumer['workflow'], '--repo', consumer['repository']],
                                env=environment, capture_output=True, text=True)
        print(json.dumps({'consumer': consumer['id'], 'notification': 'dispatched' if result.returncode == 0
                          else 'scheduled_poll_fallback', 'detail': result.stderr.strip()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    publish(parser.parse_args().directory)
