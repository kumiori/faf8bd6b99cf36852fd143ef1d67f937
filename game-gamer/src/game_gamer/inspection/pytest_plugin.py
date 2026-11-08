"""Opt-in: pytest -p game_gamer.inspection.pytest_plugin --decision-coverage FILE."""
from pathlib import Path
import pytest
from . import canonical_json, extract_decisions
from .coverage import CoverageRecorder
from .evidence import TransitionEvidence


def pytest_addoption(parser):
    parser.addoption('--decision-coverage', help='Write observed decision transition coverage JSON')
    parser.addoption('--decision-interface', default='auto', choices=['auto', 'terminal', 'commons', 'none'])
    parser.addoption('--transition-evidence',help='Write passed-test evidence for the executable reconstruction contract')


def pytest_configure(config):
    if config.getoption('--decision-coverage'):
        config._decision_graph=extract_decisions(interfaces=config.getoption('--decision-interface'))
        config._decision_recorder = CoverageRecorder(config._decision_graph)
    if config.getoption('--transition-evidence'):
        from .contracts import reconstruction_registry
        config._transition_evidence=TransitionEvidence(reconstruction_registry())


@pytest.fixture(autouse=True)
def _capture_decision_transitions(request):
    from contextlib import ExitStack
    import tomllib
    project=request.config.rootpath/'pyproject.toml'
    prefix=tomllib.loads(project.read_text()).get('project',{}).get('name',request.config.rootpath.name) if project.exists() else request.config.rootpath.name
    ref=prefix+':'+request.node.nodeid
    with ExitStack() as stack:
        if hasattr(request.config,'_decision_recorder'):
            recorder=CoverageRecorder(request.config._decision_graph)
            stack.enter_context(recorder.capture(ref))
            request.node._decision_trial=recorder
        if hasattr(request.config,'_transition_evidence'):
            trial=stack.enter_context(request.config._transition_evidence.capture(ref))
            request.node._transition_trial=trial
        yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item,call):
    outcome=yield
    report=outcome.get_result()
    reports=getattr(item,'_decision_reports',[])
    reports.append(report);item._decision_reports=reports
    if report.when!='teardown' or not all(r.passed for r in reports):
        return
    if hasattr(item,'_decision_trial'):
        target=item.config._decision_recorder
        for id,refs in item._decision_trial.transitions.items():
            target.transitions[id].update(refs)
    if hasattr(item,'_transition_trial'):
        item.config._transition_evidence.accept(item._transition_trial)


def pytest_sessionfinish(session):
    recorder = getattr(session.config, '_decision_recorder', None)
    if recorder is not None:
        Path(session.config.getoption('--decision-coverage')).write_text(canonical_json(recorder.document()), encoding='utf-8')
    evidence=getattr(session.config,'_transition_evidence',None)
    if evidence is not None:
        Path(session.config.getoption('--transition-evidence')).write_text(canonical_json(evidence.document()),encoding='utf-8')
