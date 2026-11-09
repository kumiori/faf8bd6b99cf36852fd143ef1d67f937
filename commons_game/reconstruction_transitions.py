"""Executable navigation contract for the reconstruction vertical slice.

The UI consumes these bindings/options; inspection consumes the same registry.
Shared application surfaces are explicit handoff boundaries, not verified here.
"""

from copy import deepcopy
from dataclasses import replace

from game_gamer.transitions import Registry, Result, active_transition_id, stage
from game_gamer.tui.i18n import message_key
from game_gamer.tui.navigation import navigation_label
from game_gamer.tui.screen import Cancelled

from .i18n import t

P = 'exercise.reconstruct.'
BASE = tuple(P + name for name in ('directory', 'profile', 'network', 'graph'))
ROUTES = {'reconstruction_intro': P+'intro', 'reconstruction_graph': P+'graph',
          'reconstruction_filters': P+'filters', 'reconstruction_facet': P+'facet',
          'reconstruction_layers': P+'layers', 'reconstruction_provenance': P+'provenance',
          'action_result': P+'result', 'exercises': P+'workshop'}
LOCAL = tuple(dict.fromkeys((*BASE, *(value for key, value in ROUTES.items() if key != 'exercises'))))
EXTERNAL_ROUTES = ('matrix', 'gathering', 'scenarios', 'contracts', 'inbox', 'inspect', 'help',
                   'trajectory', 'history', 'history_event', 'history_object', 'network', 'curator', 'people', 'organisations', 'resources',
                   'details','notice','incidence','scenario','expertise','cell','tutorial','tutorial_graph',
                   'curator_provenance','curator_merge_preview', 'montreal_network', 'montreal_network_graph',
                   'montreal_connection', 'montreal_profile_source', 'montreal_source_review')
RESUMABLE=(*LOCAL,P+'workshop',*('host.'+route for route in EXTERNAL_ROUTES))


def state_of(app):
    modal = getattr(app, '_reconstruction_modal', None)
    if modal is not None:
        return modal
    if app.finished:
        return P+'quit'
    route = app.route
    if route.kind == 'reconstruction':
        return P + (route.region if route.region in ('directory', 'profile', 'network') else 'directory')
    if route.kind in ROUTES:
        return ROUTES[route.kind]
    if route.kind in EXTERNAL_ROUTES:
        return 'host.'+route.kind
    return None


def capture_ui(app):
    return {'mode':app.navigation.mode,'stack':deepcopy(app.stack),'finished':app.finished}


def recover_ui(app,saved):
    app.navigation.mode=saved['mode'];app.stack=saved['stack']
    app.navigation.roots[saved['mode']]=app.stack[0]
    app.finished=saved['finished']
    app._reconstruction_modal=None
    app.refresh()


REGISTRY = Registry('commons.reconstruction.v1', state_of=state_of,
    revision_of=lambda app: app.current().revision, actor_of=lambda app: app.playing_actor,
    cancelled_exception=Cancelled,capture_ui=capture_ui,recover_ui=recover_ui, dependency_modules=(
        'game_gamer.transitions', 'game_gamer.runtime.engine', 'game_gamer.runtime.transactions',
        'game_gamer.runtime.reconstruction', 'game_gamer.runtime.invitations', 'game_gamer.runtime.curation',
        'game_gamer.runtime.actions','game_gamer.runtime.runner','game_gamer.runtime.governance',
        'game_gamer.persistence.sqlite','game_gamer.persistence.memory','game_gamer.history.replay',
        'game_gamer.schema.definitions','game_gamer.projections.participants','game_gamer.projections.reconstruction',
        'commons_game.reconstruction', 'commons_game.reconstruction_filters', 'commons_game.fullscreen',
        'commons_game.play', 'commons_game.player','commons_game.presentation','commons_game.expertise',
        'game_gamer.tui.reconstruction', 'game_gamer.tui.opening','game_gamer.tui.network','game_gamer.tui.portrait',
        'game_gamer.tui.viewport','game_gamer.tui.screen','game_gamer.tui.navigation','commons_game.engine'))
