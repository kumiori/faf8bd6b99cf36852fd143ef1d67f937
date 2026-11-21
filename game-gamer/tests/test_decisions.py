"""Decision projection contracts: real rules, read-only context, exports and audit."""
from copy import deepcopy
from io import StringIO
import json
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from game_gamer import ActionSubmission, Collective, SimulationBinding
from game_gamer.inspection import canonical_json, extract_decisions
from game_gamer.inspection.audit import audit_graph
from game_gamer.inspection.coverage import CoverageRecorder
from game_gamer.inspection.export import diff_graphs, export_graph
from game_gamer.runtime.engine import FIELDS
from game_gamer.tui import TerminalGame
from game_gamer.tui.viewport import LineViewport

EXAMPLE = Path(__file__).parents[1] / 'examples/minimal_collective/world.json'


def world():
    return Collective.start(json.loads(EXAMPLE.read_text()))


def action(game, actor, kind, key, **payload):
    target = next((payload[k] for k in ('agreement_id', 'invitation_id', 'resource_id', 'id', 'objective_id',
                                      'claim_id', 'target_id', 'merge_id') if k in payload), None)
    return ActionSubmission(action_id=key, actor_id=actor, scope_id=game.scope_id,
                            target_id=target, expected_revision=game.project()['version'], action_type=kind, payload=payload)


def binding(game, actor='sam'):
    return SimulationBinding(scope_id=game.scope_id, actor_id=actor)


def test_registry_is_the_source_of_all_actions_and_rules():
    graph = extract_decisions(interfaces='none')
    actions = {n['action_id']: n for n in graph['nodes'] if n['kind'] == 'action'}
    assert set(actions) == set(FIELDS)
    for kind, (required, optional) in FIELDS.items():
        assert actions[kind]['input_schema']['required'] == sorted(required)
        assert actions[kind]['input_schema']['optional'] == sorted(optional)
    assert any(g['reason'] == 'party_required' for g in actions['accept']['permissions'])
    assert any(g['reason'] == 'curator_required' for g in actions['merge_profiles']['permissions'])
    assert not any(g['reason'] == 'curator_required' for g in actions['recall_connection']['guards'])
    assert any(g['reason'] == 'claim_author_required' for g in actions['retract_relationship_claim']['guards'])
    assert not any(g['reason'] == 'claim_author_required' for g in actions['dispute_recollection']['guards'])
    assert any("'acceptances'" in effect['expression'] for effect in actions['accept']['effects'])
    assert any('invitation.sent' in event['expression'] for event in actions['send_contact']['events'])
    assert all(n['availability']['status'] == 'unknown' for n in actions.values())
    assert any(f['code'] == 'navigation_unavailable' for f in audit_graph(graph)['findings'])


def test_every_export_is_reproducible_and_preserves_identifiers():
    a, b = extract_decisions(interfaces='terminal'), extract_decisions(interfaces='terminal')
    for format in ('json', 'mermaid', 'dot'):
        exported = export_graph(a, format)
        assert exported == export_graph(b, format)
        assert all(n['id'] in exported for n in a['nodes'])
        assert all(e['id'] in exported for e in a['edges'])
    # An actual snapshot digest, independent of installation path.
    snapshot = json.loads((Path(__file__).parent / 'snapshots/decisions-engine.json').read_text())
    current = extract_decisions(interfaces='none')
    assert {format: hashlib.sha256(export_graph(current, format).encode()).hexdigest()
            for format in ('json', 'mermaid', 'dot')} == snapshot


