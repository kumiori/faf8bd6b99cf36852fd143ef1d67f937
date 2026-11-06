"""Saddle Pathways adapter over the shared collective engine."""
from game_gamer.runtime.engine import (
    FIELDS as FIELDS,
    TERMINAL as TERMINAL,
    CollectiveEngine,
    digest as digest,
    instant as instant,
    text as text,
)
from .projections import network, potential_complementarities


class CommonsGame(CollectiveEngine):
    def _network(self, world):
        return network(world)

    def derive_possibilities(self, world=None):
        return potential_complementarities(world if world is not None else self.get_world())