for key, label in [('workshop','Exercises'),('intro','Reconstruction introduction'),('directory','Participant directory'),
                   ('profile','Participant profile'),('network','Participant network'),('graph','Collective network'),
                   ('filters','Filter fields'),('facet','Filter values'),('layers','Network layers'),
                   ('provenance','Connection provenance'),('result','Action result')]:
    REGISTRY.state(P+key, label, entry=key=='workshop')
for key, label in [('connect.menu','Connect with participant'),('connect.confirm','Record this connection?'),
                   ('invite.message','Invitation message'),('invite.purpose','Optional invitation purpose'),('invite.delivery','Invitation delivery'),
                   ('invite.confirm','Submit invitation?'),('search.input','Search participants'),('sort.input','Sort participants')]:
    REGISTRY.state(P+key, label, kind='question')
REGISTRY.state(P+'quit', 'Quit', boundary=True,kind='outcome')
for route in EXTERNAL_ROUTES:
    REGISTRY.state('host.'+route, 'Shared '+route, boundary=True,kind='boundary')
REGISTRY.state('host.command', 'Shared developer command request', boundary=True,kind='boundary')


CHOICE_MESSAGES = {}


def choice(name, payload=None):
    return REGISTRY.choice(P+name, payload, label=t(CHOICE_MESSAGES[name]))


def define_choice(name, key, *args, **kwargs):
    CHOICE_MESSAGES[name] = key
    # Inspection reports carry the canonical labels across all runs.
    from game_gamer.tui.i18n import using_language
    with using_language('en'):
        return define(name, t(key), *args, **kwargs)


def define(name, label, sources, destinations, **kwargs):
    destinations={**destinations,'error':BASE if any(s in {P+'connect.menu',P+'invite.delivery'} for s in sources) else tuple(sources),
                  'aborted':(P+'quit',)}
    return REGISTRY.register(P+name, label, sources=sources, destinations=destinations, **kwargs)


@define('enter', 'Reconstruct the network', (P+'workshop',), {'completed': (P+'intro',)}, critical=True)
def enter(app, **_):
    app.push('reconstruction_intro')
    return Result(feedback='reconstruction.introduction')


@define('intro.skip', 'Skip opening animation', (P+'intro',), {'completed': (P+'intro',)})
def skip(app, **_):
    app.route.extra['opening_finished'] = True
    return Result(feedback='reconstruction.opening_skipped')


@define('intro.begin', 'Begin reconstruction', (P+'intro',), {'completed': (P+'directory',)}, keys=('enter',), critical=True)
def begin(app, **_):
    app.route.kind, app.route.region, app.route.scroll = 'reconstruction', 'directory', 0
    return Result(feedback='reconstruction.ready')


def local_handler(app, *, key, screen, **_):
    from .reconstruction import _handle_local
    if active_transition_id()==P+'participant.select' and not screen.entries:
        return Result('blocked',reasons=('no_eligible_participants',),feedback='reconstruction.selection_unavailable')
    _handle_local(app, key, screen)
    return Result(feedback='reconstruction.view_updated')


