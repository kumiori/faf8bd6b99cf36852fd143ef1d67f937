"""Default visual vocabulary for neutral collective objects."""

from dataclasses import dataclass

from .i18n import message_key, t


@dataclass(frozen=True)
class ObjectStyle:
    label_key: str
    plural_key: str
    symbol: str
    plain: str
    colour: str

    @property
    def label(self):
        return t(self.label_key)

    @property
    def plural(self):
        return t(self.plural_key)


OBJECTS = {
    'person': ObjectStyle(message_key('objects.person.singular'), message_key('objects.person.plural'), '●', '(P)', '#71d7e5'),
    'organisation': ObjectStyle(message_key('objects.organisation.singular'), message_key('objects.organisation.plural'), '◆', '(O)', '#c4a7e7'),
    'resource': ObjectStyle(message_key('objects.resource.singular'), message_key('objects.resource.plural'), '■', '(R)', '#e8b65e'),
    'agreement': ObjectStyle(message_key('objects.agreement.singular'), message_key('objects.agreement.plural'), '⬡', '(C)', '#d88356'),
    'invitation': ObjectStyle(message_key('objects.invitation.singular'), message_key('objects.invitation.plural'), '✉', '(I)', '#e8b65e'),
    'objective': ObjectStyle(message_key('objects.objective.singular'), message_key('objects.objective.plural'), '◎', '(G)', '#eee8d5'),
    'policy': ObjectStyle(message_key('objects.policy.singular'), message_key('objects.policy.plural'), '◇', '(Y)', '#bc91af'),
    'capacity': ObjectStyle(message_key('objects.capacity.singular'), message_key('objects.capacity.plural'), '▲', '(+)', '#a3bd95'),
    'need': ObjectStyle(message_key('objects.need.singular'), message_key('objects.need.plural'), '▽', '(-)', '#8caac4'),
    'evidence': ObjectStyle(message_key('objects.evidence.label'), message_key('objects.evidence.label'), '▣', '(E)', '#bbbbaa'),
}
