"""Fail-closed consumer validation in disposable environments and synthetic saves."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def compare_api(previous, current):
    failures = []
    for name, params in previous.items():
        if name not in current:
            failures.append('Removed public callable: '+name)
            continue
        for param, spec in params.items():
            new = current[name].get(param)
            if new is None or new['kind'] != spec['kind'] or new['required'] and not spec['required']:
                failures.append('Incompatible public parameter: '+name+'.'+param)
        for param, spec in current[name].items():
            if param not in params and spec['required']:
                failures.append('New required parameter: '+name+'.'+param)
    return failures


def markdown(report):
    lines = [f'# Game-Gamer {report["version"]} available', '', '| Check | Result |', '| --- | --- |']
    lines += [f'| {key.replace("_", " ")} | {value} |' for key, value in report['checks'].items()]
    diff = report['features']
    lines += ['', 'Newly available capabilities: '+str(diff['newly_available_count'] if
               diff['newly_available_count'] is not None else 'unknown (previous release had no manifest)'),
              '', 'Added: '+(', '.join(diff['added']) or 'none established'),
              '', 'Removed: '+(', '.join(diff['removed']) or 'none'),
              '', '**Adoption: awaiting approval.** No persisted worlds or extension versions were migrated.']
    if report.get('error'):
        lines += ['', 'Validation error: `'+report['error'].replace('`', "'")[:2000]+'`']
    return '\n'.join(lines)+'\n'


def validate(root, proposal, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads((root/'config/game-gamer-consumer.json').read_text())
    report = {**proposal, 'checks': {key: 'NOT RUN' for key in ('artifact_integrity', 'public_api',
              'extension_version_binding', 'event_replay', 'restart', 'branch_isolation', 'clean_install',
              'legacy_saves', 'application_tests', 'capabilities')}, 'compatible': False}
    probe = Path(__file__).with_name('probe.py').resolve()
    lock = json.loads((root/config['lock']).read_text())
    def run(command, *, cwd, environment, name):
        result = subprocess.run(command, cwd=cwd, env=environment, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=600)
        (output/(name+'.log')).write_text(result.stdout)
        if result.returncode:
            raise RuntimeError(name+' failed; see '+name+'.log')
        return result.stdout
    try:
        from release.bundle import sha256
        assert sha256(root/lock['wheel']) == lock['sha256'], 'Pinned wheel checksum mismatch'
        if 'tag' in lock:
            from release.consumer import download, verify_bundle
            with tempfile.TemporaryDirectory(prefix='gamer-release-verification-') as trusted:
                metadata = download(config, trusted, lock['tag'])
                record, _ = verify_bundle(trusted, metadata)
                assert metadata['id'] == lock['release_id'] and record['source_commit'] == lock['source_commit']
                assert record['assets'][Path(lock['wheel']).name] == lock['sha256'], 'Upstream release differs from pin'
        report['checks']['artifact_integrity'] = 'PASS'
        with tempfile.TemporaryDirectory(prefix='gamer-compatibility-') as directory:
            temporary = Path(directory)
            environment = {**os.environ, 'PYTHONPATH': '', 'PYTHONDONTWRITEBYTECODE': '1',
                           'SADDLE_DATA_DIR': str(temporary/'synthetic-data')}
            baseline, candidate = temporary/'baseline', temporary/'candidate'
            for target, wheel in ((baseline, root/config['baseline_wheel']), (candidate, root/lock['wheel'])):
                venv.EnvBuilder(with_pip=True).create(target)
                run([str(target/'bin/python'), '-m', 'pip', 'install', '--no-deps', str(wheel)],
                    cwd=temporary, environment=environment, name=target.name+'-install')
            old = json.loads(run([str(baseline/'bin/python'), '-I', str(probe), 'api'], cwd=temporary,
                                 environment=environment, name='baseline-api'))
            python = str(candidate/'bin/python')
            current = json.loads(run([python, '-I', str(probe), 'api'], cwd=temporary,
                                     environment=environment, name='candidate-api'))
            failures = compare_api(old, current)
            assert not failures, '; '.join(failures)
            report['checks']['public_api'] = 'PASS'
            checks = json.loads(run([python, '-I', str(probe), 'runtime', str(temporary/'synthetic.sqlite')],
                               cwd=temporary, environment=environment, name='runtime'))
            report['checks'].update(checks)
            run([python, '-I', str(probe), 'restart', str(temporary/'synthetic.sqlite')], cwd=temporary,
                environment=environment, name='restart')
            report['checks']['restart'] = 'PASS'
            run([python, '-m', 'pip', 'install', 'setuptools==75.6.0', 'wheel==0.45.1', 'pytest==8.4.2',
                 'wcwidth==0.2.13', 'PyYAML==6.0.2'], cwd=temporary, environment=environment, name='test-dependencies')
            run([python, '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', str(root)],
                cwd=temporary, environment=environment, name='application-install')
            run([python, '-m', 'pip', 'check'], cwd=temporary, environment=environment, name='dependency-consistency')
            report['checks']['clean_install'] = 'PASS'
            legacy = run([python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *config['legacy_tests']],
                         cwd=root, environment=environment, name='legacy-saves')
            report['checks']['legacy_saves'] = 'PASS'
            application = run([python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *config.get('application_tests', ['tests'])],
                              cwd=root, environment=environment, name='application-tests')
            report['test_summaries'] = {'legacy': legacy.strip().splitlines()[-1],
                                        'application': application.strip().splitlines()[-1]}
            report['checks']['application_tests'] = 'PASS'
            inventory = json.loads((root/'vendor/game-gamer-capabilities.json').read_text())
            installed = json.loads(run([python, '-I', '-c',
                'import json;from game_gamer import get_capabilities;print(json.dumps(get_capabilities()))'],
                cwd=temporary, environment=environment, name='capabilities'))
            assert installed == inventory and set(config['required_capabilities']) <= set(installed['capabilities'])
            assert not proposal['features']['removed'], 'Capabilities removed'
            report['checks']['capabilities'] = 'PASS'
            report['compatible'] = all(value == 'PASS' for value in report['checks'].values())
    except Exception as error:
        report['error'] = str(error)
        for key, value in report['checks'].items():
            if value == 'NOT RUN':
                report['checks'][key] = 'FAIL / NOT VALIDATED'
    finally:
        (output/'compatibility.json').write_text(json.dumps(report, indent=2)+'\n')
        (output/'compatibility.md').write_text(markdown(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--proposal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.root, json.loads(args.proposal.read_text()), args.output)
    print(markdown(result))
    sys.exit(0 if result['compatible'] else 1)
