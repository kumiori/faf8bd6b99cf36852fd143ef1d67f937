"""Commons application construction over Game-Gamer's public extension contract."""
from game_gamer import CollectiveEngine
from game_gamer.runtime.engine import (
    FIELDS as FIELDS,
    TERMINAL as TERMINAL,
    digest as digest,
    instant as instant,
    text as text,
)
from .extensions import COMMONS_EXTENSION


class CommonsGame(CollectiveEngine):
    """Preserve the existing constructor and save loader for Commons callers."""
    def __init__(self, *, extension=None):
        super().__init__(extension=extension or COMMONS_EXTENSION)
