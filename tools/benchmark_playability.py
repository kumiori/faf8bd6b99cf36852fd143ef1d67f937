"""Measure read-only terminal frames. Results contain timings and counts only."""
import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from commons_engine.store import SQLiteStore
from commons_game import CommonsGame
from commons_game.fullscreen import FullScreenTerminal


def benchmark(path, samples=20):
    store = SQLiteStore(path, CommonsGame)
    ui = FullScreenTerminal(store.load(), store=store, viewport=None, plain=True, explore=True)
    ui.push('reconstruction')
    ui.width, ui.height = 144, 34
    ui.build_screen()
    timings = []
    for _ in range(samples):
        start = perf_counter()
        ui.refresh()
        ui.handle('down', ui.build_screen())
        ui.build_screen()
        timings.append((perf_counter()-start)*1000)
    return {'operation': 'revision check + selection + two screen builds', 'samples': samples,
            'median_ms': round(statistics.median(timings), 3),
            'p95_ms': round(sorted(timings)[int((samples-1)*.95)], 3),
            'max_ms': round(max(timings), 3)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--samples', type=int, default=20)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.db, args.samples), indent=2))