# Each identity denotes one semantic interaction; input direction is a parameter.
for name, label, sources, keys, destinations, critical in [
    ('intro.scroll','Scroll introduction',(P+'intro',),('up','down','pageup','pagedown'),(P+'intro',),False),
    ('participant.select','Select participant',(P+'directory',),('up','down','pageup','pagedown'),(P+'directory',),True),
    ('profile.scroll','Scroll profile',(P+'profile',),('up','down','pageup','pagedown'),(P+'profile',),False),
    ('network.scroll','Scroll network',(P+'network',P+'graph'),('up','down','pageup','pagedown'),(P+'network',P+'graph'),False),
    ('region.cycle','Change focused panel',BASE,('tab','backtab'),BASE,False),
    ('region.inspect','Inspect selected participant',BASE,('enter',),BASE,False),
    ('region.network','Focus network panel',BASE,('n',),BASE,False),
    ('graph.toggle','Toggle collective/neighbourhood network',BASE,('v',),BASE,False),
    ('graph.page','Page network neighbours',BASE,('[',']'),BASE,False),
]:
    outcomes={'completed':destinations}
    if name=='participant.select':outcomes['blocked']=destinations
    define(name,label,sources,outcomes,keys=keys,critical=critical,
           provider='game_gamer.projections.participants.ParticipantDirectory.browse' if name=='participant.select' else None)(local_handler)


@define('graph.open', 'Open network view', BASE[:3], {'completed':(P+'graph',)}, keys=('G',))
def graph_open(app, **_):
    extra = app.route.extra
    app.push('reconstruction_graph', app.route.target)
    app.route.extra, app.route.region = extra, 'network'
    return Result(feedback='reconstruction.graph_open')


@define('graph.close','Return from network view',(P+'graph',),{'completed':BASE[:3]},keys=('G',),recovery=True)
def graph_close(app, **_):
    app.back()
    return Result(feedback='reconstruction.returned')


@define('search','Search participants',BASE,{'completed':BASE,'cancelled':BASE},keys=('/',),questions=(P+'search.input',))
def search(app, **_):
    from game_gamer.projections.participants import ParticipantFilters
    stage('question',state_id=P+'search.input')
    query=app.read(t('workshop.reconstruction.search_participants_by_name'))
    app.route.extra['filter']=replace(app.route.extra.get('filter',ParticipantFilters()),field='name',query=query)
    return Result(feedback='reconstruction.search_applied')


@define('sort','Sort participants',BASE,{'completed':BASE,'cancelled':BASE},keys=('o',),questions=(P+'sort.input',),
        provider='game_gamer.projections.participants.SORT_FIELDS')
def sort(app, **_):
    from game_gamer.projections.participants import SORT_FIELDS

    from .reconstruction import SORT_LABELS
    stage('question',state_id=P+'sort.input')
    app.route.extra['sort']=app.choose(t('workshop.reconstruction.sort_participants'),SORT_FIELDS,lambda value: t(SORT_LABELS[value]))
    return Result(feedback='reconstruction.sort_applied')


@define('filters.open','Filter participants',BASE,{'completed':(P+'filters',)},keys=('f',))
def filters_open(app, **_):
    from game_gamer.projections.participants import ParticipantFilters
    app.push('reconstruction_filters',draft=app.route.extra.get('filter',ParticipantFilters()),anchor=app.route.target)
    return Result(feedback='reconstruction.filters_open')


def cursor(app, *, key, screen, **_):
    app.route.index=min(max(0,app.route.index+(-1 if key=='up' else 1)),max(0,len(screen.entries)-1))
    app.route.reveal=True
    return Result(feedback='reconstruction.cursor_moved')


define('selection.move','Move menu selection',(P+'filters',P+'facet',P+'layers',P+'result'),
       {'completed':(P+'filters',P+'facet',P+'layers',P+'result')},keys=('up','down'))(cursor)


@define('filters.facet.open','Select a filter field',(P+'filters',),{'completed':(P+'facet',)},
        provider='commons_game.reconstruction_filters.FILTER_FIELDS')
def facet_open(app, *, payload, **_):
    app.push('reconstruction_facet',payload)
    return Result(feedback='reconstruction.facet_open')


@define('filters.toggle','Toggle filter value',(P+'facet',),{'completed':(P+'facet',)},
        provider='game_gamer.projections.participants.ParticipantDirectory.facet_values')
