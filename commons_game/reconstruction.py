"""Mount the Montréal reconstruction as an Ecosystem exercise."""
from dataclasses import replace
import json
from uuid import uuid4

from game_gamer.projections.participants import SORT_FIELDS, ParticipantDirectory, ParticipantFilters
from game_gamer.projections.reconstruction import exercise_graph, reconstruction_counts
from game_gamer.runtime.curation import canonical
from game_gamer.runtime.reconstruction import CLAIM_KINDS, PRIOR, RECOLLECTION
from game_gamer.tui.reconstruction import LAYER_NAMES, REGIONS, NetworkReconstructionExercise, reconstruction_screen
from game_gamer.tui.screen import Screen
from game_gamer.tui.opening import opening_screen
from game_gamer.tui.viewport import action_form

from .catalogue import people
from .presentation import person_labels
from .reconstruction_filters import filter_screen, filter_key
from .reconstruction_transitions import REGISTRY as TRANSITIONS, P, dispatch
from game_gamer.transitions import Result, active_transition_id, stage,accepted_outcome

COPY_REVIEW_REQUIRED = 'Natalie'

EXERCISE = NetworkReconstructionExercise(
    id='montreal_network_reconstruction', context_id='montreal-forum',
    title='RECONSTRUCT THE NETWORK', subtitle='Who did you connect with in Montréal?',
    introduction=(
        'In Montréal, we gathered around a whiteboard.',
        'Each of us brought a motivation, a question, a possibility.',
        'Connections appeared.',
        '',
        'Can we reconstruct the network we created together?',
        '',
        'Find yourself. Find someone you connected with. Draw the link.',
        '',
        'Wording pending Natalie’s review.',
        'Your recollection is attributed to you. A new invitation goes to the recipient’s inbox.',
    ),
)

SORT_LABELS = {'shared_offers': 'Shared offers with you', 'shared_needs': 'Shared needs with you',
               'connections': 'Number of recalled connections', 'recent': 'Recent recollection activity'}
LAYER_OPTIONS = {'reconstruction':'Montréal reconstruction','existing':'Existing relationships',
                 'invitations':'Invitations and accepted connections','contracts':'Contracts',
                 'potential':'Potential complementarities'}


def exercise_available(world):
    return world['configuration']['world'].get('scenario') == 'montreal-commons'


def exercise_projection(app):
    if 'reconstruction' not in app._projection_cache:
        world = app.world()
        roster = {actor['id'] for actor in people(world)}
        graph = exercise_graph(app.graph_projection(), context_id=EXERCISE.context_id, actor_ids=roster)
        assertions = world['configuration'].get('ecosystem-expertise', {}).get('assertions', {})
        vocabulary = assertions.get('vocabulary', {})
        topics = {table: {actor: {'domains': [vocabulary[code] for code in profile[side]['codes']],
                                   'state': profile[side]['state']}
                          for actor, profile in assertions.get('participants', {}).items()}
                  for table, side in (('capacities', 'offer'), ('needs', 'need'))}
        directory = ParticipantDirectory(world, actor_ids=roster, labels=person_labels(world),
                                         reconstruction=graph['edges'], context_id=EXERCISE.context_id,
                                         questionnaire=topics)
        app._projection_cache['reconstruction'] = (graph, directory)
    return app._projection_cache['reconstruction']


