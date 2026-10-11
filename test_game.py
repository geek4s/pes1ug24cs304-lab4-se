"""Headless checks for the Memory Color Pattern game.

Run from the project root:   python test_game.py

No window opens and no sound plays: SDL's dummy drivers are used and the game
clock is replaced with a fake one, so the whole run takes about a second.
"""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.mixer.pre_init(44100, -16, 1, 512)
pygame.init()
SCREEN = pygame.display.set_mode((500, 520))

CLOCK = {"now": 0}
pygame.time.get_ticks = lambda: CLOCK["now"]

from game.game_engine import GameEngine

STEP_MS = 10


def new_game():
    return GameEngine(500, 520)


def advance(engine, ms):
    for _ in range(ms // STEP_MS):
        CLOCK["now"] += STEP_MS
        engine.update()


def finish_watching(engine):
    while engine.state == "WATCH":
        advance(engine, STEP_MS)


def click(engine, color_id):
    pos = engine.buttons[color_id].rect.center
    engine.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


def play_round(engine, gap_ms=200):
    """Watch the pattern, then repeat it correctly."""
    finish_watching(engine)
    for color_id in list(engine.sequence):
        advance(engine, gap_ms)
        click(engine, color_id)


def press_r(engine):
    engine.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))


# ---------------------------------------------------------------- Task 1

def test_sequence_grows_by_exactly_one_step():
    engine = new_game()
    lengths = []
    previous = []
    for _ in range(10):
        lengths.append(len(engine.sequence))
        assert engine.sequence[:len(previous)] == previous, "earlier steps must be kept unchanged"
        previous = list(engine.sequence)
        play_round(engine)
        assert engine.state != "GAME_OVER"
    assert lengths == list(range(1, 11)), f"lengths per round were {lengths}"


# ---------------------------------------------------------------- Task 2

def test_playback_accelerates_each_round():
    engine = new_game()
    flashes, pauses = [], []
    for _ in range(20):
        flashes.append(engine.flash_duration)
        pauses.append(engine.pause_duration)
        play_round(engine)

    assert flashes[0] == engine.base_flash_duration and pauses[0] == engine.base_pause_duration
    assert all(b <= a for a, b in zip(flashes, flashes[1:])), flashes
    assert all(b <= a for a, b in zip(pauses, pauses[1:])), pauses
    assert flashes[5] < flashes[0] and pauses[5] < pauses[0]
    assert flashes[-1] == engine.min_flash_duration, "speed must stop at the floor"
    assert pauses[-1] == engine.min_pause_duration


def test_measured_flash_time_shrinks():
    """Measure how long the first pad is actually lit in round 1 and round 8."""
    def lit_time(engine):
        pad = engine.buttons[engine.sequence[0]]
        while not pad.is_lit:
            advance(engine, STEP_MS)
        start = CLOCK["now"]
        while pad.is_lit:
            advance(engine, STEP_MS)
        return CLOCK["now"] - start

    engine = new_game()
    early = lit_time(engine)
    for _ in range(7):
        play_round(engine)
    late = lit_time(engine)
    assert early >= 440, early
    assert late < early * 0.6, (early, late)


# ---------------------------------------------------------------- Task 3

def test_each_pad_has_its_own_tone():
    from game.sound_manager import PAD_FREQUENCIES
    engine = new_game()
    assert engine.sounds.enabled, "mixer should initialise (dummy driver in tests)"
    assert len(engine.sounds.tones) == 4
    assert len(set(PAD_FREQUENCIES)) == 4, "four distinct pitches"


def test_tone_plays_on_flash_and_on_click():
    engine = new_game()
    played = []
    engine.sounds.play = played.append

    finish_watching(engine)
    assert played == engine.sequence, "one tone per flashed step, matching its colour"

    played.clear()
    click(engine, engine.sequence[0])
    assert played == [engine.sequence[0]], "clicking a pad sounds that pad's tone"


