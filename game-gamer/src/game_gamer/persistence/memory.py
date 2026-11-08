"""In-process reference store for simulations."""
from ..runtime.engine import CollectiveEngine


class MemoryStore:
    def __init__(self, game: CollectiveEngine):
        self._game = game.replay()

    def revision(self):
        with self._game._lock:
            return self._game.revision

    def load(self):
        return self._game.snapshot()

    def submit(self, command, *, expected_version=None):
        with self._game._lock:
            result = self._game.submit(command, expected_version=expected_version)
            return {**result, 'version': len(self._game._log)}