def build_exercise(app):
    route = app.route
    if route.kind not in {'action_result', 'reconstruction_intro'}:
        exercise_projection(app)
    if route.kind in {'reconstruction_filters', 'reconstruction_facet'}:
        return filter_screen(app)
    if route.kind == 'reconstruction_layers':
        parent = next(r for r in reversed(app.stack[:-1]) if r.kind in {'reconstruction', 'reconstruction_graph'})
        groups = parent.extra.get('graph_groups', ('reconstruction', 'existing', 'invitations'))
        names = LAYER_OPTIONS
        edges = app._projection_cache['reconstruction'][0]['edges']
        entries = [('[x] ' if group in groups else '[ ] ')+label+f" ({sum(e['display_group'] == group for e in edges)})"
                   for group, label in names.items()]
        return Screen('NETWORK / LAYERS', ['Enable observations independently.'],
                      [(label, TRANSITIONS.choice(P+'layers.toggle', group)) for label,group in zip(entries,names)],
                      'Enter Toggle · b Done', route.index, route.scroll)
    if route.kind == 'reconstruction_provenance':
        graph = app._projection_cache['reconstruction'][0]
        relevant = [edge for edge in graph['edges'] if route.target in (edge['source_id'], edge['target_id'])]
        lines = []
        for edge in relevant:
            lines += [app.label(edge['source_id'])+' → '+app.label(edge['target_id'])+' / '+edge['kind']]
            lines += json.dumps({key: edge[key] for key in
                                 ('graph_identity', 'display_group', 'status', 'claim_ids', 'event_refs', 'source_record_ids',
                                  'provenance', 'observation', 'original_source_id', 'original_target_id') if key in edge},
                                ensure_ascii=False, indent=2).splitlines()
        return Screen('CONNECTION / PROVENANCE', lines or ['No recorded observations for this participant.'],
                      footer='PgUp/PgDn Scroll · b Return', scroll=route.scroll)
    if route.kind == 'action_result':
        details = route.extra
        return Screen(details['title'], details['lines'],
                      [('VIEW CONNECTION', TRANSITIONS.choice(P+'result.view')),
                       ('CONTINUE', TRANSITIONS.choice(P+'result.continue'))],
                      'Enter Choose · b Continue', route.index, route.scroll)
    if route.kind == 'reconstruction_intro':
        return opening_screen(EXERCISE, route, app.viewport,begin_choice=TRANSITIONS.choice(P+'intro.begin'))
    graph, directory = exercise_projection(app)
    route.target = canonical(app.world(), route.target)
    route.extra['available_filters'] = directory.available_filters
    profiles = directory.browse(route.extra.get('filter', ParticipantFilters()),
                                sort=route.extra.get('sort', 'name'), reference=app.playing_actor,
                                neighbour_of=route.extra.get('neighbour_of'))
    counts = reconstruction_counts(app.world(), graph, context_id=EXERCISE.context_id, actor_id=app.playing_actor)
    graph = {**graph, 'reconstruction_label': 'Montréal reconstruction'}
    return reconstruction_screen(EXERCISE, route, profiles, graph, counts, width=app.width,
                                 height=app.height, plain=app.plain,
                                 reconstructed_ids={key for key, others in directory.neighbours.items() if others})


def handle_exercise(app, key, screen):
    return dispatch(app,key,screen)


def _handle_local(app, key, screen):
    """Local display operations reached only through registered key bindings."""
    route=app.route
    if route.kind=='reconstruction_intro':
        route.scroll=max(0,route.scroll+(1 if key in {'down','pagedown'} else -1))
    elif key in {'tab','backtab'}:
        step=1 if key=='tab' else -1
        route.region=REGIONS[(REGIONS.index(route.region)+step)%len(REGIONS)]
    elif key=='enter':
        route.region='directory' if route.region=='profile' else 'profile'
    elif key=='n':
        route.region='network' if route.region!='network' else 'directory'
    elif key in {'up','down','pageup','pagedown'}:
        step=-1 if key in {'up','pageup'} else 1
        if key in {'pageup','pagedown'}:step*=max(1,app.height-14)
        if route.region=='directory' and screen.entries:
            index=min(max(0,route.index+step),len(screen.entries)-1)
            route.target=screen.entries[index][1]
            route.extra.pop('filter_checkpoint',None)
            route.extra.update(profile_scroll=0,network_page=0,network_detail=0)
        elif route.region in {'profile','network'}:
            position='profile_scroll' if route.region=='profile' else 'network_detail'
            route.extra[position]=max(0,route.extra.get(position,0)+step)
    elif key=='v':
        route.extra['graph_view']='collective' if route.extra.get('graph_view','neighbourhood')=='neighbourhood' else 'neighbourhood'
        route.extra['network_page']=0
    elif key in {'[',']'}:
        panel_width=(app.width-8)//3 if app.width>=118 else (app.width-5)//2 if app.width>=68 else app.width-2
        page_size=5 if panel_width<60 else 8
        route.extra['network_page']=max(0,route.extra.get('network_page',0)+(page_size if key==']' else -page_size))
    return True


def connection_options(app):
    target, actor = app.route.target, app.playing_actor
    world = app.world()
    if not actor or not target or target == actor or any(
            world['actors'].get(key, {}).get('kind') != 'person' or
            world['actors'][key].get('status') != 'active' or canonical(world,key)!=key
            for key in (actor, target)) or app.route.extra.get('at') is not None:
        return []
    pair = [r for r in world['relationships'].values() if r['kind'] in CLAIM_KINDS
            and r['context_id'] == EXERCISE.context_id and r['status'] != 'retracted'
            and {canonical(world, r['source_id']), canonical(world, r['target_id'])} == {actor, target}]
    actions = []
    for kind, title, relation in [
        ('recall_connection', 'We connected in Montréal', RECOLLECTION),
        ('record_prior_relationship', 'We already knew each other before Montréal', PRIOR),
    ]:
        if not any(r['kind'] == relation and canonical(world, r['source_id']) == actor for r in pair):
            id = 'recall' if kind == 'recall_connection' else 'prior_relationship'
            actions.append(TRANSITIONS.choice(P+'connect.'+id,
                {'kind': kind, 'target_id': target, 'context_id': EXERCISE.context_id,
                 'historical_date': EXERCISE.historical_date if relation == RECOLLECTION else None}))
    actions.insert(min(1, len(actions)), TRANSITIONS.choice(P+'connect.invite', {'kind': 'send_contact', 'recipient_id': target}))
    for claim in pair:
        if canonical(world, claim['source_id']) == actor:
            title = 'Retract my Montréal recollection' if claim['kind'] == RECOLLECTION else 'Retract my prior relationship declaration'
            actions.append(TRANSITIONS.choice(P+'connect.retract',
                {'kind': 'retract_relationship_claim', 'claim_id': claim['id']}, label=title))
        elif claim['kind'] == RECOLLECTION and claim['status'] == 'claimed':
            actions.append(TRANSITIONS.choice(P+'connect.dispute', {'kind': 'dispute_recollection', 'claim_id': claim['id']}))
    return actions


