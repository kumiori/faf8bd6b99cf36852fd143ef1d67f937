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
from . import source_review
from .model import require


class CommonsGame(CollectiveEngine):
    extension_fields = source_review.FIELDS
    fields = {**FIELDS, **extension_fields}

    def _prepare_extension(self, world, command, **context):
        source_review.prepare(world, command, **context)

    def _prepare(self, command):
        kind = command['kind']
        world, action_id, summary = super()._prepare(command)
        if kind == 'correct_profile':
            require(not source_review.notion_identity(self._world, command['target_id']),
                    'profile_review_required')
        if kind == 'review_curation_request' and command['decision'] == 'approve':
            from .profile_sync import stage_approval
            stage_approval(world, command['request_id'])
        return world, action_id, summary

    def _network(self, world):
        return network(world)

    def derive_possibilities(self, world=None):
        return potential_complementarities(world if world is not None else self.get_world())