def facet_toggle(app, *, payload, **_):
    panel=next(r for r in reversed(app.stack) if r.kind=='reconstruction_filters')
    draft=panel.extra['draft']; groups=dict(draft.facets); values=set(groups.get(app.route.target,()))
    values.symmetric_difference_update({payload})
    if values: groups[app.route.target]=tuple(sorted(values))
    else: groups.pop(app.route.target,None)
    panel.extra['draft']=replace(draft,facets=tuple(sorted(groups.items())))
    return Result(feedback='reconstruction.facet_toggled')


@define('filters.clear','Clear filter draft',(P+'filters',),{'completed':(P+'filters',)})
def filters_clear(app, **_):
    from game_gamer.projections.participants import ParticipantFilters
    app.route.extra['draft']=ParticipantFilters()
    return Result(feedback='reconstruction.filter_draft_cleared')


@define('filters.apply','Apply filters',(P+'filters',),{'completed':BASE},critical=True,recovery=True)
def filters_apply(app, **_):
    from .reconstruction_filters import filter_parent
    panel=app.route; parent=filter_parent(app)
    if 'filter_checkpoint' not in parent.extra:
        parent.extra['filter_checkpoint']=(parent.target,parent.extra.get('directory_start',0))
    parent.extra['filter']=panel.extra['draft']; parent.extra['neighbour_of']=panel.extra['anchor']
    if not panel.extra['draft'].facets and not panel.extra['draft'].query:
        parent.target,parent.extra['directory_start']=parent.extra.pop('filter_checkpoint')
    app.back()
    return Result(feedback='reconstruction.filters_applied')


@define('filters.cancel','Cancel filter draft',(P+'filters',),{'cancelled':BASE},critical=True,recovery=True)
def filters_cancel(app, **_):
    app.back()
    return Result('cancelled',feedback='reconstruction.filters_cancelled')


@define('layers.open','Choose network layers',BASE,{'completed':(P+'layers',)},keys=('L',))
def layers_open(app, **_):
    app.push('reconstruction_layers')
    return Result(feedback='reconstruction.layers_open')


@define('layers.toggle','Toggle network layer',(P+'layers',),{'completed':(P+'layers',)},
        provider='commons_game.reconstruction.LAYER_OPTIONS')
def layers_toggle(app, *, payload, **_):
    parent=next(r for r in reversed(app.stack[:-1]) if r.kind in {'reconstruction','reconstruction_graph'})
    groups=set(parent.extra.get('graph_groups',('reconstruction','existing','invitations')))
    groups.symmetric_difference_update({payload});parent.extra['graph_groups']=tuple(sorted(groups))
    return Result(feedback='reconstruction.layer_toggled')


@define('provenance.open','Inspect connection provenance',BASE,{'completed':(P+'provenance',)},keys=('d',))
def provenance_open(app, **_):
    app.push('reconstruction_provenance',app.route.target)
    return Result(feedback='reconstruction.provenance_open')


@define('result.view','View recorded connection',(P+'result',),{'completed':(P+'network',P+'graph')},critical=True,recovery=True)
def result_view(app, **_):
    app.back();app.route.region='network'
    return Result(feedback='reconstruction.connection_visible')


@define('result.continue','Continue reconstruction',(P+'result',),{'completed':BASE},critical=True,recovery=True)
def result_continue(app, **_):
    app.back()
    return Result(feedback='reconstruction.returned')


# Back destinations are declared from actual push/replace relationships. They
# remain parameterised by the live stack; no arbitrary destination is invented.
for name, sources, destinations in [
    ('back',(P+'intro',*BASE[:3]),(P+'workshop',)),
    ('graph.back',(P+'graph',),BASE[:3]),
    ('filters.back',(P+'filters',),BASE),
    ('facet.back',(P+'facet',),(P+'filters',)),
    ('layers.back',(P+'layers',),BASE),
    ('provenance.back',(P+'provenance',),BASE),
    ('result.back',(P+'result',),BASE),
]:
    def back(app, **_):
        app.back()
        return Result(feedback='reconstruction.returned')
    define(name,'Back',sources,{'completed':destinations},keys=('b','esc'),recovery=True,
           critical=name=='back',provider='game_gamer.tui.navigation.NavigationState.back')(back)


