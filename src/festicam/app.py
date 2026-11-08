"""FestiCam engine: one stage, six festivals, webcam hands drive the magic.

Pipeline = run_over_frame(frame, session, hand) exactly like its siblings
(airjam/airmath), so the whole thing is headless-testable.

Interactions per festival are data-driven (see festivals.py):
  * spray      - index finger pointing paints palette particles from the tip
  * fireworks  - pinch launches a firework where the fingers meet
  * wrist_ring - a decorative ring + sparkles keep to your wrist
  * snow / stars / confetti / diyas / crescent / stains  - ambience layers
Music: drum grooves or bell melodies scheduled on the frame clock.
"""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np

from .festivals import FESTIVALS, Festival, GOLD, PINK, WHITEISH
from .synth import Player
from .tracker import HandState, HandTracker

ON, OFF = 0.45, 0.58   # pinch hysteresis (same proven pair as AirJam)
SPRAY_RATE = 7          # drops spawned per frame while pointing


class Session:
    """State threaded between frames."""

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.fest = 0                     # index into FESTIVALS
        self.fest_start = 0               # tick when switched (banner animation)
        self.player = Player()
        self.tick = 0
        self.splash: list[list] = []      # [x, y, vx, vy, age, life, color]
        self.stains: list[list] = []      # painted gulaal [x, y, r, color, alpha]
        self.flakes: list[list] = []      # snow / confetti [x, y, vy, sway, color]
        self.twinkles: list[tuple[int, int]] = []
        self.trail: list[tuple[int, int]] = []
        self.notes: dict[str, int] = {}   # music scheduler state
        self.pinch_closed = False
        self.diya_flicker = 0
        self.stage = self._make_stage()

    def _make_stage(self) -> np.ndarray:
        """Deep festival night gradient - drawn once, copied each frame."""
        yy = np.linspace(0, 1, self.height)[:, None]
        base = np.zeros((self.height, self.width, 3), dtype=np.float32)
        base[..., 0] = 60 * (1 - yy) + 34
        base[..., 1] = 20 * (1 - yy) + 12
        base[..., 2] = 34 * (1 - yy) + 18
        return base.astype(np.uint8)

    @property
    def festival(self) -> Festival:
        return FESTIVALS[self.fest]

    def switch(self, idx: int) -> None:
        self.fest = idx % len(FESTIVALS)
        self.fest_start = self.tick
        self.stains.clear()
        self.splash.clear()
        self.flakes.clear()
        self.twinkles.clear()
        self.notes = {}

    def next(self) -> None:
        self.switch(self.fest + 1)

    def burst(self, x: int, y: int, color: int, n: int = 26, speed: float = 7.0) -> None:
        rng = np.random.default_rng(self.tick * 8 + n)
        for _ in range(n):
            angle = rng.uniform(0, 2 * math.pi)
            v = rng.uniform(speed * 0.35, speed)
            self.splash.append([
                x, y, int(math.cos(angle) * v), int(math.sin(angle) * v) - 2,
                0, int(rng.uniform(30, 52)), color,
            ])

    def spray_at(self, x: int, y: int, dx: float, dy: float, color: int) -> None:
        """Pichkari! drops leave the fingertip along the finger's motion."""
        rng = np.random.default_rng(self.tick)
        for _ in range(SPRAY_RATE):
            self.splash.append([
                x, y,
                int(dx * 0.8 + rng.uniform(-2, 2)),
                int(dy * 0.8 + rng.uniform(-2, 2)),
                0, int(rng.uniform(16, 34)), color,
            ])

    def spawn_ambience(self) -> None:
        f = self.festival
        if f.snow or f.confetti:
            while len(self.flakes) < (90 if f.snow else 120):
                rng = np.random.default_rng(self.tick * len(self.flakes) + len(self.flakes))
                color = WHITEISH if f.snow else f.palette[len(self.flakes) % len(f.palette)]
                self.flakes.append([
                    rng.integers(0, self.width), int(-rng.uniform(0, self.height)),
                    int(rng.integers(2, 5)), int(rng.integers(14, 40)), color,
                ])
        elif self.flakes:
            self.flakes.clear()
        if f.stars:
            while len(self.twinkles) < 70:
                rng = np.random.default_rng(self.tick * len(self.twinkles) + 7)
                self.twinkles.append((int(rng.integers(0, self.width)),
                                      int(rng.integers(0, int(self.height * 0.72)))))
        elif self.twinkles:
            self.twinkles.clear()


