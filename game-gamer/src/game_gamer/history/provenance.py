"""Epistemic classification for records and inferred projections."""
from enum import StrEnum


class EpistemicStatus(StrEnum):
    RECORDED_FACT = 'recorded_fact'
    DECLARATION = 'declaration'
    CORROBORATION = 'corroboration'
    HISTORICAL_EVIDENCE = 'historical_evidence'
    INFERENCE = 'inference'
    PROPOSAL = 'proposal'
    ACKNOWLEDGED = 'acknowledged'
    VERIFIED_OUTCOME = 'verified_outcome'
    UNKNOWN = 'unknown'


def epistemic_status(record):
    kind, status = record.get('kind'), record.get('status')
    provenance = record.get('provenance', {})
    source_status = provenance.get('epistemic_status')
    if kind == 'corroborated_recollection':
        return EpistemicStatus.CORROBORATION
    if provenance.get('kind') == 'historical_source':
        return EpistemicStatus.HISTORICAL_EVIDENCE
    if kind in {'contact_invitation', 'invited'}:
        return EpistemicStatus.PROPOSAL
    if kind == 'acknowledged_connection' and status == 'acknowledged':
        return EpistemicStatus.ACKNOWLEDGED
    if record.get('outcome_status') == 'verified' or (kind == 'independent_verification' and status == 'verified'):
        return EpistemicStatus.VERIFIED_OUTCOME
    if status == 'inferred' or source_status == 'inferred':
        return EpistemicStatus.INFERENCE
    if status in {'draft', 'proposed', 'negotiating'}:
        return EpistemicStatus.PROPOSAL
    if source_status == 'documented':
        return EpistemicStatus.RECORDED_FACT
    if source_status == 'unknown':
        return EpistemicStatus.UNKNOWN
    if status == 'reported' or source_status == 'source_assertion' or provenance.get('kind') == 'player_declaration':
        return EpistemicStatus.DECLARATION
    return EpistemicStatus.UNKNOWN
