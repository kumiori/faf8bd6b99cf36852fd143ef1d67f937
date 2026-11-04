"""Subtle Pathways terminal entry point; domain rules stay in the shared engine."""
import argparse
import json
from pathlib import Path
import sys
from commons_engine.store import SQLiteStore
from .engine import CommonsGame
from .scenario import SCENARIOS, load_scenario, demo_commands


def main(argv=None):
    parser = argparse.ArgumentParser(description='Subtle Pathways / The Commons Game · V0.1')
    parser.add_argument('--db', default='.commons.sqlite')
    commands = parser.add_subparsers(dest='operation', required=True)
    for name in ('start', 'demo'):
        command = commands.add_parser(name)
        command.add_argument('scenario', choices=SCENARIOS, nargs='?', default='bilateral-logs')
    play = commands.add_parser('play', help='Actor-bound terminal laboratory')
    play.add_argument('scenario', choices=SCENARIOS, nargs='?')
    play.add_argument('--actor', help='Active local actor ID; identity selection is not authentication')
    play.add_argument('--hot-seat', action='store_true', help='Explicitly enable development identity switching')
    trajectory = commands.add_parser('trajectory', help='Read-only native trajectory-package projection')
    trajectory.add_argument('--export', type=Path)
    inspect = commands.add_parser('inspect-trajectory', help='Inspect exported package YAML without loading it into a live world')
    inspect.add_argument('path', type=Path)
    inspect.add_argument('--branch')
    demo = commands.add_parser('trajectory-demo', help='Synthetic, explicitly hot-seat end-to-end integration')
    demo.add_argument('scenario', choices=SCENARIOS, nargs='?', default='bilateral-logs')
    demo.add_argument('--export', type=Path)
    submit = commands.add_parser('submit', help='Submit a JSON command from stdin')
    submit.add_argument('--expected-version', type=int)
    show = commands.add_parser('show')
    show.add_argument('view', choices=['now', 'world', 'network', 'agreements', 'commitments', 'reservations', 'objectives', 'log'], nargs='?', default='now')
    show.add_argument('--at', type=int)
    commands.add_parser('replay')
    serve = commands.add_parser('serve', help='Legacy browser scaffold; not required for terminal development')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--data-dir', default='.commons-worlds')
    args = parser.parse_args(argv)
    try:
        store = SQLiteStore(args.db, CommonsGame)
        if args.operation == 'play':
            from .tui import Terminal, run_play
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
                        selected = chooser.choose('SUBTLE PATHWAYS / Select a synthetic scenario:', list(SCENARIOS))
                    except (Cancelled, EOFError):
                        return 0
                game = load_scenario(selected)
                if args.actor is not None and args.actor not in game.get_world()['actors']:
                    raise ValueError('unknown_actor')
                store.initialise(game)
            run_play(game, actor=args.actor, store=store, hot_seat=args.hot_seat)
        elif args.operation in {'trajectory', 'inspect-trajectory', 'trajectory-demo'}:
            from .trajectory import (project_trajectory, reconstruct, simulate_branch,
                                     trajectory_yaml, load_trajectory_yaml)
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
                print('SUBTLE PATHWAYS / EXPLICIT SYNTHETIC HOT-SEAT DEMONSTRATION')
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
                print('PACKAGE ROUNDTRIP LOSSLESS: True')
                print('REPLAY CONSISTENT: True')
                print('ALTERNATIVES LEFT AUTHORITATIVE WORLD UNCHANGED: True')
            output_path = getattr(args, 'export', None)
            if output_path is not None:
                with output_path.open('x') as target:
                    target.write(trajectory_yaml(document))
                print('Exported read-only package document:', output_path)
        elif args.operation == 'start':
            if Path(args.db).exists():
                raise ValueError('world_exists_choose_another_db')
            store.initialise(load_scenario(args.scenario))
            print(f'World started: {args.scenario} · {args.db}')
        elif args.operation == 'demo':
            game = load_scenario(args.scenario)
            print(f'THE COMMONS GAME · {args.scenario} · synthetic demonstration')
            for command in demo_commands(args.scenario):
                result = game.submit(command)
                if not result['ok']:
                    raise ValueError(result['errors'])
                agreement = game.project('agreements')
                status = agreement[0]['status'] if agreement else 'gathering'
                print(f"{result['commit_id']}  {command['actor']:<12} {command['kind']:<20} {status}")
            print('REPLAY IDENTICAL:', game.replay().get_world() == game.get_world())
            print('OUTCOME:', game.project('objectives')[0]['status'])
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
        print('Interrupted. Accepted history is preserved.', file=sys.stderr)
        return 130
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
