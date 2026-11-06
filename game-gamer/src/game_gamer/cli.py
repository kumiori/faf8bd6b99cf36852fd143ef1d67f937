"""Entry point for the optional Game-Gamer terminal."""
import argparse
import json
from pathlib import Path
import sys

from . import Collective, DomainError, SimulationBinding


def main(argv=None):
    parser = argparse.ArgumentParser(prog='game-gamer')
    commands = parser.add_subparsers(dest='command', required=True)
    play = commands.add_parser('play', help='Run a shared simulation in the terminal')
    play.add_argument('definition', type=Path, help='Portable world JSON')
    play.add_argument('--db', type=Path, help='Saved simulation, default WORLD.sqlite beside the definition')
    play.add_argument('--actor', help='Start in this simulated role')
    play.add_argument('--line-mode', action='store_true', help='Use the scriptable line viewport')
    play.add_argument('--plain', action='store_true', help='Use portable ASCII and omit colours')
    args = parser.parse_args(argv)
    try:
        from .tui import TerminalGame
        from .tui.viewport import LineViewport
    except ModuleNotFoundError as error:
        if error.name != 'wcwidth':
            raise
        parser.error('Install game-gamer[tui] to play in the terminal.')
    try:
        definition = json.loads(args.definition.read_text(encoding='utf-8'))
        db = args.db if args.db is not None else args.definition.with_suffix('.sqlite')
        game = Collective.open(db, scope_id=definition['scope_id']) if db.exists() else Collective.start(definition, path=db)
        binding = None
        if args.actor:
            actor = game.project('world')['actors'].get(args.actor)
            if not actor or actor['status'] != 'active':
                raise DomainError('unknown_actor')
            binding = SimulationBinding(scope_id=game.scope_id, actor_id=args.actor,
                                        authority='organisation' if actor['kind'] == 'organisation' else 'personal')
        viewport = LineViewport(sys.stdin, sys.stdout) if args.line_mode else None
        TerminalGame(collective=game, binding=binding, viewport=viewport, plain=args.plain or viewport is not None,
                     hot_seat=True).run()
    except (DomainError, OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
