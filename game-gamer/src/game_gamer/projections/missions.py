"""Read mission progress from verified evidence in the shared world."""

from copy import deepcopy

from ..runtime import missions


def project_mission(world, mission_id):
    definition = missions.definitions(world)[mission_id]
    catalogue = world['configuration'][missions.CATALOGUE_ID]
    records = missions.contributions(world)
    local = [record for record in records if record['mission_id'] == mission_id]
    outcomes = [record for record in world['evidence'].values()
                if record['kind'] == 'mission_verification' and record['status'] == 'verified']
    requirements = [
        {'id': ident, **catalogue['requirements'][ident],
         'evidence_ids': [item['id'] for item in outcomes if item['requirement_id'] == ident]}
        for ident in definition['requirements']
    ]
    verified_steps = {record['proposal_id'] for record in local
                      if 'proposal_id' in record and record.get('evidence_id') in world['evidence']
                      and world['evidence'][record['evidence_id']]['status'] == 'verified'}
    steps = [
        {**record, 'status': 'verified' if record['id'] in verified_steps else 'proposed'}
        for record in local if record.get('proposal_type') == 'step'
    ]
    return deepcopy({
        **definition,
        'players': missions.members(world, mission_id),
        'requirements': requirements,
        'routes': [{'steps': steps}] if steps else [],
        'contributions': [record for record in local if record['type'] != 'join'],
        'shared_commitments': [
            record for record in records if record['mission_id'] != mission_id
            and record.get('requirement_id') in definition['requirements']
            and record['status'] in {'accepted', 'verified'}
        ],
        'outcomes': [item for item in outcomes if item['requirement_id'] in definition['requirements']
                     or item['mission_id'] == mission_id],
        'criteria_satisfied': bool(requirements) and all(item['evidence_ids'] for item in requirements),
        'complete': definition['status'] == 'completed' if definition.get('lifecycle_schema') else
                    all(item['evidence_ids'] for item in requirements),
    })
