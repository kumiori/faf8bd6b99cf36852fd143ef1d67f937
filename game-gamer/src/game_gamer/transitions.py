"""Explicit UI transition contracts and privacy-minimal diagnostic observations.

Engine commits remain authoritative. This module never submits an action and
never persists a world. Hosts execute registered handlers through one boundary.
"""
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import inspect
import json
from functools import wraps
from pathlib import Path
from time import perf_counter
from uuid import uuid4

_OBSERVERS = ContextVar('transition_observers', default=())
_ACTIVE = ContextVar('active_transition_observation', default=None)


@dataclass(frozen=True)
class State:
    id: str
    label: str
    kind: str = 'screen'
    entry: bool = False
    boundary: bool = False
    provider: str | None = None
    source: dict | None = None


@dataclass(frozen=True)
class Choice:
    transition_id: str
    label: str
    payload: object = None


@dataclass
class Result:
    outcome: str = 'completed'
    value: object = None
    reasons: tuple[str, ...] = ()
    feedback: str | None = None


@dataclass
class Definition:
    id: str
    label: str
    sources: tuple[str, ...]
    destinations: dict[str, tuple[str, ...]]
    handler: object
    engine_actions: tuple[str, ...] = ()
    guards: tuple[str, ...] = ()
    critical: bool = False
    recovery: bool = False
    provider: str | None = None
    questions: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()
    action_reference: str | None = None

    def document(self):
        fn = self.handler
        lines, start = inspect.getsourcelines(fn)
        return {key: deepcopy(value) for key, value in vars(self).items() if key != 'handler'} | {
            'source': {'module': fn.__module__, 'function': fn.__qualname__, 'line': start,
                       'end_line': start + len(lines) - 1},
            'source_file': inspect.getsourcefile(fn), 'instrumentation': 'registered_handler'}


class TraceSession:
    """Bounded in-memory trace. An optional sink receives safe structured records."""
    def __init__(self, *, session_id=None, sink=None, capacity=1000):
        self.session_id = session_id or uuid4().hex
        self.records = deque(maxlen=capacity)
        self.sink = sink
        self.sink_errors = 0

    def emit(self, record):
        record = deepcopy(record)
        self.records.append(record)
        # Telemetry failure must not turn an already committed action into a UI
        # rejection or cause a duplicate retry. Surface sink health separately.
        if self.sink is not None:
            try:
                self.sink(deepcopy(record))
            except Exception:
                self.sink_errors += 1
        for observer in _OBSERVERS.get():
            observer(deepcopy(record))


def stage(kind, *, state_id=None, feedback=None):
    observation = _ACTIVE.get()
    if observation is not None:
        observation['stages'].append({'kind': kind, 'state_id': state_id, 'feedback': feedback})


def active_transition_id():
    observation = _ACTIVE.get()
    return observation.get('transition_id') if observation else None


def observe_engine_result(kind, result, *, boundary='engine',idempotent=None):
    """Called with the actual host submission result; no payload text is copied."""
    observation = _ACTIVE.get()
    if observation is not None:
        item={'action_type': kind, 'ok': bool(result.get('ok')),
            'reasons': list(result.get('errors', [])),
            'commit_id': result.get('commit_id'), 'event_id': result.get('event_id'),
            'action_id': result.get('action_id'), 'version': result.get('state_version',result.get('version')),
            'mutation_count':len(result.get('mutations',[])), 'boundaries':[boundary],
            'idempotent':idempotent}
        prior=observation['engine_results'][-1] if observation['engine_results'] else None
        if boundary=='host' and prior and prior['boundaries']==['engine'] and all(
                prior[key]==item[key] for key in ('action_type','ok','commit_id','action_id')):
            prior['boundaries'].append('host')
            if item['version'] is not None:prior['version']=item['version']
        else:
            observation['engine_results'].append(item)
        stage('engine_result' if boundary=='engine' else 'submission_result')


