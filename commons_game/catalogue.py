"""Read-only player catalogue and explicitly issued development simulation roles."""
from uuid import uuid4
from game_gamer.runtime.curation import canonical, profile, visible

from .identity import ActorBinding, PlayerIdentity
from .model import require
from .presentation import display_label, folded, person_labels
from .source_review import notion_identity


def affiliations(world, actor_id):
    correction = profile(world, actor_id).get('profile_organisation') if actor_id in world['actors'] else None
    if correction is not None:
        return [correction] if correction else []
    return [profile(world, canonical(world, r['target_id']))['label'] for r in world['relationships'].values()
            if r['kind'] == 'affiliated_with' and r['source_id'] == actor_id and r['target_id'] in world['actors']]


def people(world, *, search='', organisation='', development=False):
    imported = [a for a in world['actors'].values() if a['kind']=='person'
                and a['status']=='active' and notion_identity(world, a['id'])]
    if development:
        actors=list(world['actors'].values())
    elif imported or not world['configuration']['world'].get('synthetic',True):
        actors=imported
    else:
        actors=[a for a in world['actors'].values() if a['kind']=='person' and a['status']=='active']
    actors=[profile(world, a['id']) for a in actors if development or visible(world, a['id'])]
    labels=person_labels(world)
    actors=[{**a,'display_name':labels[a['id']]} if a['id'] in labels else {**a} for a in actors]
    return sorted([a for a in actors if a['status']=='active' and folded(search) in folded(display_label(a))
                   and (not organisation or any(folded(organisation) in folded(label) for label in affiliations(world,a['id'])))],
                  key=lambda a:(folded(display_label({k:v for k,v in a.items() if k!='display_name'})),a['id']))


class SimulationAuthority:
    """An explicit local role-selection act, not an attribute imported from Notion.

    The provider can only issue unauthenticated, simulation-labelled roles. It
    cannot be used to establish identity, organisational authority or real consent.
    """
    name = 'development_simulation'

    def __init__(self):
        self.issued = {}

    def assume(self, actor, *, organisation_confirmed=False):
        require(actor['status']=='active','inactive_actor')
        require(actor['kind']!='organisation' or organisation_confirmed,'explicit_organisation_simulation_required')
        identity = PlayerIdentity(self.name,'simulation-'+uuid4().hex,'Simulating '+display_label(actor))
        binding = ActorBinding(self.name,identity.subject,actor['id'],'verified_simulation',
                               'organisation' if actor['kind']=='organisation' else 'personal')
        self.issued[identity.subject] = identity,binding
        return identity,binding

    def sign_in(self, subject):
        require(subject in self.issued,'unknown_simulation_session')
        return self.issued[subject][0]

    def bindings(self, identity):
        require(self.sign_in(identity.subject)==identity,'identity_provider_mismatch')
        return [self.issued[identity.subject][1]]

    def permits(self, identity,binding,actor):
        return (identity.mode=='simulation' and not identity.authenticated and binding in self.bindings(identity)
                and binding.actor_id==actor['id'] and (actor['kind']!='organisation' or binding.authority=='organisation'))