def pinch_test(session: Session, pinch: list[float]) -> bool:
    """Hysteresis pinch; True on a fresh pinch-close (for fireworks etc.)."""
    fired = False
    d = pinch[1]                      # thumb-index pinch is the "action" gesture
    if not session.pinch_closed and d < ON:
        session.pinch_closed = True
        fired = True
    elif session.pinch_closed and d > OFF:
        session.pinch_closed = False
    return fired


def schedule_music(session: Session) -> None:
    """Frame-clock music scheduler; grooves or melodies per festival."""
    f = session.festival
    if f.melody:
        notes = f.melody
        key = "mel"
        idx = session.notes.get(key, 0)
        started = session.notes.get("mel_start", None)
        if started is None:
            session.notes["mel_start"] = session.tick
            started = session.tick
        # rest gaps accumulate beats until we reach the current note
        beats_per_frame = 60 / 14000.0            # ~ 92 BPM at 30 fps
        # simpler: one note every 16 frames
        if session.tick - started >= 30:
            note, _beats = notes[idx % len(notes)]
            session.notes[key] = idx + 1
            session.notes["mel_start"] = session.tick
            if note:
                session.player.play_note(note)
    elif f.groove:
        idx = session.notes.get("groove", 0)
        started = session.notes.get("groove_start", session.tick)
        if session.tick - started >= 15:
            drum = f.groove[idx % len(f.groove)]
            session.notes["groove"] = idx + 1
            session.notes["groove_start"] = session.tick
            session.player.play(drum)
            session.burst(*pad_hint(session, drum), color=next_palette(session), n=8, speed=3.5)


def next_palette(session: Session) -> int:
    return session.festival.palette[session.tick % len(session.festival.palette)]


def pad_hint(session: Session, drum: int) -> tuple[int, int]:
    w, h = session.width, session.height
    return {2: (int(w * 0.25), int(h * 0.80)),
            0: (int(w * 0.18), int(h * 0.82)),
            1: (int(w * 0.35), int(h * 0.84)),
            3: (int(w * 0.75), int(h * 0.80))}[drum]


def _step_fx(session: Session) -> None:
    alive = []
    up = 0.55 if session.festival.snow else 0.0
    for s in session.splash:
        s[0] += s[2]
        s[1] += s[3]
        s[3] += 1                                   # gravity
        s[4] += 1
        if s[4] < s[5] and -40 < s[0] < session.width + 40 and s[1] < session.height + 10:
            alive.append(s)
    session.splash = alive
    for fl in session.flakes:
        fl[0] += int(2 * math.sin((session.tick + fl[3]) / fl[2]))
        fl[1] += fl[2] + 1
        if fl[1] > session.height:
            fl[1] = -6
    f = session.festival
    for s in list(session.stains):
        s[4] *= 0.999


def run_over_frame(frame_bgr: np.ndarray, session: Session, hand: HandState | None) -> np.ndarray:
    """Advance one frame; returns the annotated display frame."""
    import cv2

    session.tick += 1
    session.spawn_ambience()
    schedule_music(session)

    prev = session.trail[-1] if session.trail else None
    if hand is not None:
        session.trail.append((int(hand.x), int(hand.y)))
        if len(session.trail) > 26:
            del session.trail[:6]
        if session.festival.spray and session.tick % 2 == 0:
            x, y = hand.x, hand.y
            dx, dy = 0, -1
            if prev:
                dx, dy = x - prev[0], y - prev[1]
            session.spray_at(x, y, dx, dy, next_palette(session))
        if hand.pinch[1] < ON:
            f = session.festival
            if f.fireworks and pinch_test(session, hand.pinch):
                x, y = hand.x, max(60, hand.y - 120)
                color = next_palette(session)
                session.burst(x, y, color, n=40, speed=8.5)
                session.burst(x, y, next_palette(session), n=24, speed=5.5)
                session.player.play(2, pitch=0.9)
            elif f.stains:
                session.burst(hand.x, hand.y, next_palette(session), n=30, speed=6.0)
                session.stains.append([hand.x, hand.y, 46, next_palette(session), 0.30])
    _step_fx(session)

    scene = session.stage.copy()
    _paint_stains(scene, session)
    _draw_ambience(scene, session)
    if session.festival.crescent:
        _draw_crescent(scene, session)
    if session.festival.diyas:
        _draw_diyas(scene, session)
    _draw_splash(scene, session)
    if hand is not None:
        if session.festival.wrist_ring:
            _draw_wrist_ring(scene, session, hand)
        _draw_cursor(scene, session, hand)
    _draw_banner(scene, session)
    _draw_camera_card(scene, session, frame_bgr)
    _hud(scene, session)
    return scene


