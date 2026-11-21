from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile

import pytest

from game_gamer import __version__, get_capabilities
from release.bundle import REPOSITORY, sha256
from release.compatibility import compare_api, markdown
from release.consumer import feature_diff, prepare, verify_bundle


def test_manifest_is_versioned_detached_and_available_without_terminal():
    manifest = get_capabilities()
    version = tomllib.loads((Path(__file__).parents[1]/'pyproject.toml').read_text())['project']['version']
    assert manifest['version'] == __version__ == version
    assert manifest['extension_contract'] == 'game-gamer/extension/v1'
    assert {'mission.create', 'mission.challenge', 'mission.revise', 'mission.complete',
            'world.fork', 'history.replay', 'tui.network'} <= set(manifest['capabilities'])
    manifest['capabilities'].clear()
    assert get_capabilities()['capabilities']
    output = subprocess.check_output([sys.executable, '-m', 'game_gamer', 'capabilities'], text=True)
    assert json.loads(output) == get_capabilities()


def assets(tmp_path):
    directory = tmp_path/'bundle'
    directory.mkdir()
    manifest = get_capabilities()
    manifest['version'] = '9.0.1'
    wheel = directory/'game_gamer-9.0.1-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('game_gamer/capabilities.json', json.dumps(manifest))
        archive.writestr('game_gamer-9.0.1.dist-info/METADATA', 'Name: game-gamer\nVersion: 9.0.1\n')
    (directory/'capabilities.json').write_text(json.dumps(manifest))
    (directory/'CHANGELOG.md').write_text('Fictional release')
    record = {'schema': 'game-gamer/release/v1', 'package': 'game-gamer', 'version': '9.0.1', 'tag': 'v9.0.1',
              'repository': REPOSITORY, 'source_commit': 'a'*40, 'source_date_epoch': 1795219200,
              'extension_contract': manifest['extension_contract'],
              'assets': {path.name: sha256(path) for path in directory.iterdir()}}
    (directory/'release.json').write_text(json.dumps(record))
    (directory/'SHA256SUMS').write_text(''.join(f'{sha256(path)}  {path.name}\n'
                                              for path in sorted(directory.iterdir())))
    metadata = {'id': 10, 'immutable': True, 'draft': False, 'prerelease': False,
                'tag_name': 'v9.0.1', 'resolved_commit': 'a'*40}
    return directory, metadata


@pytest.mark.parametrize('changes', [{'immutable': False}, {'draft': True}, {'prerelease': True},
                                    {'resolved_commit': 'b'*40}, {'tag_name': 'v9.0.2'}])
def test_mutable_or_misbound_releases_fail_closed(tmp_path, changes):
    directory, metadata = assets(tmp_path)
    with pytest.raises(ValueError):
        verify_bundle(directory, {**metadata, **changes})


def test_checksum_tampering_is_rejected(tmp_path):
    directory, metadata = assets(tmp_path)
    (directory/'capabilities.json').write_text('{}')
    with pytest.raises(ValueError, match='Checksum mismatch'):
        verify_bundle(directory, metadata)


def test_upgrade_changes_only_pins_and_artifacts_and_preserves_extensions_and_worlds(tmp_path):
    directory, metadata = assets(tmp_path)
    root = tmp_path/'consumer'
    (root/'config').mkdir(parents=True)
    (root/'vendor').mkdir()
    (root/'pyproject.toml').write_text('dependencies = ["game-gamer[tui]==9.0.0"]')
    (root/'extension.py').write_text('VERSION = "historical-1.0.0"')
    (root/'production.sqlite').write_bytes(b'untouched persisted world')
    old_wheel = root/'vendor/game_gamer-9.0.0-py3-none-any.whl'
    with zipfile.ZipFile(old_wheel, 'w') as archive:
        archive.writestr('old.py', '')
    lock = {'version': '9.0.0', 'wheel': 'vendor/'+old_wheel.name}
    (root/'config/game-gamer-release.json').write_text(json.dumps(lock))
    config = {'lock': 'config/game-gamer-release.json', 'requirements': 'requirements/game-gamer-release.txt',
              'pins': [{'path': 'pyproject.toml', 'value': 'game-gamer[tui]==9.0.0'}],
              'supported_extension_contracts': ['game-gamer/extension/v1'], 'required_capabilities': ['history.replay']}
    proposal = prepare(root, directory, metadata, config)
    assert proposal['adoption'] == 'awaiting approval'
    assert '==9.0.1' in (root/'pyproject.toml').read_text()
    assert (root/'extension.py').read_text() == 'VERSION = "historical-1.0.0"'
    assert (root/'production.sqlite').read_bytes() == b'untouched persisted world'
    assert old_wheel.exists() and proposal['features']['baseline'] == 'not_published'
    with pytest.raises(ValueError, match='not newer'):
        prepare(root, directory, metadata, config)


def test_feature_loss_and_public_signature_breaks_are_explicit():
    current = get_capabilities()
    previous = deepcopy(current)
    previous['capabilities'].append('old.feature')
    assert feature_diff(previous, current)['removed'] == ['old.feature']
    assert feature_diff(None, current)['newly_available_count'] is None
    old = {'Collective.start': {'definition': {'kind': 'POSITIONAL_OR_KEYWORD', 'required': True}}}
    assert compare_api(old, {}) == ['Removed public callable: Collective.start']
    assert compare_api(old, {**old, 'new_callable': {}}) == []
    incompatible = deepcopy(old)
    incompatible['Collective.start']['new'] = {'kind': 'KEYWORD_ONLY', 'required': True}
    assert compare_api(old, incompatible) == ['New required parameter: Collective.start.new']
    report = markdown({'version': '9.0.1', 'checks': {'event_replay': 'FAIL / NOT VALIDATED'},
                       'features': feature_diff(None, current)})
    assert 'awaiting approval' in report and 'unknown' in report and 'FAIL' in report