@define('quit','Quit reconstruction',LOCAL,{'completed':(P+'quit',)},keys=('q',),recovery=True)
def quit(app, **_):
    app.finished=True
    return Result(feedback='reconstruction.quit')


def handoff(app, *, key, screen=None, **_):
    from game_gamer.tui.navigation import MODE_KEYS
    target={'i':'inbox','?':'help','t':'trajectory','C':'contracts','c':'contracts','w':'network','u':'curator','h':'history'}
    source=state_of(app)
    if key in MODE_KEYS:
        app.resume_mode(MODE_KEYS[key])
    elif key=='m':
        app.choose_mode()
    elif key=='p':
        app.select_actor()
    elif key=='u':
        from .curation_panel import open_panel
        open_panel(app,screen or app.build_screen())
    elif key=='w':
        app.open_network()
        if state_of(app)==source:
            return Result('blocked',reasons=('no_network_focus',),feedback='reconstruction.handoff_blocked')
    elif key=='h':
        app.push('history',app.route.target)
    elif key=='x':
        view=app.choose(t('terminal.ecosystem_views'),['matrix','network','people','organisations','resources'],navigation_label)
        if view=='matrix':app.switch_mode('ecosystem')
        elif view=='network':app.open_network()
        else:app.push(view)
    else:
        app.push(target[key])
    return Result(feedback='reconstruction.shared_surface')


for name, keys, destinations in [
    ('handoff.modes',('e','g','s'),RESUMABLE),
    ('handoff.paths',('m',),RESUMABLE),
    ('handoff.player',('p',),LOCAL),
    ('handoff.inbox',('i',),('host.inbox',)),('handoff.help',('?',),('host.help',)),
    ('handoff.trajectory',('t',),('host.trajectory',)),('handoff.contracts',('C',),('host.contracts',)),
    ('handoff.network',('w',),('host.network',)),('handoff.curator',('u',),('host.curator',)),
    ('handoff.history',('h',),('host.history',)),
    ('handoff.ecosystem',('x',),('host.matrix','host.network','host.people','host.organisations','host.resources',*LOCAL)),
]:
    define(name,'Open shared '+name.split('.')[-1],LOCAL,
           {'completed':destinations,'cancelled':LOCAL,'blocked':LOCAL},keys=keys,
           provider='game_gamer.tui.navigation.NavigationState.resume' if name in {'handoff.modes','handoff.paths'} else None)(handoff)
for source in LOCAL:
    if source not in BASE:
        REGISTRY.bindings[source,'c']=P+'handoff.contracts'


@define('handoff.command','Delegate to shared developer commands',LOCAL,{'completed':('host.command',)},keys=(':',))
def command_boundary(app,**_):
    app._reconstruction_modal='host.command'
    return Result(feedback='reconstruction.developer_handoff_requested')


@define('provenance.scroll','Scroll provenance',(P+'provenance',),{'completed':(P+'provenance',)},keys=('up','down','pageup','pagedown'))
def provenance_scroll(app,*,key,**_):
    step=-1 if key in {'up','pageup'} else 1
    if key in {'pageup','pagedown'}:step*=max(1,app.height-10)
    app.route.scroll=max(0,app.route.scroll+step)
    return Result(feedback='reconstruction.provenance_scrolled')


@define('handoff.return','Return from shared inspector',('host.inspect',),
        {'completed':BASE,'blocked':('host.inspect',)},recovery=True,guards=('immediate_reconstruction_parent',))
def handoff_return(app, **_):
    if len(app.stack)<2 or app.stack[-2].kind not in {'reconstruction','reconstruction_graph'}:
        app.notice='Return through the shared interface to the reconstruction entry.'
        return Result('blocked',reasons=('no_reconstruction_parent',),feedback='reconstruction.handoff_blocked')
    app.back()
    return Result(feedback='reconstruction.returned')


