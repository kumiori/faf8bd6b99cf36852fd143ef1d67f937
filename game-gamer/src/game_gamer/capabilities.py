"""Detached machine-readable declarations shipped with this exact package."""
from importlib.resources import files
import json


def get_capabilities():
    """Return this release's manifest without importing the optional terminal."""
    return json.loads(files('game_gamer').joinpath('capabilities.json').read_text(encoding='utf-8'))
