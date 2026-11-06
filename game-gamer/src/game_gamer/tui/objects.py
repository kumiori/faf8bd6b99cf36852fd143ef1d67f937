"""Default visual vocabulary for neutral collective objects."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectStyle:
    label: str
    plural: str
    symbol: str
    plain: str
    colour: str


OBJECTS = {
    'person': ObjectStyle('Person', 'People', '●', '(P)', '#71d7e5'),
    'organisation': ObjectStyle('Organisation', 'Organisations', '◆', '(O)', '#c4a7e7'),
    'resource': ObjectStyle('Resource', 'Resources', '■', '(R)', '#e8b65e'),
    'agreement': ObjectStyle('Contract', 'Contracts', '⬡', '(C)', '#d88356'),
    'invitation': ObjectStyle('Invitation', 'Invitations', '✉', '(I)', '#e8b65e'),
    'objective': ObjectStyle('Objective', 'Objectives', '◎', '(G)', '#eee8d5'),
    'policy': ObjectStyle('Governance policy', 'Governance policies', '◇', '(Y)', '#bc91af'),
    'capacity': ObjectStyle('Capacity', 'Capacities', '▲', '(+)', '#a3bd95'),
    'need': ObjectStyle('Need', 'Needs', '▽', '(-)', '#8caac4'),
    'evidence': ObjectStyle('Evidence', 'Evidence', '▣', '(E)', '#bbbbaa'),
}
