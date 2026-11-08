"""A deterministic, timed opening rendered by the regular input loop."""
import os
from time import monotonic

from .screen import Screen

FRAMES = (
    ('             *',),
    ('      .      *', ' .                .', '          .'),
    ('      .------*', '     /       |', ' .--.        .', '     \\      /', '       .---.'),
    ('R E C O N S T R U C T', '', 'THE NETWORK'),
)


def opening_screen(exercise, route, viewport,*,begin_choice=None):
    animated = callable(getattr(viewport, 'poll_key', None)) and os.getenv('COMMONS_REDUCED_MOTION', '').lower() not in {'1', 'true', 'yes'}
    duration = exercise.opening_seconds
    started = route.extra.setdefault('opening_started', monotonic())
    elapsed = monotonic()-started
    finished = route.extra.get('opening_finished', False) or not animated or elapsed >= duration
    if finished:
        route.extra['opening_finished'] = True
        return Screen(exercise.title, [exercise.subtitle, '', *exercise.introduction],
                      [('BEGIN RECONSTRUCTION', 'begin' if begin_choice is None else begin_choice)], 'Enter Begin · b Back',
                      navigation_text='Workshop / Collective reconstruction', scroll=route.scroll)
    frame = min(3, int(elapsed/duration*4))
    return Screen(exercise.title, [exercise.subtitle, '', *FRAMES[frame], '', 'Any key skips the opening.',
                                  '> [ BEGIN RECONSTRUCTION ]'],
                  footer='Any key Skip · Enter Begin after opening',
                  navigation=False, refresh_interval_ms=80)