def connection_menu(app, **_):
    actions = connection_options(app)
    if not actions:
        app.notice = 'Select another participant while playing as a person.'
        return Result('blocked', reasons=('eligible_person_pair_required',), feedback='connection.blocked')
    version = len(app.current().project('log'))
    app._reconstruction_modal = P+'connect.menu'
    stage('question',state_id=P+'connect.menu')
    choice = app.choose('CONNECT WITH '+app.label(app.route.target),
                        [*actions, TRANSITIONS.choice(P+'connect.cancel')], lambda item:item.label)
    return Result('selected', value=(choice,version), feedback='connection.choice_selected')


def connect(app):
    selection = TRANSITIONS.execute(P+'connect.open',app)
    if selection.outcome != 'selected':
        return
    choice,version = selection.value
    return TRANSITIONS.execute(choice.transition_id, app,
        payload={'command':choice.payload,'title':choice.label,'version':version})


def cancel_connection(app, **_):
    app._reconstruction_modal = None
    app.notice = 'Action cancelled.'
    return Result('cancelled',feedback='connection.cancelled')


def execute_connection(app, *, payload, **_):
    command = dict(payload['command'])
    title,version = payload['title'],payload['version']
    app._reconstruction_modal = None
    spec = TRANSITIONS.transitions[active_transition_id()]
    if command.get('kind') not in spec.engine_actions:
        app.notice = 'This action does not match the selected interaction.'
        return Result('blocked',reasons=('transition_action_mismatch',),feedback='connection.blocked')
    if not app.session or app.route.extra.get('at') is not None:
        app.notice='Actions require a simulated player in the current world.'
        return Result('blocked',reasons=('current_simulation_binding_required',),feedback='connection.blocked')
    stage('ui_guard_passed')
    actor,target = app.playing_actor,app.route.target
    world = app.world()
    if command['kind'] == 'send_contact':
        result = app.execute_action(command, version=version)
        if result is None:
            return Result('blocked',reasons=('current_simulation_binding_required',),feedback='connection.blocked')
        if not result['ok']:
            return Result('rejected',value=result,reasons=tuple(result['errors']),feedback='invitation.rejected')
        return Result(accepted_outcome(),
                      value=result,feedback='invitation.saved')
    app._reconstruction_modal = P+'connect.confirm'
    stage('question',state_id=P+'connect.confirm')
    with action_form(app.viewport):
        app.write(title)
        app.write('This records your account in the shared simulation.')
        if not app.confirm('RECORD THIS CONNECTION?'):
            app.notice = 'Action cancelled.'
            app._reconstruction_modal = None
            return Result('cancelled',feedback='connection.cancelled')
    app._reconstruction_modal = None
    command.setdefault('key', 'reconstruction-'+uuid4().hex)
    before_count = sum(r['kind'] == RECOLLECTION and r['status'] != 'retracted'
                       for r in world['relationships'].values())
    result = app.submit(command, version)
    app.reset_buffer()
    after_count = sum(r['kind'] == RECOLLECTION and r['status'] != 'retracted'
                      for r in app.world()['relationships'].values())
    description = app.label(actor)+' → '+app.label(target)
    app.push('action_result', title=('RECOLLECTION RECORDED' if command['kind'] == 'recall_connection' else 'ACTION RECORDED') if result['ok'] else 'ACTION FAILED',
             lines=[title, description,
                    f'Network: {before_count} → {after_count} directed claims',
                    'View the connection to inspect corroboration and provenance.' if result['ok'] else
                    'No state changed: '+', '.join(result['errors'])])
    return Result(accepted_outcome() if result['ok'] else 'rejected',
                  value=result,reasons=tuple(result['errors']),feedback='connection.recorded' if result['ok'] else 'connection.rejected')


from .reconstruction_transitions import bind_connection_handlers
bind_connection_handlers()