def test_context_uses_real_permissions_and_never_commits(tmp_path):
    definition = json.loads(EXAMPLE.read_text())
    game = Collective.start(definition, path=tmp_path / 'world.sqlite')
    request = action(game, 'sam', 'send_contact', 'contact', id='contact', recipient_id='jo', message='Practice?')
    assert game.submit(request, binding=binding(game))['ok']
    before, saved = game.history(), (tmp_path / 'world.sqlite').read_bytes()
    jo = extract_decisions(interfaces='terminal', collective=game, binding=binding(game, 'jo'), limit=1)
    sam = extract_decisions(interfaces='terminal', collective=game, binding=binding(game), limit=100)
    def row(graph, kind): return next(n for n in graph['nodes'] if n.get('action_id') == kind)
    assert row(jo, 'respond_contact')['availability']['status'] == 'enabled'
    assert row(sam, 'respond_contact')['availability'] == {
        'status': 'disabled', 'reasons': ['recipient_required'], 'basis': 'validated_existing_targets'}
    assert row(jo, 'respond_contact')['contextual_choices']['truncated']
    assert row(jo, 'propose')['availability']['status'] == 'unknown'
    assert row(jo, 'advance_time')['availability']['status'] == 'disabled'
    assert row(jo, 'advance_time')['availability']['reasons'] == ['facilitator_required']
    assert row(jo, 'review_curation_request')['availability']['status'] == 'disabled'
    assert row(jo, 'review_curation_request')['availability']['reasons'] == ['curator_required']
    assert not any(n.get('action_id') == 'merge_profiles' for n in jo['nodes'])
    assert not any(n['kind'] == 'screen' for n in jo['nodes'])
    assert game.history() == before and (tmp_path / 'world.sqlite').read_bytes() == saved
    assert canonical_json(jo) == canonical_json(extract_decisions(
        interfaces='terminal', collective=game, binding=binding(game, 'jo'), limit=1))


def test_coverage_records_observed_results_and_rejects_stale_manifests():
    graph = extract_decisions(interfaces='terminal')
    recorder = CoverageRecorder(graph)
    game = world()
    with recorder.capture('test-contact'):
        request = action(game, 'sam', 'send_contact', 'contact', id='contact', recipient_id='jo', message='Practice?')
        assert game.submit(request, binding=binding(game))['ok']
        # Exact retry is observed but does not invent a distinct transition.
        assert game.submit(request, binding=binding(game))['ok']
        assert not game.submit(action(game, 'sam', 'respond_contact', 'denied', invitation_id='contact', response='accept'),
                               binding=binding(game))['ok']
        ui = TerminalGame(collective=game, binding=binding(game), viewport=LineViewport(StringIO('1\n'), StringIO()))
        ui.prepare_screen()
        ui.forms.confirm('A confirmation created by this test is not a registered prompt')
    observed = recorder.document()
    assert {key: value for key, value in observed['transitions'].items() if key.startswith('engine.')} == {
        'engine.respond_contact.rejected': ['test-contact'], 'engine.send_contact.allowed': ['test-contact']}
    assert all('created by this test' not in key for key in observed['transitions'])
    covered = extract_decisions(interfaces='terminal', coverage=observed)
    assert next(e for e in covered['edges'] if e['id'] == 'engine.send_contact.allowed')['test_refs'] == ['test-contact']
    assert not next(e for e in covered['edges'] if e['id'] == 'engine.respond_contact.allowed')['test_refs']
    observed['implementation_digest'] = 'stale'
    with pytest.raises(ValueError, match='stale'):
        extract_decisions(interfaces='terminal', coverage=observed)


def test_audit_detects_broken_unreachable_and_recovery_paths_and_keeps_exceptions():
    graph = {'nodes': [
        {'id': 'home', 'kind': 'screen', 'entry_point': True},
        {'id': 'orphan', 'kind': 'screen'}, {'id': 'question', 'kind': 'question'}],
        'edges': [
            {'id': 'start', 'source': 'home', 'target': 'question', 'kind': 'navigation', 'declared_option': True},
            {'id': 'bad', 'source': 'question', 'target': 'missing', 'kind': 'navigation', 'declared_option': True},
            {'id': 'unmapped', 'source': 'question', 'target': None, 'kind': 'navigation', 'declared_option': True}],
        'diagnostics': []}
    report = audit_graph(graph, exceptions=[{'code': 'unreachable_screen', 'id': 'orphan', 'reason': 'A retained deprecated screen.'}])
    assert report['metrics']['unreachable_screens'] == 1
    assert report['metrics']['unmapped_options'] == 1
    assert report['metrics']['missing_recovery_paths'] == 2
    assert any(f.get('exception') for f in report['findings'])
    assert any(f['code'] == 'broken_reference' for f in report['findings'])
    assert not report['passed']


