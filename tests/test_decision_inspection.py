"""The host's implemented paths remain visible in the portable inspection API."""
import json
from pathlib import Path
import subprocess
import sys

from game_gamer.inspection import extract_decisions
from game_gamer.inspection.audit import audit_graph


def test_host_reconstruction_menu_preserves_distinct_authoritative_branches():
    graph = extract_decisions(interfaces='commons')
    options=[e for e in graph['edges'] if e['id'].startswith('exercise.reconstruct.connect.') and e.get('declared_option')]
    by_action={kind:e for e in options for kind in e.get('engine_actions',[])}
    assert {'recall_connection', 'send_contact', 'record_prior_relationship',
            'dispute_recollection', 'retract_relationship_claim'} <= by_action.keys()
    assert all(e['transition_id']==e['id'] and e['instrumentation']=='registered_handler' for e in by_action.values())
    assert any(e['id']=='exercise.reconstruct.connect.cancel' and e['recovery'] for e in options)
    path_menu = next(n for n in graph['nodes'] if n['kind'] == 'question'
                     and n['source']['function'] == 'FullScreenTerminal.choose_mode')
    assert {'ecosystem', 'gathering', 'scenarios', 'exercises'} <= {
        e['option'] for e in graph['edges'] if e['source'] == path_menu['id']}
    assert any(e.get('dynamic_provider') and e['dynamic_provider'].get('provider_id')=='game_gamer.projections.participants.ParticipantDirectory.browse'
               for e in graph['edges'])
    audit = audit_graph(graph)
    assert audit['metrics']['screens'] == sum(n['kind'] == 'screen' for n in graph['nodes'])
    assert audit['metrics']['unmapped_options'] > 0
    assert any(d['code'] == 'source_adapter_incomplete' for d in audit['findings'])


def test_cli_refuses_to_overwrite_a_world_snapshot(tmp_path):
    snapshot = tmp_path / 'world.json'
    data = (Path(__file__).parents[1] / 'game-gamer/examples/minimal_collective/world.json').read_bytes()
    snapshot.write_bytes(data)
    result = subprocess.run([sys.executable, '-m', 'game_gamer', 'inspect', 'decisions', '--contextual',
                             '--world', str(snapshot), '--actor', 'sam', '--output', str(snapshot)],
                            capture_output=True, text=True)
    assert result.returncode == 2 and 'must not overwrite inputs' in result.stderr
    assert snapshot.read_bytes() == data
