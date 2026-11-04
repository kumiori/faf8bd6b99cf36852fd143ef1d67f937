"""Read-only native trajectory-engine documents over authoritative Commons history.

No geometry is invented. The versioned discrete-history extension lives inside
the package's losslessly preserved plan namespace; Commons alone replays it.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from .engine import CommonsGame, digest
from .model import require

SCHEMA = 'subtle-trajectory/v1'
LOCK = json.loads((Path(__file__).parent / 'trajectory-lock.json').read_text())


class TrajectoryUnavailable(RuntimeError):
    pass


def package_api():
    try:
        import trajectory_engine as api
    except ModuleNotFoundError as error:
        if error.name not in {'trajectory_engine', 'yaml'}:
            raise
        raise TrajectoryUnavailable(
            'Trajectory integration is not installed. Use pip install -e ".[trajectory]" '
            'or the pinned-source setup in README.md.'
        ) from error
    if api.__version__ != LOCK['version']:
        raise TrajectoryUnavailable('Unsupported trajectory-engine version; install the pinned release.')
    source = Path(api.__file__).parent
    for name, expected in LOCK['files'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise TrajectoryUnavailable(
                'Trajectory source differs from the audited commit. Install the pinned '
                'release; unrelated working-tree changes are not used automatically.'
            )
    return api


def _envelope(document):
    require(isinstance(document, dict) and isinstance(document.get('plan'), dict), 'invalid_trajectory_document')
    require(document.get('schema_version') == 'trajectory-plan/v2', 'unsupported_package_document_schema')
    envelope = document.get('plan', {}).get('commons_trajectory', {})
    require(isinstance(envelope, dict), 'invalid_trajectory_envelope')
    require(envelope.get('schema_version') == SCHEMA, 'unsupported_commons_trajectory_schema')
    require(envelope.get('authority') == 'commons_event_history' and
            envelope.get('access') == 'read_only_projection', 'invalid_trajectory_boundary')
    require(envelope.get('package') == {k: LOCK[k] for k in ('repository', 'commit', 'version')},
            'unsupported_trajectory_source')
    require(isinstance(envelope.get('events'), list) and bool(envelope['events']), 'trajectory_events_required')
    require(digest(envelope['events']) == envelope.get('history_digest'), 'invalid_trajectory_history_digest')
    return envelope


def project_trajectory(game, *, trajectory_id='commons-history', branches=()):
    """Capture one consistent log prefix and return a detached package document."""
    api = package_api()
    events = game.project('log')
    replayed = CommonsGame.from_log(events)
    world = replayed.get_world()
    config = world['configuration']['world']
    objective = next(iter(world['objectives'].values()))
    timestamp = events[0]['occurred_at']
    envelope = {
        'schema_version': SCHEMA, 'trajectory_id': trajectory_id,
        'authority': 'commons_event_history', 'access': 'read_only_projection',
        'package': {key: LOCK[key] for key in ('repository', 'commit', 'version')},
        'provenance': {'history_kind': 'recorded',
                       'world_kind': 'synthetic_simulation' if config.get('synthetic') is True else 'unspecified',
                       'scenario': config['scenario'],
                       'note': 'Record-level epistemic status and evidence remain in the unmodified events.'},
        'events': events, 'history_digest': digest(events), 'branches': deepcopy(list(branches)),
    }
    document = api.build_trajectory_document(plan={
        'id': trajectory_id, 'title': 'Subtle Pathways / ' + config['title'],
        'initial_condition': 'Initial collective state recorded by Commons.',
        'goal_statement': objective['label'], 'created_at': timestamp,
        'commons_trajectory': envelope,
    }, primitives=[], uncertainty=[])
    validate_document(document)
    return document


def reconstruct(document, *, at=None, branch_id=None):
    """Detached inspection replay only; never saves or replaces a live world."""
    envelope = _envelope(document)
    events = envelope['events']
    if branch_id is not None:
        matches = [branch for branch in envelope['branches'] if branch['id'] == branch_id]
        require(len(matches) == 1, 'unknown_trajectory_branch')
        branch = matches[0]
        parent = branch['parent_sequence']
        require(type(parent) is int and 1 <= parent <= len(events), 'invalid_branch_parent')
        prefix = events[:parent]
        base = CommonsGame.from_log(prefix)
        require(branch['kind'] == 'hypothetical_simulation', 'invalid_branch_provenance')
        require(branch['parent_commit_id'] == prefix[-1]['commit']['id'] and
                branch['parent_state_hash'] == digest(base.get_world()) and
                branch['parent_history_digest'] == digest(prefix), 'branch_parent_mismatch')
        require(digest(branch['events']) == branch['history_digest'], 'invalid_branch_history_digest')
        events = prefix + branch['events']
    game = CommonsGame.from_log(events)
    if at is not None:
        require(type(at) is int and 1 <= at <= len(events), 'invalid_event')
        game = CommonsGame.from_log(events[:at])
    return game


def validate_document(document):
    envelope = _envelope(document)
    require(document.get('primitives') == [] and document.get('uncertainty') == [],
            'unauthored_geometry_not_supported')
    require(isinstance(envelope.get('branches'), list), 'invalid_trajectory_branches')
    reconstruct(document)
    branch_ids = set()
    for branch in envelope['branches']:
        require(isinstance(branch, dict), 'invalid_trajectory_branch')
        require(isinstance(branch.get('id'), str) and bool(branch['id'].strip()) and
                branch['id'] not in branch_ids, 'duplicate_or_invalid_branch_id')
        branch_ids.add(branch['id'])
        reconstruct(document, branch_id=branch['id'])
        require(isinstance(branch.get('attempts'), list), 'branch_attempts_required')
        replayed = simulate_branch(reconstruct(document), parent_sequence=branch['parent_sequence'],
                                  commands=[attempt['command'] for attempt in branch['attempts']],
                                  branch_id=branch['id'])
        require(replayed == branch, 'branch_resolution_mismatch')
    return document


def simulate_branch(game, *, parent_sequence, commands, branch_id):
    """Resolve proposed alternatives using the same engine in an isolated replay."""
    require(isinstance(branch_id, str) and bool(branch_id.strip()), 'branch_id_required')
    events = game.project('log')
    require(type(parent_sequence) is int and 1 <= parent_sequence <= len(events), 'invalid_branch_parent')
    prefix = events[:parent_sequence]
    branch_game = CommonsGame.from_log(prefix)
    parent_hash = digest(branch_game.get_world())
    attempts = []
    for command in commands:
        candidate = deepcopy(command)
        result = branch_game.submit(candidate)
        attempts.append({'command': candidate, 'ok': result['ok'], 'errors': result['errors']})
    suffix = branch_game.project('log')[parent_sequence:]
    return {'id': branch_id, 'kind': 'hypothetical_simulation',
            'parent_sequence': parent_sequence, 'parent_commit_id': prefix[-1]['commit']['id'],
            'parent_state_hash': parent_hash, 'parent_history_digest': digest(prefix),
            'events': suffix, 'history_digest': digest(suffix), 'attempts': attempts}


def trajectory_yaml(document):
    validate_document(document)
    return package_api().trajectory_yaml(document)


def load_trajectory_yaml(source):
    document = package_api().load_trajectory_yaml(source)
    return validate_document(document)


def frames(document, *, branch_id=None):
    """State summaries are disposable projections, never a second persisted state."""
    envelope = _envelope(document)
    game = reconstruct(document, branch_id=branch_id)
    parent = None
    if branch_id is not None:
        parent = next(b['parent_sequence'] for b in envelope['branches'] if b['id'] == branch_id)
    for entry in game.project('log'):
        world = game.world_at(event=entry['sequence'])
        yield {
            'state_id': f"{branch_id or envelope['trajectory_id']}:state:{entry['sequence']:06}",
            'sequence': entry['sequence'], 'event_id': entry['id'], 'commit_id': entry['commit']['id'],
            'timestamp': entry['occurred_at'], 'time_kind': 'commons_logical_transaction_time',
            'history_kind': 'hypothetical' if parent is not None and entry['sequence'] > parent else 'recorded_prefix' if parent else 'recorded',
            'world_kind': envelope['provenance']['world_kind'],
            'actor_id': entry['actor_id'], 'kind': entry['command']['kind'] if entry['command'] else 'initialize',
            'state_hash': digest(world),
            'agreements': [{key: agreement[key] for key in ('id', 'current_version', 'status', 'outcome_status')}
                           for agreement in world['agreements'].values()],
        }
