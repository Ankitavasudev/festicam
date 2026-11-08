"""Headless tests for the FestiCam v2 engine: no webcam, no mediapipe, no audio."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pytest

from festicam.app import (Session, face_dab, pinch_burst, run_over_frame,
                          stage_frame, update_rain)
from festicam.festivals import CHRISTMAS, EID, FESTIVALS, HOLI, NEW_YEAR
from festicam.tracker import HandState, HandTracker

SRC = Path(__file__).parent.parent / "src" / "festicam"


def make_session():
    return Session(width=960, height=540)


def hand_state(wrist_y=500):
    tips = [[120, 300], [240, 250], [280, 230], [300, 270], [340, 240]]
    return HandState(tips=tips, wrist=(240, wrist_y), pinch=[0.9, 0.5, 0.9, 0.9],
                     x=240, y=250)


class _L(SimpleNamespace):
    """Fake landmark: positional x/y in normalized image coords."""

    def __init__(self, x, y):
        super().__init__(x=x, y=y)


def face_state(left_eye_y=0.5, width=960, height=540, shift=0.0):
    """A level (or tilted) face: eye A on screen-left, eye B on screen-right."""
    lm = {
        33: _L(0.40 + shift, left_eye_y),        # screen-left eye outer
        263: _L(0.60 + shift, 0.5),              # screen-right eye outer
        1: _L(0.50 + shift, 0.58),               # nose tip
        50: _L(0.40 + shift, 0.62), 101: _L(0.44 + shift, 0.60), 205: _L(0.46 + shift, 0.66),
        280: _L(0.56 + shift, 0.60), 330: _L(0.60 + shift, 0.62), 425: _L(0.54 + shift, 0.66),
    }
    # convert to list-like access used by faces.state_from
    return lm


from festicam import faces as faces_mod


def to_lm(d):
    return [d.get(i, _L(0.5, 0.5)) for i in range(478)]


def run_face(session, lm, frames=1):
    face = faces_mod.state_from(lm, session.width, session.height)
    frame = np.zeros((session.height, session.width, 3), dtype=np.uint8)
    for _ in range(frames):
        session.tick += 1
        face_dab(session, face)
    return face


# --- festivals data ----------------------------------------------------------

def test_six_festivals_registered():
    assert len(FESTIVALS) == 6
    assert [f.key for f in FESTIVALS] == ["1", "2", "3", "4", "5", "6"]


def test_holi_is_first_and_paints():
    assert FESTIVALS[0] is HOLI
    assert HOLI.cheek_paint and HOLI.rain and HOLI.garland


def test_no_music_fields_anywhere():
    for f in FESTIVALS:
        for banned in ("music", "melody", "groove", "spray", "diyas", "crescent", "wrist_ring"):
            assert not hasattr(f, banned), f"stale field {banned!r} on {f.key}"


def test_switch_clears_persistent_fx():
    s = make_session()
    s.dab_cheek(100, 100, HOLI.palette[0])
    s.flakes.append([1, 2, 3, 4, (0, 0, 0)])
    s.switch(1)
    assert s.paints == [] and s.flakes == []


def test_next_wraps_around():
    s = make_session()
    s.switch(len(FESTIVALS) - 1)
    s.next()
    assert s.fest == 0


# --- stage: camera is the fullscreen stage ------------------------------------

def test_stage_frame_is_full_canvas():
    s = make_session()
    raw = np.zeros((480, 640, 3), dtype=np.uint8)
    out = stage_frame(raw, s)
    assert out.shape == (s.height, s.width, 3)


def test_stage_finish_upgrades_a_flat_frame():
    s = make_session()
    raw = np.zeros((480, 640, 3), dtype=np.uint8)
    raw[200:280, :] = 90                        # something to sharp/grade
    out = stage_frame(raw, s)
    assert int(out.max()) > 90                  # warm grade + unsharp lifted it


def test_stage_crops_to_169():
    s = make_session()
    tall = np.zeros((900, 400, 3), dtype=np.uint8)   # too tall -> center crop
    out = stage_frame(tall, s)
    assert out.shape[0] == s.height and out.shape[1] == s.width


# --- face tilt -> cheek paint --------------------------------------------------

def test_face_level_no_dab():
    s = make_session()
    run_face(s, to_lm(face_state()), frames=2)
    assert s.paints == []


def test_face_tilt_left_paints_screen_left_cheek():
    s = make_session()
    run_face(s, to_lm(face_state(left_eye_y=0.55)), frames=2)
    assert len(s.paints) == 1
    x, y, _a, _c = s.paints[0]
    assert x < s.width / 2, "tilt left must land on the screen-left cheek"


def test_face_tilt_right_paints_screen_right_cheek():
    s = make_session()
    run_face(s, to_lm(face_state(left_eye_y=0.45)), frames=2)
    assert len(s.paints) == 1
    x, _y, _a, _c = s.paints[0]
    assert x > s.width / 2


def test_face_must_return_level_before_next_dab():
    s = make_session()
    lm = to_lm(face_state(left_eye_y=0.55))
    run_face(s, lm, frames=2)
    assert len(s.paints) == 1
    run_face(s, lm, frames=3)                   # still tilted: armed only when level
    assert len(s.paints) == 1


def test_dab_cap():
    s = make_session()
    for i in range(60):
        s.dab_cheek(i, i, HOLI.palette[0])
    assert len(s.paints) <= 26


def test_no_cheek_paint_off_holi_like_flags():
    s = make_session()
    s.switch(2)                                  # rakhi: no cheek_paint
    run_face(s, to_lm(face_state(left_eye_y=0.55)), frames=2)
    assert s.paints == []


# --- hand raised -> paani -------------------------------------------------------

def test_raised_hand_spawns_rain():
    s = make_session()
    frame = np.zeros((s.height, s.width, 3), dtype=np.uint8)
    before = len(s.drops)
    run_over_frame(frame.copy(), s, hand_state(wrist_y=int(0.3 * s.height)))
    assert len(s.drops) > before


def test_lower_hand_no_rain():
    s = make_session()
    frame = np.zeros((s.height, s.width, 3), dtype=np.uint8)
    run_over_frame(frame.copy(), s, hand_state(wrist_y=int(0.8 * s.height)))
    assert not s.drops


def test_rain_drops_subjected_to_gravity():
    s = make_session()
    s.rain_at(400)
    assert s.drops and s.drops[0][3] > 0         # starts falling


# --- pinch -> burst --------------------------------------------------------------

def test_pinch_burst_in_any_festival():
    s = make_session()
    frame = np.zeros((s.height, s.width, 3), dtype=np.uint8)
    hs = HandState(tips=hand_state().tips, wrist=(240, 400), pinch=[0.9, 0.2, 0.9, 0.9],
                   x=480, y=240)
    run_over_frame(frame.copy(), s, hs)
    assert any(not d[7] for d in s.drops)        # burst beads exist among rain drops


def test_burst_cooldown():
    s = make_session()
    hs = HandState(tips=hand_state().tips, wrist=(240, 400), pinch=[0.9, 0.2, 0.9, 0.9],
                   x=480, y=240)
    pinch_burst(s, hs)
    n = len(s.drops)
    for _ in range(3):
        s.tick += 1
        pinch_burst(s, hs)
    assert len(s.drops) == n


# --- ambience ---------------------------------------------------------------------

def test_snow_in_christmas():
    s = make_session()
    s.switch(4)
    frame = np.zeros((s.height, s.width, 3), dtype=np.uint8)
    run_over_frame(frame.copy(), s, None)
    assert len(s.flakes) >= 90


def test_confetti_in_new_year_only_when_active():
    s = make_session()
    s.switch(5)
    frame = np.zeros((s.height, s.width, 3), dtype=np.uint8)
    run_over_frame(frame.copy(), s, None)
    assert len(s.flakes) >= 120
    s.switch(0)
    run_over_frame(frame.copy(), s, None)
    assert s.flakes == []


def test_stars_in_eid():
    s = make_session()
    s.switch(3)
    frame = np.zeros((s.height, s.width, 3), dtype=np.uint8)
    run_over_frame(frame.copy(), s, None)
    assert len(s.twinkles) >= 70
    assert EID.moon


def test_frame_shape_preserved_and_camera_used():
    s = make_session()
    frame = np.ones((390, 640, 3), dtype=np.uint8) * 80   # fake "camera" image
    out = run_over_frame(frame.copy(), s, None)
    assert out.shape == frame.shape
    assert out.max() >= frame.max()                        # scene built on camera pixels


# --- sound is gone -----------------------------------------------------------------

def test_synth_module_deleted():
    assert not (SRC / "synth.py").exists(), "sound was removed from FestiCam"


def test_no_audio_imports():
    src = "".join(p.read_text(encoding="utf-8") for p in SRC.glob("*.py"))
    for banned in ("sounddevice", "winsound", "synth", "play_note", "JINGLE_BELLS"):
        assert banned not in src, f"audio leaked back in via {banned!r}"


# --- art layers --------------------------------------------------------------------

def test_garland_layer_has_shape_and_color():
    from festicam.art import make_garland

    g = make_garland(320, list(HOLI.palette))
    assert g.shape == (int(320 * 0.20) + 100, 320, 4)
    assert (g[:, :, 3] > 0).sum() > 200


def test_rangoli_layer():
    from festicam.art import make_rangoli

    r = make_rangoli(64, list(NEW_YEAR.palette))
    assert r.shape[0] == r.shape[1] and (r[:, :, 3] > 0).any()


def test_moon_layer():
    import festicam.festivals as F
    from festicam.art import make_moon

    m = make_moon(40, F.GOLD)
    assert (m[:, :, 3] > 0).any()


def test_splash_sprite():
    from festicam.art import make_splash

    s = make_splash(30, HOLI.palette[0])
    assert s.ndim == 3 and s.shape[2] == 4 and (s[:, :, 3] > 0).any()


def test_overlay_composites_and_clips():
    from festicam.art import blank, overlay

    scene = np.zeros((40, 40, 3), dtype=np.uint8)
    art = np.zeros((20, 20, 4), dtype=np.uint8)
    art[:, :, :3] = (0, 0, 255)
    art[:, :, 3] = 255
    overlay(scene, art, 30, 30)                 # mostly off-canvas: must clip safely
    assert scene[35, 35, 2] == 255
    overlay(scene, art, -10, -10)               # negative clip safe
    assert scene[5, 5, 2] == 255


def test_stamp_resizes():
    from festicam.art import blank, stamp

    scene = np.zeros((60, 60, 3), dtype=np.uint8)
    art = np.zeros((10, 10, 4), dtype=np.uint8)
    art[:, :, 2] = 255
    art[:, :, 3] = 255
    stamp(scene, art, 30, 30, scale=2.0)
    assert scene[30, 30, 2] == 255


# --- tracker -----------------------------------------------------------------------

def test_hand_state_has_wrist():
    hs = hand_state()
    assert hs.wrist == (240, 500)


def test_tracker_lazy_load():
    t = HandTracker()
    assert t._mode is None
