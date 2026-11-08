"""Discoverable facets with OR within fields and AND across fields."""
from dataclasses import replace

from game_gamer.projections.participants import ParticipantFilters
from game_gamer.tui.screen import Screen
from .reconstruction_transitions import REGISTRY, P

LABELS = {'organisations': 'Organisation', 'roles': 'Role', 'offers': 'Offers', 'needs': 'Needs',
          'connections': 'Connections', '__missing__': 'Not recorded', '__none_declared__': 'None declared',
          'connected': 'Has a recorded recollection', 'not_connected': 'No recorded recollection',
          'recalled_by_me': 'Recalled by me', 'neighbourhood': 'Connected to selected person',
          'complementarity': 'Offers what I need'}
FILTER_FIELDS=('organisations','roles','offers','needs','connections')


def filter_parent(app):
    return next(route for route in reversed(app.stack) if route.kind in {'reconstruction', 'reconstruction_graph'})


def filter_screen(app):
    parent = filter_parent(app)
    directory = app._projection_cache['reconstruction'][1]
    panel = next(route for route in reversed(app.stack) if route.kind == 'reconstruction_filters')
    draft = panel.extra['draft']
    reference = app.playing_actor
    selected = dict(draft.facets)
    count = len(directory.browse(draft, reference=reference, neighbour_of=panel.extra['anchor']))
    lines = [f'People matching: {count}', 'OR within a field · AND across fields',
             f'Active choices: {sum(len(values) for values in selected.values())}']
    route = app.route
    if route.kind == 'reconstruction_facet':
        field = route.target
        values = directory.facet_values(field, draft, reference=reference, neighbour_of=panel.extra['anchor'])
        entries = [(('[x] ' if value in selected.get(field, ()) else '[ ] ')+LABELS.get(value, value)+f' ({count})',
                    REGISTRY.choice(P+'filters.toggle',value))
                   for value, count in values]
        return Screen('FILTER / '+LABELS[field].upper(), lines, entries, 'Enter Toggle · b Fields',
                      route.index, route.scroll)
    fields = FILTER_FIELDS
    entries = [(LABELS[field]+f" · {len(selected.get(field, ()))} selected",REGISTRY.choice(P+'filters.facet.open',field)) for field in fields]
    entries += [('APPLY · '+str(count)+' people',REGISTRY.choice(P+'filters.apply')),
                ('CLEAR',REGISTRY.choice(P+'filters.clear')),('CANCEL',REGISTRY.choice(P+'filters.cancel'))]
    return Screen('FILTER PEOPLE', lines, entries, 'Enter Choose · b Cancel', route.index, route.scroll)


def filter_key(app, key, screen):
    from .reconstruction_transitions import dispatch
    return dispatch(app,key,screen)
