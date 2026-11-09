"""A deterministic, timed opening rendered by the regular input loop."""

from time import monotonic

from .i18n import t
from .screen import Screen
from .visual import motion_enabled

FRAMES = (
    ('             *',),
    ('      .      *', ' .                .', '          .'),
    ('      .------*', '     /       |', ' .--.        .', '     \\      /', '       .---.'),
)


def opening_screen(exercise, route, viewport,*,begin_choice=None):
    animated = motion_enabled(viewport)
    duration = exercise.opening_seconds
    started = route.extra.setdefault('opening_started', monotonic())
    elapsed = monotonic()-started
    finished = route.extra.get('opening_finished', False) or not animated or elapsed >= duration
    if finished:
        route.extra['opening_finished'] = True
        return Screen(exercise.title, [exercise.subtitle, '', *exercise.introduction],
                      [(t('workshop.opening.begin_reconstruction'), 'begin' if begin_choice is None else begin_choice)], t('workshop.opening.enter_begin_b_back'),
                      navigation_text=t('workshop.opening.workshop_collective_reconstruction'), scroll=route.scroll)
    frame = min(3, int(elapsed/duration*4))
    art = FRAMES[frame] if frame < len(FRAMES) else (t('workshop.opening.animated_title'), '', t('workshop.opening.network_title'))
    return Screen(exercise.title, [exercise.subtitle, '', *art, '', t('workshop.opening.any_key_skips_the_opening'),
                                  '> [ '+t('workshop.opening.begin_reconstruction')+' ]'],
                  footer=t('workshop.opening.any_key_skip_enter_begin'),
                  navigation=False, refresh_interval_ms=80)
