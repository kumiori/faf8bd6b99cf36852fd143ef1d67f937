"""Apply host display labels to the reusable terminal network."""
from game_gamer.tui.network import CATEGORIES as BASE_CATEGORIES
from game_gamer.tui.network import LAYERS as BASE_LAYERS
from game_gamer.tui.network import OBJECT_TYPES as OBJECT_TYPES
from game_gamer.tui.network import PRIORITY as PRIORITY
from game_gamer.tui.network import category_label as base_category_label
from game_gamer.tui.network import draw_graph as render
from game_gamer.tui.network import edge_category as base_edge_category
from game_gamer.tui.network import focus_graph as focus
from game_gamer.tui.network import object_type_label as object_type_label

from .presentation import display_label
from .network_config import LAYER_STYLES, LAYER_CATEGORIES, layer_label

LAYERS = {**BASE_LAYERS, **LAYER_STYLES}
CATEGORIES = (*BASE_CATEGORIES, *LAYER_CATEGORIES.values())


def category_label(category):
    layer = next((key for key, value in LAYER_CATEGORIES.items() if value == category), None)
    return layer_label(layer) if layer else base_category_label(category)


def edge_category(edge, lookup):
    return base_edge_category(edge, lookup, layer_categories=LAYER_CATEGORIES)


def focus_graph(*args, **kwargs):
    return focus(*args, **kwargs, labeler=display_label, layer_styles=LAYER_STYLES, layer_categories=LAYER_CATEGORIES)


def draw_graph(*args, **kwargs):
    return render(*args, **kwargs, labeler=display_label)