def test_diff_reports_all_requested_change_categories_and_ignores_line_shifts():
    original = extract_decisions(interfaces='none')
    changed = deepcopy(original)
    edge = next(e for e in changed['edges'] if e['id'] == 'engine.accept.allowed')
    edge.update(action_id='reject', guard=['new guard'], permissions=['new authority'], recovery=True)
    changed['nodes'].append({'id': 'new-screen', 'kind': 'screen'})
    diff = diff_graphs(original, changed)
    assert diff['screens']['added'] == ['new-screen']
    assert all(diff['changed'][key] for key in ('action_mappings', 'guards', 'permissions', 'recovery_paths'))
    unchanged = deepcopy(original)
    unchanged['nodes'][0]['source']['line'] += 1
    assert not any(diff_graphs(original, unchanged)['changed'].values())


def test_cli_all_formats_audit_context_and_diff(tmp_path):
    def run(*args):
        return subprocess.run([sys.executable, '-m', 'game_gamer', 'inspect', 'decisions', *map(str, args)],
                              capture_output=True, text=True)
    for format in ('json', 'mermaid', 'dot'):
        path = tmp_path / format
        result = run('--interface', 'none', '--format', format, '--output', path)
        assert result.returncode == 0, result.stderr
        assert path.stat().st_size
    audit_file = tmp_path / 'audit.json'
    result = run('--interface', 'none', '--audit', '--audit-output', audit_file)
    assert result.returncode == 0 and 'DECISION GRAPH AUDIT' in result.stdout
    assert json.loads(audit_file.read_text())['metrics']['engine_actions'] == len(FIELDS)
    assert json.loads(run('--diff', tmp_path / 'json', tmp_path / 'json').stdout)['options'] == {'added': [], 'removed': []}
    result = run('--interface', 'none', '--contextual', '--world', EXAMPLE, '--actor', 'jo')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['mode'] == 'contextual'
    assert run('--contextual').returncode == 2


def test_dynamic_roster_is_symbolic_and_scope_is_closed():
    graph = extract_decisions(interfaces='terminal')
    assert any(e.get('dynamic_provider') for e in graph['edges'])
    scope = extract_decisions(interfaces='terminal', scope='ecosystem')
    ids = {n['id'] for n in scope['nodes']}
    assert all(e['source'] in ids and (e.get('target') is None or e['target'] in ids) for e in scope['edges'])
    assert len(scope['nodes']) < len(graph['nodes'])
    # All declared, unresolved choices remain visible to the audit.
    assert any(f['code'] == 'unresolved_dynamic_provider' for f in audit_graph(graph)['findings'])
    from importlib.util import find_spec
    if find_spec('commons_game') is None:
        with pytest.raises(ValueError, match='interface_unavailable: commons'):
            extract_decisions(interfaces='commons', level='decision')
    else:
        decisions = extract_decisions(interfaces='commons', level='decision')
        assert decisions['edges'] and all(e['level'] == 'decision' for e in decisions['edges'])


def test_source_adapters_keep_ids_when_unrelated_lines_move(tmp_path, monkeypatch):
    from game_gamer.inspection import InterfaceAdapter
    monkeypatch.syspath_prepend(str(tmp_path))
    source = tmp_path / 'decision_fixture.py'
    implementation = 'def run(app):\n    return app.choose("Choose", ["One", "Two"])\n'
    source.write_text(implementation)
    adapter = InterfaceAdapter('fixture', ('decision_fixture',), ('decision_fixture.run',))
    before = extract_decisions(interfaces='none', adapters=[adapter])
    source.write_text('# An unrelated comment\n\n' + implementation)
    after = extract_decisions(interfaces='none', adapters=[adapter])
    assert [n['id'] for n in before['nodes']] == [n['id'] for n in after['nodes']]
    assert [e['id'] for e in before['edges']] == [e['id'] for e in after['edges']]
    assert before['implementation_digest'] != after['implementation_digest']


def test_missing_optional_interface_is_reported_without_losing_engine(monkeypatch):
    from game_gamer.inspection import source
    original = source.load
    def without_terminal(module):
        if module.startswith('game_gamer.tui.'):
            raise ValueError('source_unavailable: ' + module)
        return original(module)
    monkeypatch.setattr(source, 'load', without_terminal)
    graph = extract_decisions(interfaces='terminal')
    assert sum(n['kind'] == 'action' for n in graph['nodes']) == len(FIELDS)
    assert graph['interfaces'][0]['status'] == 'unavailable'
    assert any(f['code'] == 'interface_unavailable' for f in audit_graph(graph)['findings'])
