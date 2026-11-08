"""Passed-test evidence linked to explicit runtime transition observations."""
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

from ..transitions import observe_transitions

_CHECKS = ContextVar('verified_transition_checks', default=None)


def verified(transition_id, *checks):
    """Record checks only after the test has asserted the corresponding property.

    The pytest plugin publishes these only if setup, call and teardown all pass.
    Check names are explicit assertions, never inferred from test names.
    """
    capture = _CHECKS.get()
    if capture is not None:
        capture['checks'].append((transition_id, tuple(checks)))


class TransitionEvidence:
    def __init__(self, registry):
        self.registry = registry
        self.contract_digest = registry.digest()
        self.trials = []

    @contextmanager
    def capture(self, test_ref):
        trial={'test_ref':test_ref,'records':[],'checks':[]}
        token=_CHECKS.set(trial)
        try:
            with observe_transitions(trial['records'].append):
                yield trial
        finally:
            _CHECKS.reset(token)

    def accept(self,trial):
        """The caller must have verified that the test passed, including teardown."""
        self.trials.append(deepcopy(trial))

    def document(self):
        rows={}
        for trial in self.trials:
            ref=trial['test_ref']
            observed=set()
            for record in trial['records']:
                if record['contract_id']!=self.registry.id:
                    continue
                id=record['transition_id']; observed.add(id)
                row=rows.setdefault(id,{'test_refs':set(),'outcomes':set(),'checks':set(),
                    'committed_engine_actions':set(),'observed_questions':set(),'contract_violations':set(),
                    'check_test_refs':defaultdict(set),'observations':[]})
                row['test_refs'].add(ref);row['outcomes'].add(record['outcome'])
                row['contract_violations'].update(record['contract_violations'])
                row['observed_questions'].update(s['state_id'] for s in record['stages'] if s['kind']=='question' and s['state_id'])
                if record['outcome']=='committed':
                    row['committed_engine_actions'].update(e['action_type'] for e in record['engine_results'] if e['ok'])
                row['observations'].append({'test_ref':ref,'trace':record})
            for id, checks in trial['checks']:
                if id not in observed:
                    raise ValueError('verification_check_without_observed_transition: '+id)
                rows[id]['checks'].update(checks)
                for check in checks:rows[id]['check_test_refs'][check].add(ref)
        document={}
        for id,row in sorted(rows.items()):
            document[id]={key:sorted(value) if isinstance(value,set) else
                          {k:sorted(v) for k,v in sorted(value.items())} if key=='check_test_refs' else value
                          for key,value in row.items()}
        return {'schema_version':'game-gamer/transition-evidence/v1','contract_id':self.registry.id,
                'contract_digest':self.contract_digest,'source':'passed_test_runtime_traces',
                'passed_test_refs':sorted({trial['test_ref'] for trial in self.trials}),
                'transitions':document}