def observe_submission(handler):
    """Observe the authoritative result without changing its event/envelope shape."""
    @wraps(handler)
    def submit(engine,command,*args,**kwargs):
        if _ACTIVE.get() is None:
            return handler(engine,command,*args,**kwargs)
        stage('engine_requested')
        # Observe retry resolution under the same re-entrant commit lock. A
        # detached UI revision cannot distinguish a retry from another client's
        # concurrent commit. The authoritative command/result remain unchanged.
        with engine._lock:
            prior=engine._prior(command) if isinstance(command,dict) else None
            result=handler(engine,command,*args,**kwargs)
            if isinstance(command,dict) and isinstance(command.get('kind'),str):
                observe_engine_result(command['kind'],result,idempotent=bool(prior and result.get('ok')))
        return result
    return submit


def accepted_outcome():
    observation=_ACTIVE.get()
    result=observation['engine_results'][-1] if observation and observation['engine_results'] else None
    if result is None or not result['ok'] or type(result['idempotent']) is not bool:
        raise ValueError('accepted_submission_receipt_not_observed')
    return 'idempotent' if result['idempotent'] else 'committed'


@contextmanager
def observe_transitions(callback):
    token = _OBSERVERS.set((*_OBSERVERS.get(), callback))
    try:
        yield
    finally:
        _OBSERVERS.reset(token)


