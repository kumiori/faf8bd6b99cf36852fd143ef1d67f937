"""Compare the migrated host to recorded pre-extraction trajectories."""
import json
from pathlib import Path

import pytest

from commons_game.engine import digest
from commons_game.player import ActorSession
from commons_game.scenario import definition, load_scenario

BASELINE = json.loads((Path(__file__).parent / 'fixtures/game-gamer-baseline.json').read_text())


def check_prefix(game, expected):
    world = game.get_world()
    assert digest(world) == expected['world']
    assert digest(game.project('network')) == expected['network']
    assert digest(game.project('log')) == expected['history']
    assert digest({actor_id: ActorSession(game, actor_id).inbox_records()
                   for actor_id, actor in world['actors'].items() if actor['status'] == 'active'}) == expected['inbox']
    assert game.replay().get_world() == world


@pytest.mark.parametrize('name', BASELINE['cases'])
def test_frozen_trajectory(name):
    case = BASELINE['cases'][name]
    assert digest(definition(name)) == case['definition_sha256']
    game = load_scenario(name)
    assert game.get_world()['configuration']['world']['schema_version'] == case['world_schema']
    check_prefix(game, case['initial'])
    for step in case['steps']:
        assert game.submit(step['command'])['errors'] == step['errors']
        check_prefix(game, step)