def select_delivery(app,**_):
    action=REGISTRY.transitions[active_transition_id()].action_reference
    return Result(value=action,feedback='invitation.delivery_selected')


for name,label,kind in [('send',message_key('contact.send_now'),'send_contact'),('draft',message_key('contact.save_draft'),'draft_contact')]:
    define_choice('invite.delivery.'+name,label,(P+'invite.delivery',),{'completed':(P+'invite.delivery',)},
           critical=True,action_reference=kind)(select_delivery)


def bind_connection_handlers():
    """Called after owning UI functions are defined, avoiding circular imports."""
    from .reconstruction import cancel_connection, connection_menu, execute_connection
    define('connect.open','Choose connection type',BASE,
           {'selected':(P+'connect.menu',),'cancelled':BASE,'blocked':BASE},keys=('c',),
           critical=True,provider='commons_game.reconstruction.connection_options',
           questions=(P+'connect.menu',),requirements=('selected','blocked','cancelled','feedback','recovery'),
           guards=('bound_person_and_distinct_active_person',))(connection_menu)
    for name,label,actions in [
        ('recall',message_key('workshop.reconstruction.we_connected_in_montreal'),('recall_connection',)),
        ('prior_relationship',message_key('workshop.reconstruction.we_already_knew_each_other'),('record_prior_relationship',)),
        ('invite',message_key('workshop.reconstruction.i_would_like_to_connect'),('send_contact','draft_contact')),
        ('dispute',message_key('workshop.reconstruction.dispute_this_participants_recollection'),('dispute_recollection',)),
        ('retract',message_key('workshop.reconstruction.retract_my_relationship_declaration'),('retract_relationship_claim',)),
    ]:
        targets=('host.inspect',) if name=='invite' else (P+'result',)
        define_choice('connect.'+name,label,(P+'connect.menu',),
               {'committed':targets,'idempotent':targets,
                'rejected':BASE if name=='invite' else (P+'result',),'cancelled':BASE,'blocked':BASE},
               critical=True,engine_actions=actions,guards=('engine_validation',),
               questions=(P+'invite.message',P+'invite.purpose',P+'invite.delivery',P+'invite.confirm') if name=='invite' else (P+'connect.confirm',),
               requirements=('committed','rejected','cancelled','persistence','replay','engine_consistency','feedback','recovery')+
                            (('idempotency',) if name=='prior_relationship' else ()))(execute_connection)
    define_choice('connect.cancel',message_key('workshop.reconstruction.cancel'),(P+'connect.menu',),{'cancelled':BASE},critical=True,recovery=True)(cancel_connection)
    REGISTRY.validate()


def dispatch(app,key,screen):
    state=state_of(app)
    if state=='host.inspect' and key in {'b','esc'} and len(app.stack)>1 and app.stack[-2].kind in {'reconstruction','reconstruction_graph'}:
        REGISTRY.execute(P+'handoff.return',app)
        return True
    if state not in LOCAL:
        return False
    if state==P+'intro' and not app.route.extra.get('opening_finished',False):
        REGISTRY.execute(P+'intro.skip',app)
        return True
    if key=='enter' and state in {P+'filters',P+'facet',P+'layers',P+'result'}:
        if not screen.entries:
            return True
        choice=screen.entries[min(app.route.index,len(screen.entries)-1)][1]
        REGISTRY.execute(choice.transition_id,app,payload=choice.payload)
        return True
    id=REGISTRY.bindings.get((state,key))
    if id is None:
        app.notice=t('workshop.reconstruction.use_the_reconstruction_controls_or')
        return True
    if id==P+'handoff.command':
        REGISTRY.execute(id,app)
        app._reconstruction_modal=None
        return False
    if id==P+'connect.open':
        from .reconstruction import connect
        connect(app)
    else:
        REGISTRY.execute(id,app,key=key,screen=screen)
    return True
