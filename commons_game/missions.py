"""Install the curated Montréal mission pack in the existing shared world."""

import json
from copy import deepcopy
from pathlib import Path

from game_gamer.runtime.missions import CATALOGUE_ID


def missions_installed(world):
    return CATALOGUE_ID in world['configuration']


def install_missions(game):
    """Trusted setup, also used to extend saved Montréal worlds in place."""
    with game._lock:
        before = game.get_world()
        configuration = before['configuration']
        if configuration['world']['scenario'] != 'montreal-commons' or missions_installed(before):
            return {'ok': True, 'changed': False}

        path = Path(__file__).parent / 'scenarios' / 'montreal-missions.json'
        pack = json.loads(path.read_text(encoding='utf-8'))
        definitions = pack.pop('missions')
        source_fields = ('id', 'title', 'need', 'target', 'structural_result', 'principal_means', 'provenance')
        pack['scenario_cards'] = {record['id']: {key: record[key] for key in source_fields}
                                  for record in definitions}
        after = deepcopy(before)
        after['configuration'][CATALOGUE_ID] = {'id': CATALOGUE_ID, 'status': 'active', **pack}
        for definition in definitions:
            after['configuration'][definition['id']] = {
                'kind': 'mission_definition', 'curation': {'kind': 'curated_gameplay'}, **definition,
            }
        game._commit(before, after, 'missions.installed')
        return {'ok': True, 'changed': True}
