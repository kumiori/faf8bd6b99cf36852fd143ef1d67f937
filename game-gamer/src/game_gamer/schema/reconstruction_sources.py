"""Validate supplied transcriptions and source references without inferring links."""
from ..model import require

SOURCE_FIELDS = {
    'participant_statement': {'actor_id', 'statement'},
    'whiteboard_connection': {'source_id', 'target_id', 'directed', 'observation'},
    'whiteboard_photo': set(),
}


def prepare_reconstruction_sources(rows, actor_ids):
    """Return canonical evidence records for a trusted host's import boundary."""
    evidence = {}
    require(isinstance(rows, list), 'invalid_reconstruction_sources')
    for row in rows:
        require(isinstance(row, dict), 'invalid_reconstruction_source')
        kind = row.get('kind')
        require(isinstance(kind, str) and kind in SOURCE_FIELDS, 'unsupported_reconstruction_source')
        fields = {'id', 'kind', 'context_id', 'reference'} | SOURCE_FIELDS[kind]
        require(set(row) == fields, 'invalid_reconstruction_source_fields')
        for name in ('id', 'context_id', 'reference'):
            require(isinstance(row[name], str) and row[name].strip() == row[name] and row[name],
                    'invalid_reconstruction_source_reference')
        require(not row['id'].startswith('evidence_'), 'reserved_evidence_id')
        require(row['id'] not in evidence, 'duplicate_reconstruction_source')
        if kind == 'participant_statement':
            require(isinstance(row['actor_id'], str) and row['actor_id'] in actor_ids and isinstance(row['statement'], str) and row['statement'].strip(),
                    'invalid_participant_statement')
        if kind == 'whiteboard_connection':
            require(isinstance(row['source_id'], str) and isinstance(row['target_id'], str)
                    and row['source_id'] in actor_ids and row['target_id'] in actor_ids
                    and row['source_id'] != row['target_id'], 'invalid_whiteboard_endpoints')
            require((row['directed'] is None or type(row['directed']) is bool) and isinstance(row['observation'], str) and
                    row['observation'] in {'possible', 'transcribed', 'verified_transcription'},
                    'invalid_whiteboard_observation')
        evidence[row['id']] = {**row, 'status': 'reported', 'provenance': {
            'kind': 'historical_source', 'reference': row['reference']}}
    return evidence
