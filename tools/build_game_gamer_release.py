"""Build or check the deterministic Game-Gamer wheel used by Commons."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT/'game-gamer'
LOCK = ROOT/'config/game-gamer-release.json'
SOURCE_DATE_EPOCH = '1795219200'


def source_files():
    return sorted(path for path in (PACKAGE/'src/game_gamer').rglob('*')
                  if path.is_file() and path.suffix in {'.py', '.yaml', '.json'} and '__pycache__' not in path.parts)


def check_release():
    lock = json.loads(LOCK.read_text())
    wheel = ROOT/lock['wheel']
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == lock['sha256'], 'Release wheel hash mismatch'
    # The application may deliberately retain an older release than the development tree.
    current = tomllib.loads((PACKAGE/'pyproject.toml').read_text())['project']['version']
    with zipfile.ZipFile(wheel) as archive:
        from email.parser import BytesParser
        metadata = BytesParser().parsebytes(archive.read('game_gamer-'+lock['version']+'.dist-info/METADATA'))
        assert metadata['Name'] == 'game-gamer' and metadata['Version'] == lock['version']
        if current == lock['version']:
            expected = {path.relative_to(PACKAGE/'src').as_posix() for path in source_files()}
            actual = {name for name in archive.namelist() if name.startswith('game_gamer/')}
            assert actual == expected, 'Release wheel source inventory differs from checkout'
            for path in source_files():
                assert archive.read(path.relative_to(PACKAGE/'src').as_posix()) == path.read_bytes(), str(path)
    print('Verified pinned release '+lock['version']+' '+lock['sha256'])


def build_release():
    version = tomllib.loads((PACKAGE/'pyproject.toml').read_text())['project']['version']
    environment = {**os.environ, 'SOURCE_DATE_EPOCH': SOURCE_DATE_EPOCH, 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
    with tempfile.TemporaryDirectory(prefix='game-gamer-release-') as temporary:
        clean = Path(temporary)/'source'
        clean.mkdir()
        shutil.copytree(PACKAGE/'src', clean/'src', ignore=shutil.ignore_patterns('__pycache__', '*.egg-info'))
        for name in ('pyproject.toml', 'README.md', 'LICENSE', 'NOTICE', 'COPYING'):
            if (PACKAGE/name).is_file():
                shutil.copy2(PACKAGE/name, clean/name)
        subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                        '--wheel-dir', temporary, str(clean)], env=environment, check=True)
        wheel = next(Path(temporary).glob('game_gamer-*.whl'))
        target = ROOT/'vendor'/wheel.name
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(wheel.read_bytes())
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    LOCK.parent.mkdir(exist_ok=True)
    LOCK.write_text(json.dumps({'package': 'game-gamer', 'version': version,
                               'extension_contract': 'game-gamer/extension/v1',
                               'wheel': target.relative_to(ROOT).as_posix(), 'sha256': checksum,
                               'source_date_epoch': int(SOURCE_DATE_EPOCH)}, indent=2)+'\n')
    requirements = ROOT/'requirements/game-gamer-release.txt'
    requirements.parent.mkdir(exist_ok=True)
    requirements.write_text(target.relative_to(ROOT).as_posix()+' --hash=sha256:'+checksum+'\n')
    check_release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    if parser.parse_args().check:
        check_release()
    else:
        build_release()
