"""Read-only measurements of the saved world; action writes use disposable copies."""
import argparse
import json
from pathlib import Path
from statistics import median
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.catalogue import people
from commons_game.fullscreen import FullScreenTerminal
from commons_game.player import ActorSession
from commons_game.reconstruction import exercise_projection
from game_gamer.projections.participants import ParticipantFilters


def measure(operation, samples):
    values = []
    for _ in range(samples):
        start = perf_counter()
        operation()
        values.append((perf_counter()-start)*1000)
    values.sort()
    return {'samples': samples, 'median_ms': round(median(values), 3),
            'p95_ms': round(values[int((samples-1)*.95)], 3), 'max_ms': round(values[-1], 3)}


def run(path, samples):
    store = SQLiteStore(path, CommonsGame)
    original = store.load()
    ui = FullScreenTerminal(original, store=store, viewport=None, plain=True, explore=True)
    ui.push('reconstruction')
    ui.width, ui.height = 144, 34
    ui.build_screen()
    directory = exercise_projection(ui)[1]
    roster = people(ui.world())
    actor = roster[0]['id']
    results = {'world': {'people': len(roster), 'actors': len(ui.world()['actors']),
                         'events': original.revision}, 'measurements': {}}
    measurements = results['measurements']

    def cursor():
        ui.refresh()
        ui.handle('down', ui.build_screen())
        ui.build_screen()

    measurements['arrow_frame'] = measure(cursor, samples)
    ui.route.region = 'profile'
    measurements['profile'] = measure(ui.build_screen, samples)
    measurements['facet_values'] = measure(lambda: directory.facet_values('offers', ParticipantFilters(), reference=actor), samples)
    ui.route.region = 'network'
    measurements['neighbourhood'] = measure(ui.build_screen, samples)
    ui.push('reconstruction_graph', ui.route.target, graph_view='collective')
    ui.route.region = 'network'
    measurements['collective_graph'] = measure(ui.build_screen, samples)
    with tempfile.TemporaryDirectory(prefix='commons-benchmark-') as temporary:
        copies = []
        for index in range(min(samples, 5)):
            copy = SQLiteStore(Path(temporary)/f'{index}.sqlite', CommonsGame)
            copy.initialise(original)
            copy.path.chmod(0o600)
            copies.append(copy)
        values = []
        for index, copy in enumerate(copies):
            game = copy.load()
            session = ActorSession(game, actor, store=copy)
            start = perf_counter()
            result = session.submit({'key': f'bench-{index}', 'kind': 'recall_connection',
                                     'target_id': roster[1]['id'], 'context_id': 'benchmark-only'},
                                    expected_version=game.revision)
            assert result['ok'], result
            restored = copy.load()
            assert restored.revision == game.revision+1
            values.append((perf_counter()-start)*1000)
        values.sort()
        measurements['sqlite_submit_and_refresh'] = {
            'samples': len(values), 'median_ms': round(median(values), 3),
            'p95_ms': round(values[int((len(values)-1)*.95)], 3), 'max_ms': round(values[-1], 3)}
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=30)
    args = parser.parse_args()
    print(json.dumps(run(args.db, args.samples), indent=2))
