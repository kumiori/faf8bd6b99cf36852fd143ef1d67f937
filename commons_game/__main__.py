"""Terminal entry point; the same commands are available through the HTTP adapter."""
import argparse
import json
from pathlib import Path
import sys
from commons_engine.store import SQLiteStore
from .engine import CommonsGame
from .scenario import SCENARIOS, load_scenario, demo_commands


def main(argv=None):
    parser = argparse.ArgumentParser(description='The Commons Game · V0.1')
    parser.add_argument('--db', default='.commons.sqlite')
    commands = parser.add_subparsers(dest='operation', required=True)
    for name in ('start', 'demo'):
        command = commands.add_parser(name)
        command.add_argument('scenario', choices=SCENARIOS, nargs='?', default='bilateral-logs')
    submit = commands.add_parser('submit', help='Submit a JSON command from stdin')
    submit.add_argument('--expected-version', type=int)
    show = commands.add_parser('show')
    show.add_argument('view', choices=['now', 'world', 'network', 'agreements', 'commitments', 'reservations', 'objectives', 'log'], nargs='?', default='now')
    show.add_argument('--at', type=int)
    commands.add_parser('replay')
    serve = commands.add_parser('serve')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--data-dir', default='.commons-worlds')
    args = parser.parse_args(argv)
    try:
        store = SQLiteStore(args.db, CommonsGame)
        if args.operation == 'start':
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
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
