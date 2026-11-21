"""Verify immutable release assets and prepare a bounded dependency-only update."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from release.bundle import REPOSITORY, sha256


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version_tuple(version):
    require(isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version), 'Stable semantic version required')
    return tuple(map(int, version.split('.')))


def verify_bundle(directory, metadata):
    directory = Path(directory)
    require(metadata.get('immutable') is True and not metadata.get('draft') and not metadata.get('prerelease'),
            'Only published immutable stable releases are eligible')
    record = json.loads((directory/'release.json').read_text())
    require(record['schema'] == 'game-gamer/release/v1' and record['package'] == 'game-gamer', 'Wrong release schema')
    version_tuple(record['version'])
    require(record['repository'] == REPOSITORY and metadata['tag_name'] == record['tag'] == 'v'+record['version'],
            'Release identity mismatch')
    require(metadata['resolved_commit'] == record['source_commit'], 'Tag/source commit mismatch')
    wheel_name = 'game_gamer-'+record['version']+'-py3-none-any.whl'
    require(set(record['assets']) == {wheel_name, 'capabilities.json', 'CHANGELOG.md'}, 'Unexpected release assets')
    checksums = {}
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        require(name not in checksums and re.fullmatch(r'[0-9a-f]{64}', checksum), 'Invalid checksums')
        checksums[name] = checksum
    require(set(checksums) == {*record['assets'], 'release.json'}, 'Incomplete checksum inventory')
    for name, checksum in checksums.items():
        require(sha256(directory/name) == checksum, 'Checksum mismatch: '+name)
        if name != 'release.json':
            require(checksum == record['assets'][name], 'Release checksum disagreement')
    manifest = json.loads((directory/'capabilities.json').read_text())
    require(manifest.get('schema') == 'game-gamer/capabilities/v1' and manifest['package'] == 'game-gamer'
            and manifest['version'] == record['version'] and manifest['extension_contract'] == record['extension_contract'],
            'Manifest identity mismatch')
    capabilities = manifest['capabilities']
    require(isinstance(capabilities, list) and capabilities == sorted(set(capabilities))
            and all(isinstance(item, str) and re.fullmatch(r'[a-z][a-z0-9_.]+', item) for item in capabilities),
            'Invalid capability inventory')
    with zipfile.ZipFile(directory/wheel_name) as archive:
        require(json.loads(archive.read('game_gamer/capabilities.json')) == manifest, 'Wheel/manifest disagreement')
        info = BytesParser().parsebytes(archive.read('game_gamer-'+record['version']+'.dist-info/METADATA'))
        require(info['Name'] == 'game-gamer' and info['Version'] == record['version'], 'Wheel metadata mismatch')
    return record, manifest


def inspect_capabilities(wheel):
    with zipfile.ZipFile(wheel) as archive:
        if 'game_gamer/capabilities.json' not in archive.namelist():
            return None
        return json.loads(archive.read('game_gamer/capabilities.json'))


def feature_diff(previous, current):
    if previous is None:
        return {'baseline': 'not_published', 'added': [], 'removed': [], 'newly_available_count': None,
                'note': 'Previous artifact has no manifest; first publication is not proof these features are new.'}
    old, new = set(previous['capabilities']), set(current['capabilities'])
    return {'baseline': 'published', 'added': sorted(new-old), 'removed': sorted(old-new),
            'newly_available_count': len(new-old)}


def prepare(root, directory, metadata, config):
    root, directory = Path(root), Path(directory)
    record, manifest = verify_bundle(directory, metadata)
    lock_path = root/config['lock']
    old = json.loads(lock_path.read_text())
    require(version_tuple(record['version']) > version_tuple(old['version']), 'Release is not newer')
    require(manifest['extension_contract'] in config['supported_extension_contracts'], 'Unsupported extension contract')
    require(set(config['required_capabilities']) <= set(manifest['capabilities']), 'Required capabilities missing')
    previous = inspect_capabilities(root/old['wheel'])
    difference = feature_diff(previous, manifest)
    require(not difference['removed'], 'Advertised capabilities were removed')
    updates = {}
    # Paths are checked-in consumer configuration, never supplied by a release.
    for entry in config['pins']:
        path = root/entry['path']
        content = path.read_text()
        require(content.count(entry['value']) == 1, 'Exact previous pin not found: '+entry['path'])
        replacement = entry.get('template', 'game-gamer[tui]=={version}').format(version=record['version'])
        updates[entry['path']] = content.replace(entry['value'], replacement)
    wheel = directory/('game_gamer-'+record['version']+'-py3-none-any.whl')
    target = 'vendor/'+wheel.name
    new_lock = {'package': 'game-gamer', 'version': record['version'], 'wheel': target,
                'sha256': sha256(wheel), 'extension_contract': record['extension_contract'],
                'source_date_epoch': record['source_date_epoch'], 'source_commit': record['source_commit'],
                'repository': record['repository'], 'tag': record['tag'], 'release_id': metadata['id']}
    updates[config['lock']] = json.dumps(new_lock, indent=2)+'\n'
    updates[config['requirements']] = target+' --hash=sha256:'+sha256(wheel)+'\n'
    updates['vendor/game-gamer-capabilities.json'] = json.dumps(manifest, indent=2)+'\n'
    # Refresh only the previous-pin metadata for the next proposal.
    next_config = json.loads(json.dumps(config))
    next_config['baseline_wheel'] = old['wheel']
    for entry in next_config['pins']:
        entry['value'] = entry.get('template', 'game-gamer[tui]=={version}').format(version=record['version'])
    updates['config/game-gamer-consumer.json'] = json.dumps(next_config, indent=2)+'\n'
    for relative, content in updates.items():
        path = root/relative
        require(path.resolve().is_relative_to(root.resolve()), 'Unsafe consumer path')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (root/'vendor').mkdir(exist_ok=True)
    shutil.copy2(wheel, root/target)
    return {'schema': 'game-gamer/upgrade/v1', 'previous_version': old['version'], 'version': record['version'],
            'source_commit': record['source_commit'], 'release_id': metadata['id'], 'features': difference,
            'adoption': 'awaiting approval', 'paths': sorted([*updates, target])}


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True).strip()


def download(config, directory, tag=None):
    repo = config['upstream']
    require(repo == REPOSITORY, 'Unexpected upstream')
    endpoint = 'tags/'+tag if tag else 'latest'
    if tag:
        require(re.fullmatch(r'v\d+\.\d+\.\d+', tag), 'Invalid release tag')
    metadata = json.loads(gh('api', f'repos/{repo}/releases/{endpoint}'))
    require(metadata.get('immutable') is True and not metadata['draft'] and not metadata['prerelease'],
            'Only immutable releases may be downloaded')
    tag_name = metadata['tag_name']
    require(re.fullmatch(r'v\d+\.\d+\.\d+', tag_name), 'Invalid release tag')
    reference = json.loads(gh('api', f'repos/{repo}/git/ref/tags/{tag_name}'))['object']
    if reference['type'] == 'tag':
        reference = json.loads(gh('api', f'repos/{repo}/git/tags/{reference["sha"]}'))['object']
    require(reference['type'] == 'commit', 'Tag must resolve to a commit')
    metadata['resolved_commit'] = reference['sha']
    subprocess.run(['gh', 'release', 'download', tag_name, '--repo', repo, '--dir', str(directory),
                    '--pattern', '*.whl', '--pattern', 'capabilities.json', '--pattern', 'CHANGELOG.md',
                    '--pattern', 'release.json', '--pattern', 'SHA256SUMS'], check=True)
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--tag')
    parser.add_argument('--skip-existing', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((args.root/'config/game-gamer-consumer.json').read_text())
    args.bundle.mkdir(parents=True, exist_ok=True)
    metadata = json.loads(args.metadata.read_text()) if args.metadata else download(config, args.bundle, args.tag)
    old = json.loads((args.root/config['lock']).read_text())
    if version_tuple(metadata['tag_name'][1:]) <= version_tuple(old['version']):
        print('Already at newest eligible release')
    elif args.skip_existing and json.loads(gh('pr', 'list', '--repo', __import__('os').environ['GITHUB_REPOSITORY'],
         '--head', 'codex/game-gamer-'+metadata['tag_name'][1:], '--state', 'all', '--json', 'number')):
        print('An upgrade proposal already exists for this release; preserving its review decision')
    else:
        report = prepare(args.root, args.bundle, metadata, config)
        args.output.write_text(json.dumps(report, indent=2)+'\n')
        print('Prepared upgrade proposal '+report['version'])
