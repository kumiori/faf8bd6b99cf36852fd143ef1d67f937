"""Scenario descriptions are presentation metadata, not engine objectives/worlds."""

import json
from copy import deepcopy
from pathlib import Path

from .i18n import t
from .scenario import SCENARIOS, definition


def catalogue(world):
    records=json.loads((Path(__file__).parent/'scenarios/workshop-catalogue.json').read_text())
    for name in SCENARIOS:
        if name=='montreal-commons':
            continue  # An ecosystem world and generic context are not a scenario.
        spec=definition(name)
        records.append({'id':'fixture:'+name,'title':spec['title']+t('cli.play.synthetic_fixture'),
            'description':spec['description'],'context':t('scenarios.an_installed_deterministic_regression_situation'),
            'status':t('scenarios.playable_synthetic_fixture') if world['configuration']['world']['scenario']==name else
                     t('scenarios.separate_saved_world_description_only'),
            'provenance':{'kind':'synthetic_fixture','source_path':'commons_game/scenarios/'+name+'.json'},
            'possible_objectives':[{'title':o['label']} for o in spec.get('objectives',[])],
            'conditions':[t('scenarios.a_fixture_does_not_confer')],
            'world_bindings':{name:{o['id']:t('scenarios.registered_objective_in_this_synthetic') for o in spec.get('objectives',[])}}})
    return deepcopy(records)


def objectives_for(record, world):
    bindings=record.get('world_bindings',{}).get(world['configuration']['world']['scenario'],{})
    return [(world['objectives'][key],meaning) for key,meaning in bindings.items() if key in world['objectives']]


def scenarios_for(objective_id,world):
    return [record for record in catalogue(world) if any(o['id']==objective_id for o,_ in objectives_for(record,world))]
