"""Commons policies and projections registered through the public contract."""
from game_gamer import CommandDefinition, Extension, PolicyHook, register_extension

from . import source_review
from .model import require
from .projections import network, potential_complementarities


def profile_policy(world, command, **context):
    if command['kind'] == 'correct_profile':
        require(not source_review.notion_identity(world, command['target_id']), 'profile_review_required')


def profile_approval(world, command, **context):
    if command['kind'] == 'review_curation_request' and command['decision'] == 'approve':
        from .profile_sync import stage_approval
        stage_approval(world, command['request_id'])


COMMONS_EXTENSION = register_extension(Extension(
    id='commons.application', version='1.0.0',
    commands={name: CommandDefinition(required=required, optional=optional,
                                      handler=source_review.prepare, target_field='source_id')
              for name, (required, optional) in source_review.FIELDS.items()},
    policies=(PolicyHook(after=profile_policy), PolicyHook(after=profile_approval)),
    projections={'network': network, 'possibilities': potential_complementarities},
))
