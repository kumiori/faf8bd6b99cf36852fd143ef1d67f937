"""Application-owned layer vocabulary and navigation metadata."""
from .i18n import t

MONTREAL_LAYER = 'montreal_2026_reconstructed'
LAYER_STYLES = {MONTREAL_LAYER: ('#a7b6ff', 'solid')}
LAYER_CATEGORIES = {MONTREAL_LAYER: 'Montréal source topology'}
MAJOR_ROUTES = frozenset({'matrix', 'gathering', 'scenarios', 'exercises', 'history',
                          'montreal_network', 'montreal_network_graph', 'network'})


def layer_label(layer):
    return t('network.montreal_topology') if layer == MONTREAL_LAYER else layer
