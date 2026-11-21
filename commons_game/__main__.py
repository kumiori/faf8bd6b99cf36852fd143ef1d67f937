"""SADDLE PATHWAYS terminal entry point; domain rules stay in the shared engine."""

import argparse
import json
import os
import sys
from pathlib import Path

import tomllib
from game_gamer.tui.errors import error_message

from commons_engine.store import SQLiteStore

from .engine import CommonsGame
from .i18n import t
from .missions import install_missions
from .scenario import SCENARIOS, demo_commands, load_scenario


def main(argv=None):
    parser = argparse.ArgumentParser(description=t('cli.help.description'))
    parser.add_argument('--db', help=t('cli.help.db'))
    commands = parser.add_subparsers(dest='operation')
    for name in ('start', 'demo'):
        command = commands.add_parser(name)
        command.add_argument('scenario', choices=SCENARIOS, nargs='?', default='bilateral-logs')
    play = commands.add_parser('play', help=t('cli.help.play'))
    play.add_argument('scenario', choices=SCENARIOS, nargs='?')
    play.add_argument('--actor', help=t('cli.help.actor'))
    play.add_argument('--hot-seat', action='store_true', help=t('cli.help.hot_seat'))
    play.add_argument('--mock-identities', type=Path, help=t('cli.help.mock_identities'))
    play.add_argument('--mock-player', help=t('cli.help.mock_player'))
    play.add_argument('--explore', action='store_true', help=t('cli.help.explore'))
    play.add_argument('--plain', action='store_true', help=t('cli.help.plain'))
    play.add_argument('--line-mode', action='store_true', help=t('cli.help.line_mode'))
    play.add_argument('--ui-trace-output',type=Path,help=t('cli.help.ui_trace_output'))
    play.add_argument('--developer-ui', action='store_true', help=t('cli.help.developer_ui'))
    play.add_argument('--choose-world', action='store_true', help=t('cli.help.choose_world'))
    imp = commands.add_parser('import-ecosystem', help=t('cli.help.import_ecosystem'))
    imp.add_argument('snapshot', type=Path)
    sources = commands.add_parser('import-reconstruction-sources', help=t('cli.help.import_reconstruction_sources'))
    sources.add_argument('snapshot', type=Path)
    montreal = commands.add_parser('import-montreal-network', help=t('cli.help.import_montreal_network'))
    montreal.add_argument('connections', type=Path)
    montreal.add_argument('statements', type=Path)
    montreal.add_argument('--identities', type=Path, help=t('cli.help.identities'))
    montreal.add_argument('--dry-run', action='store_true', help=t('cli.help.dry_run'))
    access = commands.add_parser('curator-access', help=t('cli.help.curator_access'))
    access.add_argument('decision', choices=('grant', 'revoke'))
    access.add_argument('actor', help=t('cli.help.actor_2'))
    access.add_argument('--reference', required=True, help=t('cli.help.reference'))
    capture = commands.add_parser('capture-notion', help=t('cli.help.capture_notion'))
    capture.add_argument('--source-mapping', type=Path, required=True)
    capture.add_argument('--protocol-project', type=Path, default=Path('../app_protocol_hack'))
    capture.add_argument('--output', type=Path, required=True)
    sync = commands.add_parser('sync-profile', help=t('identity_ui.cli.sync'))
    sync.add_argument('job_id', nargs='?')
    sync.add_argument('--mapping', type=Path)
    claim = commands.add_parser('profile-claim', help=t('identity_ui.cli.claim'))
    claim.add_argument('decision', choices=('issue', 'verify'))
    claim.add_argument('--actor')
    claim.add_argument('--curator', required=True)
    claim.add_argument('--provider', required=True)
    claim.add_argument('--subject', required=True)
    claim.add_argument('--reference', required=True)
    trajectory = commands.add_parser('trajectory', help=t('cli.help.trajectory'))
    trajectory.add_argument('--export', type=Path)
    inspect = commands.add_parser('inspect-trajectory', help=t('cli.help.inspect_trajectory'))
    inspect.add_argument('path', type=Path)
    inspect.add_argument('--branch')
    demo = commands.add_parser('trajectory-demo', help=t('cli.help.trajectory_demo'))
    demo.add_argument('scenario', choices=SCENARIOS, nargs='?', default='bilateral-logs')
    demo.add_argument('--export', type=Path)
    submit = commands.add_parser('submit', help=t('cli.help.submit'))
    submit.add_argument('--expected-version', type=int)
    show = commands.add_parser('show')
    show.add_argument('view', choices=['now', 'world', 'network', 'agreements', 'commitments', 'reservations', 'objectives', 'missions', 'log'], nargs='?', default='now')
    show.add_argument('--at', type=int)
    commands.add_parser('replay')
    serve = commands.add_parser('serve', help=t('cli.help.serve'))
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--data-dir', default='.commons-worlds')
    validate = commands.add_parser('validate-text', help=t('cli.help.validate_text'))
    validate.add_argument('--root', type=Path)
    supplied = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(supplied)
    if args.operation is None:
        args = parser.parse_args([*supplied,'play'])
    if args.operation == 'validate-text':
        from .validate_text import main as validate_text
        return validate_text(['--root', str(args.root)] if args.root else [])
    data_dir = Path(os.getenv('SADDLE_DATA_DIR',str(Path.home()/'.local/share/saddle-pathways'))).expanduser()
    explicit_db = args.db is not None
    args.db = str(Path(args.db).expanduser()) if args.db else str(data_dir/'commons.sqlite')
    try:
        store = SQLiteStore(args.db, CommonsGame)
        if args.operation == 'capture-notion':
            from .ecosystem_import import capture_snapshot, sibling_client
            secrets_path = args.protocol_project / '.streamlit/secrets.toml'
            configured = tomllib.loads(secrets_path.read_text()).get('notion', {}) if secrets_path.exists() else {}
            token = (os.getenv('PROTOHACK_NOTION_TOKEN') or configured.get('protohack_token')
                     or configured.get('api_key') or configured.get('token') or os.getenv('NOTION_TOKEN'))
            if not token:
                raise ValueError(t('cli.configure_protohack_notion_token_or'))
            mapping = json.loads(args.source_mapping.read_text())
            snapshot = capture_snapshot(sibling_client(args.protocol_project, token), mapping['sources'])
            # Do not overwrite an earlier reproducible observation.
            with args.output.open('x') as target:
                json.dump(snapshot, target, ensure_ascii=False, indent=2)
            args.output.chmod(0o600)
            print(t('cli.captured_read_only_ecosystem_snapshot'), args.output)
        elif args.operation == 'import-ecosystem':
            from .ecosystem_import import import_snapshot
            snapshot = json.loads(args.snapshot.read_text())
            print(json.dumps(store.transact(lambda game: import_snapshot(game, snapshot)), indent=2))
        elif args.operation == 'import-reconstruction-sources':
            from .ecosystem_import import import_reconstruction_sources
            document = json.loads(args.snapshot.read_text())
            print(json.dumps(store.transact(lambda game: import_reconstruction_sources(game, document)), indent=2))
        elif args.operation == 'import-montreal-network':
            from .montreal_sources import import_montreal_network, read_sources
            document = read_sources(args.connections, args.statements)
            identities = json.loads(args.identities.read_text()) if args.identities else None
            if args.dry_run:
                report = import_montreal_network(store.load(), document, identities=identities, dry_run=True)
            else:
                report = store.transact(lambda game: import_montreal_network(game, document, identities=identities))
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.operation == 'curator-access':
            from .curator_access import provision_curator
            result = store.transact(lambda game: provision_curator(
                game, args.actor, enabled=args.decision == 'grant', reference=args.reference))
            print(json.dumps(result, indent=2))
        elif args.operation == 'sync-profile':
            from .profile_sync import NotionProfiles, sync_one
            if args.job_id is None:
                jobs = store.load().get_world()['configuration'].get('profile-sync', {}).get('jobs', {})
                print(json.dumps({key: {field: job[field] for field in ('kind', 'actor_id', 'status')}
                                  for key, job in jobs.items() if job['status'] != 'synced'}, indent=2))
                return 0
            if args.mapping is None:
                raise ValueError(t('identity_ui.cli.mapping_required'))
            token = os.getenv('COMMONS_NOTION_WRITE_TOKEN')
            client = NotionProfiles(token, json.loads(args.mapping.read_text()))
            result = sync_one(store, args.job_id, client)
            print(json.dumps(result, indent=2))
            return 0 if result['status'] == 'synced' else 1
        elif args.operation == 'profile-claim':
            from .profile_claims import issue, verify
            context = dict(curator=args.curator, provider=args.provider, subject=args.subject, reference=args.reference)
            if args.decision == 'issue':
                result = store.transact(lambda game: issue(game, args.actor, **context))
            else:
                from getpass import getpass
                token = getpass(t('identity_ui.cli.token')) if sys.stdin.isatty() else sys.stdin.readline().strip()
                result = store.transact(lambda game: verify(game, token, **context))
            print(json.dumps(result, indent=2))
        elif args.operation == 'play':
            from .tui import Cancelled, Terminal, run_play
            primary = not (args.developer_ui or args.actor or args.mock_identities or args.hot_seat)
            if args.ui_trace_output and not primary:
                raise ValueError('ui_trace_output_requires_the_primary_reconstruction_interface')
            from .fullscreen import supported
            interactive_primary = primary and not args.line_mode and supported(sys.stdin,sys.stdout)
            if interactive_primary and args.scenario is None and not args.choose_world:
                args.scenario = 'montreal-commons' if not explicit_db else None
            splash_done = False
            multiple_saved_worlds = not explicit_db and len(list(data_dir.glob('*.sqlite'))) > 1
            if primary and (args.choose_world or args.scenario is None and (not store.path.exists() or multiple_saved_worlds)):
                from .play import PlayableTerminal
                chooser = PlayableTerminal(load_scenario('montreal-commons'),plain=args.plain)
                chooser.splash();splash_done=True
                choices = ['montreal-commons',*(name for name in SCENARIOS if name!='montreal-commons')]
                try:
                    selected = chooser.choose(t('cli.play.world_commons_is_the_default'),choices,
                        lambda name: t('cli.play.commons_montreal_ecosystem') if name=='montreal-commons' else load_scenario(name).get_world()['configuration']['world']['title']+t('cli.play.synthetic_fixture'))
                except (EOFError,Cancelled):
                    return 0
                args.scenario = selected
                if not explicit_db:
                    args.db = str(data_dir/('commons.sqlite' if selected=='montreal-commons' else selected+'.sqlite'))
                    store = SQLiteStore(args.db,CommonsGame)
            if store.path.exists():
                game = store.load()
                saved_scenario = game.get_world()['configuration']['world']['scenario']
                if args.scenario is not None and args.scenario != saved_scenario:
                    raise ValueError('world_scenario_mismatch_choose_another_db')
            else:
                selected = args.scenario
                if selected is None:
                    from .tui import Cancelled
                    chooser = Terminal(load_scenario())
                    try:
                        selected = chooser.choose(t('cli.play.saddle_pathways_select_a_world'), list(SCENARIOS))
                    except (Cancelled, EOFError):
                        return 0
                game = load_scenario(selected)
                if args.actor is not None and args.actor not in game.get_world()['actors']:
                    raise ValueError('unknown_actor')
                store.path.parent.mkdir(parents=True,exist_ok=True)
                install_missions(game)
                store.initialise(game)
            if args.mock_player and not args.mock_identities:
                raise ValueError('mock_identities_manifest_required')
            if args.mock_identities and (args.actor or args.hot_seat):
                raise ValueError('mock_bindings_use_sign_out_instead_of_hot_seat')
            provider = identity = None
            if args.mock_identities:
                from .identity import MockIdentityProvider
                provider = MockIdentityProvider(json.loads(args.mock_identities.read_text()))
                if args.mock_player:
                    identity = provider.sign_in(args.mock_player)
            if primary:
                from .fullscreen import run_fullscreen, supported
                trace=None
                if args.ui_trace_output:
                    if args.ui_trace_output.resolve()==store.path.resolve():
                        raise ValueError('ui_trace_and_world_paths_must_differ')
                    from game_gamer.transitions import TraceSession, jsonl_sink
                    trace=TraceSession(sink=jsonl_sink(args.ui_trace_output))
                if not args.line_mode and supported(sys.stdin, sys.stdout):
                    run_fullscreen(game,store=store,plain=args.plain,explore=args.explore,transition_trace=trace)
                    if trace is not None and trace.sink_errors:
                        raise ValueError(t('errors.ui_trace_output_failed'))
                    return 0
                if trace is not None:
                    from game_gamer.tui.viewport import LineViewport

                    from .fullscreen import FullScreenTerminal
                    FullScreenTerminal(game,store=store,plain=True,explore=args.explore,
                        viewport=LineViewport(sys.stdin,sys.stdout),transition_trace=trace).run()
                    if trace.sink_errors:raise ValueError(t('errors.ui_trace_output_failed'))
                    return 0
                from .play import PlayableTerminal
                terminal=PlayableTerminal(game,store=store,plain=args.plain,explore=args.explore)
                terminal.splash_done=splash_done
                terminal.run()
            else:
                run_play(game, actor=args.actor, store=store, hot_seat=args.hot_seat,
                         provider=provider, identity=identity, plain=args.plain, explore=args.explore)
        elif args.operation in {'trajectory', 'inspect-trajectory', 'trajectory-demo'}:
            from .trajectory import (
                load_trajectory_yaml,
                project_trajectory,
                reconstruct,
                simulate_branch,
                trajectory_yaml,
            )
            from .tui import render_trajectory
            if args.operation == 'inspect-trajectory':
                document = load_trajectory_yaml(args.path.read_text())
                render_trajectory(document, sys.stdout, branch_id=args.branch)
            elif args.operation == 'trajectory':
                document = project_trajectory(store.load())
                render_trajectory(document, sys.stdout)
            else:
                from .player import ActorSession
                game = load_scenario(args.scenario)
                script = demo_commands(args.scenario)
                session = ActorSession(game, script[0]['actor'], hot_seat=True)
                print(t('cli.saddle_pathways_explicit_synthetic_hot'))
                for command in script:
                    session.switch(command['actor'])
                    result = session.submit(command)
                    if not result['ok']:
                        raise ValueError(result['errors'])
                parent = next(entry['sequence'] for entry in game.project('log')
                              if entry['command'] and entry['command']['kind'] == 'amend')
                proposal = game.get_world()['configuration']['world']['proposal']
                original = game.get_world(), game.project('log')
                branches = []
                for kind in ('accept', 'reject'):
                    candidate = {'key': 'alternative-' + kind, 'kind': kind, 'actor': proposal['parties'][1],
                                 'agreement_id': proposal['id'], 'version': 2}
                    if kind == 'reject':
                        candidate['reason'] = 'Hypothetical disagreement with the proposed conditions.'
                    branches.append(simulate_branch(game, parent_sequence=parent, commands=[candidate], branch_id=kind))
                document = project_trajectory(game, branches=branches)
                imported = load_trajectory_yaml(trajectory_yaml(document))
                if imported['plan']['commons_trajectory'] != document['plan']['commons_trajectory']:
                    raise ValueError('trajectory_roundtrip_mismatch')
                if reconstruct(imported).get_world() != game.get_world() or original != (game.get_world(), game.project('log')):
                    raise ValueError('trajectory_state_mismatch')
                render_trajectory(document, sys.stdout)
                for branch in branches:
                    render_trajectory(document, sys.stdout, branch_id=branch['id'])
                print(t('cli.package_roundtrip_lossless_true'))
                print(t('cli.replay_consistent_true'))
                print(t('cli.alternatives_left_authoritative_world_unchanged'))
            output_path = getattr(args, 'export', None)
            if output_path is not None:
                with output_path.open('x') as target:
                    target.write(trajectory_yaml(document))
                print(t('cli.exported_read_only_package_document'), output_path)
        elif args.operation == 'start':
            if Path(args.db).exists():
                raise ValueError('world_exists_choose_another_db')
            store.path.parent.mkdir(parents=True,exist_ok=True)
            game = load_scenario(args.scenario)
            install_missions(game)
            store.initialise(game)
            print(t('cli.world_started', scenario=args.scenario, db=args.db))
        elif args.operation == 'demo':
            game = load_scenario(args.scenario)
            print(t('cli.the_commons_game_synthetic_demonstration', scenario=args.scenario))
            for command in demo_commands(args.scenario):
                result = game.submit(command)
                if not result['ok']:
                    raise ValueError(result['errors'])
                agreement = game.project('agreements')
                status = agreement[0]['status'] if agreement else 'gathering'
                print(f"{result['commit_id']}  {command['actor']:<12} {command['kind']:<20} {status}")
            print(t('cli.replay_identical'), game.replay().get_world() == game.get_world())
            print(t('cli.outcome'), game.project('objectives')[0]['status'])
        elif args.operation == 'submit':
            result = store.submit(json.load(sys.stdin), expected_version=args.expected_version)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return 0 if result['ok'] else 2
        elif args.operation == 'show':
            print(json.dumps(store.load().project(args.view, at=args.at), indent=2, ensure_ascii=False))
        elif args.operation == 'replay':
            game = store.load()
            print(json.dumps({'identical': game.get_world() == game.replay().get_world(),
                              'version': len(game.project('log'))}))
        else:
            from .server import serve
            serve(args.port, args.data_dir)
        return 0
    except KeyboardInterrupt:
        print(t('cli.interrupted_accepted_history_is_preserved'), file=sys.stderr)
        return 130
    except ModuleNotFoundError as error:
        if error.name != 'notion_client':
            raise
        print(t('cli.install_the_notion_extra_to'), file=sys.stderr)
        return 1
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(error_message(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
