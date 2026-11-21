"""One-time profile invitations redeemed through the trusted verification boundary."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from game_gamer.runtime.curation import canonical, profile

from .engine import digest, text
from .model import require
from .source_review import notion_identity

CLAIMS = 'profile-claims'


def _curator(world, actor):
    require(actor in world['actors'] and canonical(world, actor) == actor
            and profile(world, actor)['status'] == 'active'
            and 'curator' in world['actors'][actor]['roles'], 'curator_required')


def issue(game, target, *, curator, provider, subject, reference, now=None):
    now = now or datetime.now(timezone.utc)
    before = game.get_world()
    _curator(before, curator)
    identity = digest([text(provider), text(subject)])
    require(target in before['actors'] and profile(before, target)['status'] == 'provisional'
            and canonical(before, target) == target, 'provisional_profile_required')
    reference = text(reference, 'curator_reference_required')
    require(len(reference) <= 2000, 'curator_reference_required')
    after = deepcopy(before)
    claims = after['configuration'].setdefault(CLAIMS, {'id': CLAIMS, 'status': 'active', 'invitations': {}})['invitations']
    require(not any(row['status'] == 'verified' and row['identity'] == identity for row in claims.values()),
            'verified_identity_already_bound')
    for row in claims.values():
        if row['actor_id'] == target and row['status'] == 'issued':
            row['status'] = 'superseded'
    token = token_urlsafe(32)
    ident = 'claim:'+digest(token)
    expires = (now + timedelta(days=7)).isoformat()
    claims[ident] = {'actor_id': target, 'identity': identity, 'provider': provider.strip(),
                     'status': 'issued', 'issued_by': curator, 'issued_at': now.isoformat(),
                     'expires_at': expires, 'issue_reference': reference}
    game._commit(before, after, 'profile_claim.invited', actor=curator)
    return {'ok': True, 'actor_id': target, 'token': token, 'expires_at': expires}


def verify(game, token, *, curator, provider, subject, reference, now=None):
    now = now or datetime.now(timezone.utc)
    before = game.get_world()
    _curator(before, curator)
    ident = 'claim:'+digest(text(token))
    invitations = before['configuration'].get(CLAIMS, {}).get('invitations', {})
    record = invitations.get(ident)
    require(record and record['status'] == 'issued' and now < datetime.fromisoformat(record['expires_at']),
            'profile_claim_unavailable')
    identity = digest([text(provider), text(subject)])
    require(identity == record['identity'], 'profile_claim_identity_mismatch')
    require(not any(row['status'] == 'verified' and row['identity'] == identity for row in invitations.values()),
            'verified_identity_already_bound')
    reference = text(reference, 'verified_identity_reference_required')
    require(len(reference) <= 2000, 'verified_identity_reference_required')
    target = record['actor_id']
    require(profile(before, target)['status'] == 'provisional' and canonical(before, target) == target,
            'provisional_profile_required')
    require(notion_identity(before, target), 'provisional_profile_sync_required')
    after = deepcopy(before)
    after['configuration'][CLAIMS]['invitations'][ident].update(
        status='verified', verified_by=curator, verified_at=now.isoformat(), verification_reference=reference,
    )
    after['actors'][target]['status'] = 'active'
    game._commit(before, after, 'profile_claim.verified', actor=curator)
    return {'ok': True, 'actor_id': target, 'status': 'verified'}
