"""Identity-provider boundary. Only an explicit simulation provider ships here."""
from copy import deepcopy
from dataclasses import dataclass
from typing import Protocol

from .engine import digest, text
from .model import require


@dataclass(frozen=True)
class PlayerIdentity:
    provider: str
    subject: str
    label: str
    mode: str = 'simulation'
    authenticated: bool = False


@dataclass(frozen=True)
class ActorBinding:
    provider: str
    subject: str
    actor_id: str
    status: str
    authority: str = 'personal'


class IdentityProvider(Protocol):
    def sign_in(self, subject: str) -> PlayerIdentity: ...
    def bindings(self, identity: PlayerIdentity) -> list[ActorBinding]: ...
    def permits(self, identity: PlayerIdentity, binding: ActorBinding, actor: dict) -> bool: ...


class MockIdentityProvider:
    """Explicit local grants, never claims, affiliations or Notion credentials.

    The manifest is trusted local development configuration, not a login service.
    Selecting its subject simulates sign-in. Nothing here authenticates a person.
    """
    name = 'local_mock'

    def __init__(self, manifest):
        require(manifest.get('mode') == 'simulation', 'simulation_manifest_required')
        self.players = deepcopy(manifest.get('players', {}))
        for subject, player in self.players.items():
            text(subject); text(player['label'])
            for binding in player.get('bindings', []):
                text(binding['actor_id'])
                require(binding.get('authority', 'personal') in {'personal', 'organisation'}, 'invalid_binding_authority')

    def sign_in(self, subject):
        require(subject in self.players, 'unknown_mock_player')
        return PlayerIdentity(self.name, subject, self.players[subject]['label'])

    def register_guest(self, subject, label):
        """An unbound mock subject can request a profile; it gains no actor role."""
        text(subject); text(label)
        require(subject not in self.players, 'mock_player_already_exists')
        self.players[subject] = {'label': label, 'bindings': []}
        return self.sign_in(subject)

    def bindings(self, identity):
        require(identity == self.sign_in(identity.subject), 'identity_provider_mismatch')
        return [ActorBinding(self.name, identity.subject, item['actor_id'],
                             'verified_simulation', item.get('authority', 'personal'))
                for item in self.players[identity.subject].get('bindings', [])]

    def permits(self, identity, binding, actor):
        return (binding in self.bindings(identity) and binding.actor_id == actor['id']
                and (actor['kind'] != 'organisation' or binding.authority == 'organisation'))


def request_binding(game, identity, *, actor_id=None, profile_label=None):
    """Record a pending claim only. Repeated requests never duplicate actors."""
    require(identity.mode == 'simulation' and not identity.authenticated, 'live_identity_unavailable')
    before = game.get_world()
    if actor_id is not None:
        require(actor_id in before['actors'], 'unknown_actor')
    else:
        text(profile_label)
    request_id = 'binding-request:' + digest([identity.provider, identity.subject, actor_id, profile_label])[:24]
    prior = before['configuration'].get(request_id)
    if prior:
        return {'ok': True, 'request': deepcopy(prior), 'duplicate': True}
    after = deepcopy(before)
    record = {'id': request_id, 'status': 'pending', 'provider': identity.provider,
              'subject': identity.subject, 'actor_id': actor_id, 'profile_label': profile_label,
              'mode': 'simulation', 'requested_at': game._timestamp()}
    after['configuration'][request_id] = record
    game._commit(before, after, 'identity_binding.requested')
    return {'ok': True, 'request': deepcopy(record), 'duplicate': False}