def _paint_stains(scene: np.ndarray, session: Session) -> None:
    import cv2

    for x, y, r, color, alpha in session.stains[-90:]:
        overlay = tuple(int(c * alpha) for c in color)
        cv2.circle(scene, (int(x), int(y)), int(r), overlay, -1, cv2.LINE_AA)


def _draw_ambience(scene: np.ndarray, session: Session) -> None:
    import cv2

    for x, y, _vy, sway, color in session.flakes:
        cv2.circle(scene, (int(x + 2 * math.sin((session.tick + sway) / sway * 4)), int(y)),
                   3 if session.festival.snow else 4, color, -1, cv2.LINE_AA)
    for i, (x, y) in enumerate(session.twinkles):
        tw = 0.5 + 0.5 * math.sin((session.tick + i * 13) / 17.0)
        c = tuple(int(v * (0.25 + tw)) for v in GOLD)
        cv2.circle(scene, (x, y), 2 + int(2 * tw), c, -1, cv2.LINE_AA)


def _draw_crescent(scene: np.ndarray, session: Session) -> None:
    import cv2

    cx, cy, r = session.width - 150, 110, 52
    cv2.circle(scene, (cx, cy), r, GOLD, -1, cv2.LINE_AA)
    cv2.circle(scene, (cx + int(r * 0.55), cy - int(r * 0.18)), int(r * 0.88), (18, 12, 28), -1)
    for dx, dy in ((-r, int(r * 0.6)), (-int(r * 1.3), int(r * 0.9))):
        tw = 0.5 + 0.5 * math.sin((session.tick + dx) / 13.0)
        cv2.circle(scene, (cx + dx, cy + dy), 3 + int(2 * tw), tuple(int(v * tw) for v in GOLD), -1)


