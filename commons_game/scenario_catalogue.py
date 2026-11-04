"""Scenario descriptions are presentation metadata, not engine objectives/worlds."""
from copy import deepcopy
import json
from pathlib import Path

from .scenario import SCENARIOS, definition


def catalogue(world):
    records=json.loads((Path(__file__).parent/'scenarios/workshop-catalogue.json').read_text())
    for name in SCENARIOS:
        if name=='montreal-commons':
            continue  # An ecosystem world and generic context are not a scenario.
        spec=definition(name)
        records.append({'id':'fixture:'+name,'title':spec['title']+' · synthetic fixture',
            'description':spec['description'],'context':'An installed deterministic regression situation, not empirical workshop evidence.',
            'status':'PLAYABLE SYNTHETIC FIXTURE' if world['configuration']['world']['scenario']==name else
                     'SEPARATE SAVED WORLD / description only here',
            'provenance':{'kind':'synthetic_fixture','source_path':'commons_game/scenarios/'+name+'.json'},
            'possible_objectives':[{'title':o['label']} for o in spec.get('objectives',[])],
            'conditions':['A fixture does not confer real consent or institutional authority.'],
            'world_bindings':{name:{o['id']:'Registered objective in this synthetic scenario.' for o in spec.get('objectives',[])}}})
    return deepcopy(records)


def objectives_for(record, world):
    bindings=record.get('world_bindings',{}).get(world['configuration']['world']['scenario'],{})
    return [(world['objectives'][key],meaning) for key,meaning in bindings.items() if key in world['objectives']]


def scenarios_for(objective_id,world):
    return [record for record in catalogue(world) if any(o['id']==objective_id for o,_ in objectives_for(record,world))]
