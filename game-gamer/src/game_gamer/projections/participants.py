"""Directory over detached actor and questionnaire records."""
from collections import defaultdict
from dataclasses import dataclass, replace
from ..runtime.curation import canonical, profile as corrected_profile, visible
import unicodedata


def _fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold())
                   if not unicodedata.combining(c))


@dataclass(frozen=True)
class ParticipantProfile:
    id: str
    name: str
    actor_type: str
    organisations: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    motivation: str | None = None
    offers: tuple[str, ...] = ()
    needs: tuple[str, ...] = ()
    offers_state: str | None = None
    needs_state: str | None = None
    domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParticipantFilters:
    field: str = 'name'
    query: str = ''
    facets: tuple[tuple[str, tuple[str, ...]], ...] = ()


FILTER_FIELDS = ('name', 'organisations', 'actor_type', 'roles', 'motivation', 'offers',
                 'needs', 'connected', 'not_connected', 'neighbourhood')
SORT_FIELDS = ('name', 'organisation', 'connections', 'shared_offers', 'shared_needs', 'recent')


class ParticipantDirectory:
    def __init__(self, world, *, actor_ids=None, labels=None, reconstruction=(), context_id=None, questionnaire=None):
        actors = {key: corrected_profile(world, key) for key in world['actors']}
        labels = labels or {}
        questionnaire = questionnaire or {}
        states = defaultdict(dict)
        organisations, offers, needs = (defaultdict(set) for _ in range(3))
        for relation in world['relationships'].values():
            if (relation['kind'] == 'affiliated_with' and relation['status'] != 'inferred'
                    and actors.get(relation['target_id'], {}).get('kind') == 'organisation'):
                organisations[canonical(world, relation['source_id'])].add(actors[canonical(world, relation['target_id'])]['label'])
        for table, values in (('capacities', offers), ('needs', needs)):
            current = questionnaire.get(table, {})
            for actor_id, observation in current.items():
                values[canonical(world, actor_id)].update(observation['domains'])
                states[table][canonical(world, actor_id)] = observation['state']
            for item in world[table].values():
                actor_id = canonical(world, item['actor_id'])
                superseded = actor_id in current and item.get('provenance', {}).get('kind') != 'player_declaration'
                if item['status'] in {'reported', 'verified'} and not superseded:
                    values[actor_id].add(item['domain'])
        statements = defaultdict(set)
        for record in world['evidence'].values():
            if record['kind'] == 'participant_statement' and (context_id is None or record['context_id'] == context_id):
                statements[record['actor_id']].add(record['statement'])
        self.profiles = {}
        for key, actor in actors.items():
            if actor['status'] != 'active' or not visible(world, key) or (actor_ids is not None and key not in actor_ids):
                continue
            roles = tuple(actor.get('roles', []))
            if 'profile_role' in actor:
                roles = (actor['profile_role'],) if actor['profile_role'] else ()
            motivation = '\n'.join(sorted(statements[key])) or None
            if 'motivation' in actor:
                motivation = actor['motivation'] or None
            organisation = ((actor['profile_organisation'],) if actor['profile_organisation'] else ()) if 'profile_organisation' in actor else tuple(sorted(organisations[key], key=_fold))
            self.profiles[key] = ParticipantProfile(
                id=key, name=labels.get(key, actor['label']), actor_type=actor['kind'],
                organisations=organisation, roles=roles,
                motivation=motivation, offers=tuple(actor.get('profile_offers', sorted(offers[key], key=_fold))),
                needs=tuple(actor.get('profile_needs', sorted(needs[key], key=_fold))),
                offers_state='answered' if 'profile_offers' in actor else states['capacities'].get(key),
                needs_state='answered' if 'profile_needs' in actor else states['needs'].get(key),
                domains=tuple(actor.get('profile_domains', ())))
        self.recalled_by = defaultdict(set)
        for record in world['relationships'].values():
            if record['kind'] == 'recollection_claim' and record['status'] != 'retracted' and (
                    context_id is None or record['context_id'] == context_id):
                source, target = canonical(world, record['source_id']), canonical(world, record['target_id'])
                if source != target:
                    self.recalled_by[source].add(target)
        self.neighbours = defaultdict(set)
        self.recent = defaultdict(int)
        for edge in reconstruction:
            if edge['layer'] not in {'recollection', 'corroborated', 'disputed_recollection'}:
                continue
            source, target = edge['source_id'], edge['target_id']
            if source not in self.profiles or target not in self.profiles:
                continue
            self.neighbours[source].add(target)
            self.neighbours[target].add(source)
            latest = max(int(ref.rsplit('_', 1)[-1]) for ref in edge['event_refs'])
            for key in (source, target):
                self.recent[key] = max(self.recent[key], latest)

    @property
    def available_filters(self):
        fields = ['name', 'actor_type']
        for field in ('organisations', 'roles', 'motivation', 'offers', 'needs'):
            if any(getattr(profile, field) for profile in self.profiles.values()):
                fields.append(field)
        return (*fields, 'connected', 'not_connected', 'neighbourhood', 'complementarity')

    def browse(self, filters=ParticipantFilters(), *, sort='name', reference=None, neighbour_of=None):
        profiles = self.profiles.values()
        field, query = filters.field, _fold(filters.query.strip())
        if field == 'connected':
            profiles = (p for p in profiles if self.neighbours[p.id])
        elif field == 'not_connected':
            profiles = (p for p in profiles if not self.neighbours[p.id])
        elif field == 'neighbourhood':
            profiles = (p for p in profiles if p.id in self.neighbours[neighbour_of])
        elif field == 'complementarity':
            origin = self.profiles.get(reference)
            profiles = (p for p in profiles if origin and p.id != reference and set(p.offers) & set(origin.needs))
        elif field in FILTER_FIELDS and query:
            def matches(profile):
                values = getattr(profile, field)
                return any(query in _fold(value) for value in (values if isinstance(values, tuple) else (values or '',)))
            profiles = filter(matches, profiles)
        for facet, selected in filters.facets:
            profiles = [p for p in profiles if set(self.values(p, facet, reference=reference,
                                                            neighbour_of=neighbour_of)) & set(selected)]
        origin = self.profiles.get(reference)

        def order(profile):
            if sort == 'organisation':
                value = (not profile.organisations, tuple(map(_fold, profile.organisations)))
            elif sort == 'connections':
                value = -len(self.neighbours[profile.id])
            elif sort == 'recent':
                value = -self.recent[profile.id]
            elif origin is not None and sort in {'shared_offers', 'shared_needs'}:
                attribute = sort.removeprefix('shared_')
                value = -len(set(getattr(origin, attribute)) & set(getattr(profile, attribute)))
            else:
                value = 0
            return value, _fold(profile.name), profile.id

        return sorted(profiles, key=order)


    def values(self, participant, field, *, reference=None, neighbour_of=None):
        if field == 'connections':
            values = ['connected' if self.neighbours[participant.id] else 'not_connected']
            if participant.id in self.recalled_by[reference]:
                values.append('recalled_by_me')
            if participant.id in self.neighbours[neighbour_of]:
                values.append('neighbourhood')
            origin = self.profiles.get(reference)
            if origin and participant.id != reference and set(participant.offers) & set(origin.needs):
                values.append('complementarity')
            return values
        value = getattr(participant, field)
        values = value if isinstance(value, tuple) else (value,) if value else ()
        if values:
            return values
        if field in {'offers', 'needs'} and getattr(participant, field+'_state') == 'answered':
            return ('__none_declared__',)
        return ('__missing__',)

    def facet_values(self, field, filters=ParticipantFilters(), *, reference=None, neighbour_of=None):
        remaining = replace(filters, facets=tuple((key, values) for key, values in filters.facets if key != field))
        counts = defaultdict(int)
        for participant in self.browse(remaining, reference=reference, neighbour_of=neighbour_of):
            for value in self.values(participant, field, reference=reference, neighbour_of=neighbour_of):
                counts[value] += 1
        return sorted(counts.items(), key=lambda item: (_fold(item[0]), item[0]))