def test_error_sound_on_wrong_click():
    engine = new_game()
    errors = []
    engine.sounds.play_error = lambda: errors.append(True)
    finish_watching(engine)
    click(engine, (engine.sequence[0] + 1) % 4)
    assert errors == [True]


# ---------------------------------------------------------------- Task 4

def test_timer_only_runs_on_player_turn():
    engine = new_game()
    assert engine.state == "WATCH"
    advance(engine, 300)
    assert engine.turn_time_left == engine.turn_time_limit
    finish_watching(engine)
    advance(engine, 500)
    assert engine.turn_time_limit - 520 <= engine.turn_time_left <= engine.turn_time_limit - 480


def test_running_out_of_time_ends_the_game():
    engine = new_game()
    finish_watching(engine)
    advance(engine, engine.turn_time_limit - 50)
    assert engine.state == "PLAYER_TURN", "must not end early"
    advance(engine, 100)
    assert engine.state == "GAME_OVER"
    assert engine.game_over_reason == "TIME'S UP!"
    assert engine.turn_time_left == 0


def test_timer_budget_grows_with_pattern_and_resets_each_round():
    engine = new_game()
    limits = []
    for _ in range(6):
        limits.append(engine.turn_time_limit)
        assert engine.turn_time_left == engine.turn_time_limit
        play_round(engine)
    assert all(b > a for a, b in zip(limits, limits[1:])), limits


# ---------------------------------------------- README "Expected Behavior"

def test_wrong_click_is_game_over_and_r_restarts():
    engine = new_game()
    for _ in range(3):
        play_round(engine)
    assert engine.score == 3
    finish_watching(engine)
    click(engine, (engine.sequence[0] + 1) % 4)
    assert engine.state == "GAME_OVER" and engine.game_over_reason == "WRONG PATTERN!"

    click(engine, 0)
    assert engine.state == "GAME_OVER", "clicks do nothing on the Game Over screen"

    press_r(engine)
    assert engine.state == "WATCH"
    assert engine.score == 0 and len(engine.sequence) == 1 and engine.player_input == []
    assert engine.flash_duration == engine.base_flash_duration, "speed resets too"


def test_clicks_are_ignored_while_watching():
    engine = new_game()
    click(engine, 0)
    assert engine.player_input == [] and engine.state == "WATCH"


# ------------------------------------------------- click-flash side issues

def test_every_step_of_next_round_gets_a_full_flash():
    """The click that ends a round must not shorten the next round's playback."""
    engine = new_game()
    play_round(engine)                       # last click is the pad round 2 starts with

    full_flashes = 0
    lit_since = {}
    while engine.state == "WATCH":
        advance(engine, STEP_MS)
        for pad in engine.buttons:
            if pad.is_lit and pad.color_id not in lit_since:
                lit_since[pad.color_id] = CLOCK["now"]
            elif not pad.is_lit and pad.color_id in lit_since:
                if CLOCK["now"] - lit_since.pop(pad.color_id) >= engine.flash_duration:
                    full_flashes += 1
    assert full_flashes == len(engine.sequence), (full_flashes, len(engine.sequence))


def test_quick_clicks_do_not_leave_a_pad_stuck_lit():
    engine = new_game()
    finish_watching(engine)
    engine.sequence[:] = [0, 1, 2]
    click(engine, 0)
    advance(engine, 80)
    click(engine, 1)
    advance(engine, 400)
    assert [b.color_id for b in engine.buttons if b.is_lit] == []


def test_render_in_every_state():
    engine = new_game()
    engine.render(SCREEN)                    # WATCH
    finish_watching(engine)
    engine.render(SCREEN)                    # PLAYER_TURN
    advance(engine, engine.turn_time_limit + 100)
    engine.render(SCREEN)                    # GAME_OVER
    assert engine.state == "GAME_OVER"


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in list(globals().items()) if name.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
