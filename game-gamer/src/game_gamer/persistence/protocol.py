"""Store contract. Submission compares and commits under the same authority."""
from typing import Protocol

from ..runtime.engine import CollectiveEngine


class CollectiveStore(Protocol):
    def load(self) -> CollectiveEngine:
        """Return a detached engine at one committed history prefix."""
        ...

    def submit(self, command: dict, *, expected_version: int | None = None) -> dict:
        """Atomically validate the command and append any accepted event."""
        ...
