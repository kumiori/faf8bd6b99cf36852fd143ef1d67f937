"""Entry point for the optional Game-Gamer terminal."""
import argparse
import json
from pathlib import Path
import sys

from . import Collective, DomainError, SimulationBinding


def main(argv=None):
    parser = argparse.ArgumentParser(prog='game-gamer')
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Read-only developer introspection')
    inspections = inspect.add_subparsers(dest='inspection', required=True)
    decisions = inspections.add_parser('decisions', help='Extract and audit the implemented decision graph')
    decisions.add_argument('--format', choices=['json', 'mermaid', 'dot'], default='json')
    decisions.add_argument('--output', type=Path)
    decisions.add_argument('--audit', action='store_true')
    decisions.add_argument('--audit-output', type=Path)
    decisions.add_argument('--coverage', type=Path, help='Observed transition coverage JSON')
    decisions.add_argument('--exceptions', type=Path, help='Documented audit exceptions JSON')
    decisions.add_argument('--interface', choices=['auto', 'terminal', 'commons', 'none'], default='auto')
    decisions.add_argument('--scope', help='Scope name or stable node ID prefix')
    decisions.add_argument('--level', choices=['navigation', 'decision', 'state'])
    decisions.add_argument('--world', type=Path, help='Portable world JSON or exported history JSON')
    decisions.add_argument('--db', type=Path, help='Read an existing saved world; requires --world for scope')
    decisions.add_argument('--actor')
    decisions.add_argument('--contextual', action='store_true')
    decisions.add_argument('--limit', type=int, default=100, help='Maximum contextual choices per action')
    decisions.add_argument('--diff', type=Path, nargs=2, metavar=('PREVIOUS', 'CURRENT'))
    decisions.add_argument('--view',choices=['overview','navigation','decisions','lifecycle'])
    decisions.add_argument('--filter',action='append',default=[],choices=['unmapped','missing-recovery','untested','uninstrumented','unresolved-dynamic'])
    decisions.add_argument('--inventory-output',type=Path)
    decisions.add_argument('--transition-evidence',type=Path)
    decisions.add_argument('--release-gate',action='store_true')
    decisions.add_argument('--release-output',type=Path)
    decisions.add_argument('--responsiveness',type=Path)
    decisions.add_argument('--max-p95-ms',type=float,default=100)
    play = commands.add_parser('play', help='Run a shared simulation in the terminal')
    play.add_argument('definition', type=Path, help='Portable world JSON')
    play.add_argument('--db', type=Path, help='Saved simulation, default WORLD.sqlite beside the definition')
    play.add_argument('--actor', help='Start in this simulated role')
    play.add_argument('--line-mode', action='store_true', help='Use the scriptable line viewport')
    play.add_argument('--plain', action='store_true', help='Use portable ASCII and omit colours')
    args = parser.parse_args(argv)
    if args.command == 'inspect':
        try:
            return inspect_decisions(args, parser)
        except (DomainError, OSError, ValueError, KeyError, TypeError) as error:
            parser.error(str(error))
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


def inspect_decisions(args, parser):
    from .inspection import canonical_json, extract_decisions
    from .inspection.audit import audit_graph, audit_text
    from .inspection.export import diff_graphs, export_graph

    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    inputs = [p for p in (args.world, args.db, args.coverage, args.exceptions,args.transition_evidence,args.responsiveness, *(args.diff or [])) if p]
    outputs = [p for p in (args.output, args.audit_output,args.inventory_output,args.release_output) if p]
    if any(output.resolve() == input.resolve() for output in outputs for input in inputs):
        parser.error('Inspection outputs must not overwrite inputs')
    if len({p.resolve() for p in outputs}) != len(outputs):
        parser.error('Graph and audit outputs must be distinct')
    if args.diff:
        result = canonical_json(diff_graphs(*(read(path) for path in args.diff)))
        if args.output:
            args.output.write_text(result, encoding='utf-8')
        else:
            print(result, end='')
        return 0
    if args.audit_output and not args.audit:
        parser.error('--audit-output requires --audit')
    if args.inventory_output and not args.audit:
        parser.error('--inventory-output requires --audit')
    if args.release_output and not args.release_gate:
        parser.error('--release-output requires --release-gate')
    if args.release_gate and (not args.transition_evidence or args.scope not in {'exercise.reconstruct','reconstruction'}):
        parser.error('--release-gate requires --scope exercise.reconstruct and --transition-evidence')
    if args.contextual and (not args.world or not args.actor):
        parser.error('--contextual requires --world and --actor')
    if not args.contextual and any((args.world, args.actor, args.db)):
        parser.error('--world, --actor and --db require --contextual')
    game = binding = None
    if args.contextual:
        definition = read(args.world)
        if args.db:
            # Snapshot the existing log through its read-only SQLite connection;
            # subsequent availability evaluation uses detached memory only.
            from .persistence.log import load_log
            from .persistence.memory import MemoryStore
            from .runtime.engine import CollectiveEngine
            game = Collective(MemoryStore(CollectiveEngine.from_log(load_log(args.db))))
            if game.scope_id != definition['scope_id']:
                raise DomainError('scope_mismatch')
        elif 'history_digest' in definition:
            game = Collective.from_history(definition)
        else:
            game = Collective.start(definition)
        actor = game.project('world')['actors'].get(args.actor)
        if not actor:
            raise DomainError('unknown_actor')
        binding = SimulationBinding(scope_id=game.scope_id, actor_id=args.actor,
                                    authority='organisation' if actor['kind'] == 'organisation' else 'personal')
    graph = extract_decisions(interfaces=args.interface, collective=game, binding=binding, limit=args.limit,
                              coverage=read(args.coverage) if args.coverage else None,
                              scope=args.scope, level=args.level,
                              transition_evidence=read(args.transition_evidence) if args.transition_evidence else None)
    canonical_graph=graph
    report=audit_graph(graph,exceptions=read(args.exceptions) if args.exceptions else ()) if args.audit else None
    gate=None
    if args.release_gate:
        from .inspection.release import release_gate
        gate=release_gate(graph,read(args.transition_evidence),
                          responsiveness=read(args.responsiveness) if args.responsiveness else None,
                          max_p95_ms=args.max_p95_ms)
        if args.release_output:
            args.release_output.write_text(canonical_json(gate),encoding='utf-8')
    if args.view or args.filter:
        from .inspection.views import project_view
        graph=project_view(graph,args.view or 'decisions',filters=args.filter)
    if args.output:
        args.output.write_text(export_graph(graph, args.format), encoding='utf-8')
    elif not args.audit and not args.release_gate:
        print(export_graph(graph, args.format), end='')
    if args.audit:
        print(audit_text(report), end='')
        if args.audit_output:
            args.audit_output.write_text(canonical_json(report), encoding='utf-8')
        if args.inventory_output:
            from .inspection.diagnostics import diagnostic_inventory
            # Inventory refers to the canonical graph, not a filtered view.
            args.inventory_output.write_text(canonical_json(diagnostic_inventory(canonical_graph,report)),encoding='utf-8')
    if gate is not None:
        print('RECONSTRUCTION RELEASE GATE: '+('PASS' if gate['passed'] else 'BLOCKED'))
        return 0 if gate['passed'] and (report is None or report['passed']) else 1
    if report is not None:
        return 0 if report['passed'] else 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
