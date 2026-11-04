"""Read-only explanation of existing Gathering gates; feasibility is not outcome."""
def conditions(world, objective):
    invitations=[r for r in world['relationships'].values() if r['kind']=='invited' and r.get('objective_id')==objective['id']]
    lines=[f"Pending invitations: {sum(r['status']=='proposed' for r in invitations)}",
           f"Accepted invitations: {sum(r['status']=='accepted' for r in invitations)}",
           f"Required attending parties at activation: {objective['success']['minimum_attendees']}",
           'Invitation acceptance records simulated attendance intent, not verified realisation.']
    for agreement in world['agreements'].values():
        if agreement['objective_id']!=objective['id']: continue
        version=agreement['versions'][agreement['current_version']-1]
        attendance={r['target_id'] for r in invitations if r['status']=='accepted'}|{agreement['created_by']}
        count=len(attendance & set(agreement['parties']))
        lines.append('Agreement: '+agreement['label'])
        lines.append(f"  Attending parties (including proposer): {count}/{objective['success']['minimum_attendees']}")
        lines.append(f"  Exact-version party acceptances: {len(version['acceptances'])}/{len(agreement['parties'])}")
        lines.append('  Lifecycle: '+agreement['status']+'; outcome: '+agreement['outcome_status'])
    lines += ['Activation also requires the governing policy and available/reconciled resources.',
              'Hube venue/date/accommodation/documentation feasibility remains a separate regression engine; no cross-world satisfaction is inferred.']
    return lines
