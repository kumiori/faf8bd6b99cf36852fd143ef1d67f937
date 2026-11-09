"""Discoverable facets with OR within fields and AND across fields."""

from dataclasses import replace

from game_gamer.projections.participants import ParticipantFilters
from game_gamer.tui.i18n import message_key
from game_gamer.tui.screen import Screen

from .i18n import t
from .reconstruction_transitions import REGISTRY, P

LABELS = {'organisations': message_key('objects.organisation.singular'), 'roles': message_key('workshop.filters.values.roles'), 'offers': message_key('objects.offers'), 'needs': message_key('objects.need.plural'),
          'connections': message_key('workshop.filters.values.connections'), '__missing__': message_key('common.not_recorded'), '__none_declared__': message_key('workshop.directory.none_declared'),
          'connected': message_key('workshop.filters.values.connected'), 'not_connected': message_key('workshop.filters.values.not_connected'),
          'recalled_by_me': message_key('workshop.filters.values.recalled_by_me'), 'neighbourhood': message_key('workshop.filters.values.neighbourhood'),
          'complementarity': message_key('workshop.filters.values.complementarity')}
FILTER_FIELDS=('organisations','roles','offers','needs','connections')


def filter_label(value):
    return t(LABELS[value]) if value in LABELS else value


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
    lines = [t('workshop.filters.people_matching', count=count), t('workshop.filters.or_within_a_field_and'),
             t('workshop.filters.active_choices', value=sum((len(values) for values in selected.values())))]
    route = app.route
    if route.kind == 'reconstruction_facet':
        field = route.target
        values = directory.facet_values(field, draft, reference=reference, neighbour_of=panel.extra['anchor'])
        entries = [(('[x] ' if value in selected.get(field, ()) else '[ ] ')+filter_label(value)+f' ({count})',
                    REGISTRY.choice(P+'filters.toggle',value))
                   for value, count in values]
        return Screen(t('workshop.filters.field_title', field=filter_label(field).upper()), lines, entries, t('workshop.filters.enter_toggle_b_fields'),
                      route.index, route.scroll)
    fields = FILTER_FIELDS
    entries = [(t('workshop.filters.field_summary', field=filter_label(field), count=len(selected.get(field, ()))),REGISTRY.choice(P+'filters.facet.open',field)) for field in fields]
    entries += [(t('workshop.filters.apply', count=count),REGISTRY.choice(P+'filters.apply')),
                (t('workshop.filters.clear'),REGISTRY.choice(P+'filters.clear')),(t('controls.cancel_button'),REGISTRY.choice(P+'filters.cancel'))]
    return Screen(t('workshop.filters.filter_people'), lines, entries, t('curation.enter_choose_b_cancel'), route.index, route.scroll)


def filter_key(app, key, screen):
    from .reconstruction_transitions import dispatch
    return dispatch(app,key,screen)