def _draw_diyas(scene: np.ndarray, session: Session) -> None:
    import cv2

    n = 7
    for i in range(n):
        x = int(session.width * (i + 1) / (n + 1))
        y = session.height - 34
        flick = 0.5 + 0.5 * math.sin((session.tick + i * 9) / 6.0)
        cv2.ellipse(scene, (x, y), (22, 9), 0, 0, 180, (40, 120, 220), -1)   # diya bowl
        flame = 10 + int(5 * flick)
        cv2.ellipse(scene, (x, y - flame // 2), (6, flame), 0, 0, 360, (60, 150, 255), -1)  # flame
        halo = tuple(int(v * (0.25 + 0.3 * flick)) for v in GOLD)
        cv2.circle(scene, (x, y - flame), 26 + int(8 * flick), halo, 1, cv2.LINE_AA)


def _draw_splash(scene: np.ndarray, session: Session) -> None:
    import cv2

    for x, y, _vx, _vy, age, life, color in session.splash:
        fade = max(0.15, 1.0 - age / max(life, 1))
        c = tuple(int(v * fade) for v in color)
        cv2.circle(scene, (int(x), int(y)), 4 if fade > 0.5 else 3, c, -1)


def _draw_wrist_ring(scene: np.ndarray, session: Session, hand: HandState) -> None:
    import cv2

    # wrist is landmark 0 -> tips list has no wrist; approximate midpoint between fingertips
    xs = [t[0] for t in hand.tips]
    ys = [t[1] for t in hand.tips]
    cx, cy = int(sum(xs) / len(xs)), int(max(ys) + 34)
    r = 34
    for k, (rr, thick) in enumerate(((r + 8, 2), (r + 3, 4), (r, 3))):
        color = [GOLD, PINK, GOLD][k] if k in (0, 2) else next_palette(session)
        cv2.circle(scene, (cx, cy), rr + int(2 * math.sin((session.tick + k) / 5)), color, thick, cv2.LINE_AA)
    for i in range(8):
        a = i * math.pi / 4 + session.tick / 40
        px, py = cx + int((r + 5) * math.cos(a)), cy + int((r + 5) * math.sin(a))
        cv2.circle(scene, (px, py), 3, GOLD, -1, cv2.LINE_AA)


def _draw_cursor(scene: np.ndarray, session: Session, hand: HandState) -> None:
    import cv2

    pts = session.trail[-22:]
    for i in range(1, len(pts)):
        t = i / len(pts)
        cv2.line(scene, pts[i - 1], pts[i], (int(220 * t), int(210 * t), int(255 * t)),
                 max(1, int(5 * t)), cv2.LINE_AA)
    tip = hand.tips[1]
    glow = tuple(int(c * 0.5) for c in next_palette(session))
    cv2.circle(scene, tuple(tip), 11, glow, -1, cv2.LINE_AA)
    cv2.circle(scene, tuple(tip), 6, (255, 255, 255), -1, cv2.LINE_AA)


def _draw_banner(scene: np.ndarray, session: Session) -> None:
    import cv2

    f = session.festival
    age = session.tick - session.fest_start
    slide = max(0.0, 1.0 - age / 16.0)   # drop-in banner (~0.5 s)
    y = int(58 - 150 * slide)
    scale = 1.5 if len(f.title) <= 18 else 1.15
    (tw, _), _ = cv2.getTextSize(f.title, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)
    x = (session.width - tw) // 2
    shimmy = int(3 * math.sin(session.tick / 28))
    # soft shadow + gradient double-strike keeps big type readable over fx
    cv2.putText(scene, f.title, (x + 3, y + 3), cv2.FONT_HERSHEY_SIMPLEX, scale, (20, 20, 30), 3, cv2.LINE_AA)
    c1 = f.palette[session.tick % len(f.palette)]
    c2 = f.palette[(session.tick // 40) % len(f.palette)]
    cv2.putText(scene, f.title, (x, y + shimmy), cv2.FONT_HERSHEY_SIMPLEX, scale, c1, 3, cv2.LINE_AA)
    cv2.putText(scene, f.title, (x, y + shimmy), cv2.FONT_HERSHEY_SIMPLEX, scale, c2, 1, cv2.LINE_AA)
    (tw2, _), _ = cv2.getTextSize(f.subtitle, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.putText(scene, f.subtitle, ((session.width - tw2) // 2, y + 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (225, 225, 225), 1, cv2.LINE_AA)


def _draw_camera_card(scene: np.ndarray, session: Session, frame_bgr: np.ndarray) -> None:
    import cv2

    card_w = max(190, session.width // 6)
    h, w = frame_bgr.shape[:2]
    card_h = int(card_w * h / w)
    x0 = session.width - card_w - 24
    y0 = session.height - card_h - 24
    card = cv2.resize(frame_bgr, (card_w, card_h), interpolation=cv2.INTER_AREA)
    card = cv2.addWeighted(card, 1.22, cv2.GaussianBlur(card, (0, 0), 3), -0.22, 6)
    cv2.rectangle(scene, (x0 + 4, y0 + 5), (x0 + card_w + 4, y0 + card_h + 5), (8, 8, 8), -1)
    scene[y0:y0 + card_h, x0:x0 + card_w] = card
    cv2.rectangle(scene, (x0 - 2, y0 - 2), (x0 + card_w + 2, y0 + card_h + 2), (235, 235, 235), 2, cv2.LINE_AA)


def _hud(scene: np.ndarray, session: Session) -> None:
    import cv2

    f = session.festival
    cv2.putText(scene, f"FestiCam - {f.title.lower()}   |   keys 1-6 festival   SPACE music   c burst   q quit",
                (20, scene.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (225, 225, 225), 1, cv2.LINE_AA)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="festicam", description="Open the camera and the festival arrives.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args(argv)

    try:
        import mediapipe  # noqa: F401
    except ImportError:
        print("FestiCam needs mediapipe: pip install mediapipe")
        return 2
    try:
        import cv2
    except ImportError:
        print("FestiCam needs opencv-python: pip install opencv-python")
        return 2

    session = Session(width=args.width, height=args.height)
    print("audio backend:", session.player.backend)
    tracker = HandTracker()
    if sys.platform == "win32":
        cam = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        if not cam.isOpened():
            cam = cv2.VideoCapture(args.camera)
    else:
        cam = cv2.VideoCapture(args.camera)
    if not cam.isOpened():
        print("could not open camera %d" % args.camera)
        return 2
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    win = "FestiCam - festival in your camera"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.waitKey(1)
    print("FestiCam  -  Holi first. press 1-6 to visit festivals, ESC to quit.")
    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)
            hand = tracker.process(frame)
            out = run_over_frame(frame, session, hand)
            cv2.imshow(win, out)
            keyl = cv2.waitKeyEx(1)
            key = keyl & 0xFF
            if key == ord("q") or key == 27:
                break
            if key in b"123456":
                session.switch(key - ord("1"))
            elif key == ord("c"):
                session.stains.clear()
            elif key == ord("n"):
                session.next()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    finally:
        tracker.close()
        cam.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
