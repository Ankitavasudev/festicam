"""Headless tests for the FestiCam engine: no webcam, no mediapipe, no audio."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest

from festicam.app import Session, pinch_test, run_over_frame, pad_hint
from festicam.festivals import CHRISTMAS, DIWALI, HOLI, FESTIVALS
from festicam.synth import JINGLE_BELLS, SPARKLE_BELLS, BELL, Player, bell, repitch, sample
from festicam.tracker import HandState, HandTracker


def make_session():
    return Session(width=960, height=540)


def hand_state():
    tips = [[120, 300], [240, 250], [280, 230], [300, 270], [340, 240]]
    return HandState(tips=tips, pinch=[0.9, 0.5, 0.9, 0.9], x=240, y=250)


# --- festivals data ----------------------------------------------------------

def test_six_festivals_registered():
    assert len(FESTIVALS) == 6
    assert [f.key for f in FESTIVALS] == ["1", "2", "3", "4", "5", "6"]


def test_holi_first():
    assert FESTIVALS[0].title == "HAPPY HOLI!"
    assert FESTIVALS[0].spray and FESTIVALS[0].stains


def test_switch_clears_splashes_and_moves_banner():
    s = make_session()
    s.switch(1)
    assert s.festival.title == "HAPPY DIWALI!"
    s.burst(100, 100, s.festival.palette[0])
    assert s.splash
    s.switch(0)
    assert not s.splash  # reset feels like a fresh festival


def test_next_wraps_around():
    s = make_session()
    s.switch(len(FESTIVALS) - 1)
    s.next()
    assert s.fest == 0


# --- engine pipeline --------------------------------------------------------

def test_frame_shape_preserved():
    s = make_session()
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    out = run_over_frame(frame, s, None)
    assert out.shape == frame.shape


def test_stage_is_navy_not_black():
    s = make_session()
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    out = run_over_frame(frame, s, None)
    assert out.mean() > 10  # gradient stage, not raw black


def test_holi_spray_spawns_drops():
    s = make_session()
    s.switch(0)
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    hs = hand_state()
    before = len(s.splash)
    run_over_frame(frame.copy(), s, hs)
    run_over_frame(frame.copy(), s, hs)
    assert len(s.splash) > before


def test_fireworks_on_pinch_in_diwali():
    s = make_session()
    s.switch(1)
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    hs = HandState(tips=hand_state().tips, pinch=[0.9, 0.2, 0.9, 0.9], x=480, y=240)
    run_over_frame(frame.copy(), s, hs)
    assert len(s.splash) >= 40
    assert s.player.backend in ("sounddevice", "winsound", "silent")


def test_no_flakes_outside_snow_festivals():
    s = make_session()
    s.switch(3)  # eid: stars, not snow or confetti
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    for _ in range(5):
        run_over_frame(frame.copy(), s, None)
    assert s.flakes == []        # only christmas/holi rain particles


def test_snow_in_christmas():
    s = make_session()
    s.switch(4)
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    run_over_frame(frame.copy(), s, None)
    assert len(s.flakes) >= 90


def test_holi_pinch_paints_stain():
    s = make_session()
    s.switch(0)
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    hs = HandState(tips=hand_state().tips, pinch=[0.9, 0.2, 0.9, 0.9], x=480, y=260)
    run_over_frame(frame.copy(), s, hs)
    assert s.stains


def test_music_scheduled_over_frames():
    s = make_session()
    s.switch(4)  # christmas melody
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    for _ in range(70):
        run_over_frame(frame.copy(), s, None)
    assert s.notes["mel"] >= 1   # jingle bells clocks along


# --- synth ------------------------------------------------------------------

def test_bell_instruments():
    s = sample(BELL)
    assert s.dtype == np.float32 and len(s) > 0 and np.isfinite(s).all()


def test_jingle_bells_melody_shape():
    assert len(JINGLE_BELLS) == 11
    assert all(f > 100 for f, _b in JINGLE_BELLS if f)


def test_sparkle_bells_shape():
    assert len(SPARKLE_BELLS) == 6


def test_repitch_changes_wave():
    s = sample(BELL)
    up = repitch(s, 1.5)
    assert up.shape == s.shape
    assert not np.array_equal(up[:100], s[:100])


def test_bell_durations_affect_length():
    assert len(bell(880, 0.3)) < len(bell(880, 1.5))


def test_player_silent_no_device():
    p = Player()
    p.play(BELL)
    p.play_note(440.0)


def test_pad_hint_inside_frame():
    s = make_session()
    for drum in (0, 1, 2, 3):
        x, y = pad_hint(s, drum)
        assert 0 <= x < s.width and 0 <= y < s.height


# --- tracker ----------------------------------------------------------------

def test_tracker_lazy_load():
    t = HandTracker()
    assert t._mode is None


def test_hand_state_fields():
    hs = hand_state()
    assert len(hs.tips) == 5 and len(hs.pinch) == 4
