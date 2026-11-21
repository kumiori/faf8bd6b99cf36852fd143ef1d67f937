"""Build a deterministic wheel and its immutable release asset set."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile

REPOSITORY = 'kumiori/113a4cce0c9191877e82b1a0b6767a70'
EPOCH = '1795219200'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(source, output, commit):
    source, output = Path(source), Path(output)
    version = tomllib.loads((source/'pyproject.toml').read_text())['project']['version']
    manifest = json.loads((source/'src/game_gamer/capabilities.json').read_text())
    assert manifest['version'] == version and manifest['package'] == 'game-gamer'
    assert len(commit) == 40 and all(c in '0123456789abcdef' for c in commit), 'Full source commit required'
    output.mkdir(parents=True, exist_ok=True)
    assert not list(output.iterdir()), 'Release output must be empty; published assets are never overwritten'
    with tempfile.TemporaryDirectory(prefix='game-gamer-build-') as directory:
        clean = Path(directory)/'source'
        clean.mkdir()
        shutil.copytree(source/'src', clean/'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
        for name in ('pyproject.toml', 'README.md', 'LICENSE', 'NOTICE', 'COPYING'):
            if (source/name).is_file():
                shutil.copy2(source/name, clean/name)
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                        '--wheel-dir', str(output.resolve()), str(clean)], check=True,
                       env={**os.environ, 'SOURCE_DATE_EPOCH': EPOCH})
    wheel = next(output.glob('game_gamer-*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        payload = archive.read('game_gamer/capabilities.json')
        assert json.loads(payload) == manifest
    (output/'capabilities.json').write_bytes(payload)
    shutil.copy2(source/'CHANGELOG.md', output/'CHANGELOG.md')
    record = {'schema': 'game-gamer/release/v1', 'package': 'game-gamer', 'version': version,
              'tag': 'v'+version, 'repository': REPOSITORY, 'source_commit': commit,
              'extension_contract': manifest['extension_contract'], 'source_date_epoch': int(EPOCH),
              'assets': {path.name: sha256(path) for path in sorted(output.iterdir())}}
    (output/'release.json').write_text(json.dumps(record, indent=2)+'\n')
    (output/'SHA256SUMS').write_text(''.join(f'{sha256(path)}  {path.name}\n'
                                           for path in sorted(output.iterdir()) if path.name != 'SHA256SUMS'))
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.source_commit), indent=2))