class Registry:
    def __init__(self, id, *, state_of, revision_of, actor_of, cancelled_exception, dependency_modules=(),capture_ui=None,recover_ui=None):
        self.id = id
        self.state_of, self.revision_of, self.actor_of = state_of, revision_of, actor_of
        self.cancelled_exception = cancelled_exception
        self.states, self.transitions, self.bindings = {}, {}, {}
        self.dependency_modules = dependency_modules
        self.capture_ui,self.recover_ui=capture_ui,recover_ui

    def state(self, id, label, **kwargs):
        if id in self.states:
            raise ValueError('duplicate_transition_state: ' + id)
        frame = inspect.currentframe().f_back
        source = {'module':frame.f_globals['__name__'], 'function':frame.f_code.co_qualname,
                  'line':frame.f_lineno,'end_line':frame.f_lineno,'kind':'declaration'}
        self.states[id] = State(id, label, source=source, **kwargs)
        return id

    def register(self, id, label, *, sources, destinations, keys=(), **kwargs):
        def decorate(handler):
            if id in self.transitions:
                raise ValueError('duplicate_transition_id: ' + id)
            definition = Definition(id, label, tuple(sources),
                {outcome: tuple(targets) for outcome, targets in destinations.items()}, handler, **kwargs)
            self.transitions[id] = definition
            for source in sources:
                for key in keys:
                    if (source, key) in self.bindings:
                        raise ValueError('ambiguous_transition_binding: ' + source + ':' + key)
                    self.bindings[source, key] = id
            handler.transition_ids = (*getattr(handler,'transition_ids',()),id)
            return handler
        return decorate

    def choice(self, id, payload=None, *, label=None):
        definition = self.transitions[id]
        return Choice(id, definition.label if label is None else label, payload)

    def validate(self):
        from .runtime.engine import FIELDS
        for definition in self.transitions.values():
            states = set(definition.sources) | {s for states in definition.destinations.values() for s in states} | set(definition.questions)
            if states - self.states.keys():
                raise ValueError('unregistered_transition_state: ' + definition.id)
            if not definition.destinations or set(definition.engine_actions) - FIELDS.keys() or (
                    definition.action_reference is not None and definition.action_reference not in FIELDS):
                raise ValueError('invalid_transition_definition: ' + definition.id)
        return self

    def digest(self):
        modules = set(self.dependency_modules) | {fn.handler.__module__ for fn in self.transitions.values()}
        from importlib.util import find_spec
        sources = {module: hashlib.sha256(Path(find_spec(module).origin).read_bytes()).hexdigest()
                   for module in sorted(modules)}
        document = {'states': [asdict(s) for s in self.states.values()],
                    'transitions': [d.document() for d in self.transitions.values()], 'sources': sources}
        # Install locations are provenance, not part of portable identity/digest.
        for definition in document['transitions']:
            definition.pop('source_file', None)
        return hashlib.sha256(json.dumps(document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def execute(self, id, app, **parameters):
        definition = self.transitions[id]
        source = self.state_of(app)
        before = self.revision_of(app)
        actor = self.actor_of(app)
        saved_ui=self.capture_ui(app) if self.capture_ui else None
        observation = {'transition_id': id, 'engine_results': [], 'stages': []}
        token = _ACTIVE.set(observation)
        started = perf_counter()
        failure = None
        try:
            stage('requested', state_id=source)
            if source not in definition.sources:
                result = Result('blocked', reasons=('unexpected_source_state',), feedback='transition.blocked')
                app.notice = 'This interaction is unavailable from the current screen.'
            else:
                result = definition.handler(app, **parameters)
                if not isinstance(result, Result):
                    raise TypeError('transition_handler_requires_result: ' + id)
        except self.cancelled_exception:
            if self.recover_ui:self.recover_ui(app,saved_ui)
            else:app._reconstruction_modal=None
            if any(e['ok'] for e in observation['engine_results']):
                app.notice='The saved action remains in history. Returned to the previous view.'
                result=Result('error',reasons=('cancel_after_commit',),feedback='transition.saved_recovery')
            else:
                app.notice = 'Action cancelled. No incomplete action was submitted.'
                result = Result('cancelled', feedback='transition.cancelled')
        except KeyboardInterrupt:
            if self.recover_ui:self.recover_ui(app,saved_ui)
            app.finished=True
            app.notice='Interaction interrupted. Inspect saved history before retrying.'
            result=Result('aborted',reasons=('keyboard_interrupt',),feedback='transition.interrupted')
        except Exception as error:
            if self.recover_ui:self.recover_ui(app,saved_ui)
            else:app._reconstruction_modal=None
            app.notice='Interaction failed. Returned to the previous view; saved actions remain in history.'
            result = Result('error', reasons=(type(error).__name__,), feedback='transition.error')
            if self.recover_ui is None:failure = error
        finally:
            _ACTIVE.reset(token)
        destination = self.state_of(app)
        after = self.revision_of(app)
        engine = observation['engine_results']
        violations = []
        source_rejected=result.reasons==('unexpected_source_state',)
        if not source_rejected and result.outcome not in definition.destinations:
            violations.append('undeclared_outcome')
        elif not source_rejected and destination not in definition.destinations[result.outcome]:
            violations.append('undeclared_destination')
        if any(e['action_type'] not in definition.engine_actions for e in engine):
            violations.append('undeclared_engine_action')
        if result.outcome == 'committed' and (not engine or not all(e['ok'] and e['idempotent'] is False for e in engine)):
            violations.append('commit_not_observed')
        if result.outcome=='idempotent' and (not engine or not all(e['ok'] and e['idempotent'] is True for e in engine)):
            violations.append('idempotent_receipt_not_observed')
        if result.outcome in {'cancelled', 'blocked', 'rejected'} and any(e['ok'] or e['mutation_count'] for e in engine):
            violations.append('rejected_or_cancelled_action_committed')
        if not definition.engine_actions and engine:
            violations.append('navigation_changed_authoritative_state')
        observation['stages'].append({'kind': 'feedback', 'state_id': destination, 'feedback': result.feedback})
        record = {'schema_version': 'game-gamer/ui-trace/v1', 'transition_id': id,
            'session_id': _session(app).session_id, 'actor_id': actor, 'source_state': source,
            'requested_action': engine[-1]['action_type'] if engine else (definition.action_reference or (definition.engine_actions[0] if len(definition.engine_actions) == 1 else None)),
            'outcome': result.outcome, 'destination_state': destination,
            'duration_ms': round((perf_counter()-started)*1000, 3), 'correlation_id': uuid4().hex,
            'world_revision_before': before, 'world_revision_after': after,
            'reasons': list(result.reasons), 'feedback': result.feedback,
            'engine_results': engine, 'stages': observation['stages'], 'contract_violations': violations,
            'contract_id': self.id}
        _session(app).emit(record)
        if failure is not None:
            raise failure
        return result


def _session(app):
    session = getattr(app, 'transition_trace', None)
    if session is None:
        session = app.transition_trace = TraceSession()
    return session


def jsonl_sink(path):
    """Explicit opt-in trace output; creates a private file, copies no payloads."""
    import os
    path=Path(path)
    def write(record):
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(descriptor,'w',encoding='utf-8') as stream:
            stream.write(json.dumps(record,sort_keys=True,ensure_ascii=False)+'\n')
    return write
