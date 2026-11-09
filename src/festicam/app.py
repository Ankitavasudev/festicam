"""FestiCam engine: your camera IS the festival stage.

Pipeline = run_over_frame(staged_camera, session, hand, face), fully
headless-testable like its siblings (airjam/airmath).

Feel of the app (per the product vision): the camera fills the screen
first, sticker-grade festive art frames it, and everything is one
effortless gesture away -
  * tilt your head -> gulaal lands on that very cheek
  * raise a hand   -> paani falls
  * pinch          -> a color burst
No sound. No menus. Keys 1-6 switch the festival.
"""

from __future__ import annotations

import argparse
import math
import sys

import numpy as np

from .art import make_garland, make_lights, make_moon, make_rangoli, make_splash, make_wash, stamp, overlay
from .faces import FaceState, FaceTracker
from .festivals import FESTIVALS, Festival, GOLD, WATER, WHITEISH
from .tracker import HandState, HandTracker

ON, OFF = 0.45, 0.58    # pinch hysteresis (proven pair from AirJam)
COOLDOWN = 6            # frames between bursts
RAIN_Y = 0.45           # wrist above this fraction of height = hand raised
TILT_ON, TILT_OFF = 0.30, 0.16   # cheek-paint hysteresis (normalized eye-line slope)
CHEEK_STAMPS_MAX = 26
GLIDE_MIN = 9.0         # fingertip speed (px/frame) that starts a ribbon
RIBBON_MAX = 220        # ribbon segments kept on screen
WASH_ALPHA = 0.5


class Session:
    """State threaded between frames."""

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.fest = 0
        self.fest_start = 0
        self.tick = 0
        self.paints: list[list] = []      # cheek dabs [x, y, alpha, color]
        self.drops: list[list] = []       # paani droplets [x, y, vy, age, life]
        self.flakes: list[list] = []      # snow / confetti [x, y, vy, sway, color]
        self.ribbons: list[list] = []     # glide ribbons [x0, y0, x1, y1, color, age, life, width]
        self.embers: list[list] = []      # rising sparks [x, y, vy, sway, age, life, color]
        self._sm = None                   # smoothed fingertip for ribbon control
        self.twinkles: list[tuple[int, int]] = []
        self.trail: list[tuple[int, int]] = []          # fingertip sparkle trail
        self.pinch_closed = False
        self.last_burst = -99
        self.tilt_armed = True            # face must come back level before next dab
        self._sprites: dict[int, np.ndarray] = {}
        self._art_cache: dict[int, dict] = {}

    # ----- festival helpers ----------------------------------------------

    @property
    def festival(self) -> Festival:
        return FESTIVALS[self.fest]

    def switch(self, idx: int) -> None:
        self.fest = idx % len(FESTIVALS)
        self.fest_start = self.tick
        self.paints.clear()
        self.drops.clear()
        self.flakes.clear()
        self.twinkles.clear()
        self.ribbons.clear()
        self.embers.clear()
        self._sm = None
        self.tilt_armed = True
        # welcome burst: the new festival paints its own arrival
        f = self.festival
        for i in range(3):
            self.burst(int(self.width * (0.3 + 0.2 * i)), int(self.height * 0.34 + 26 * i),
                       f.palette[i % len(f.palette)], n=14, speed=6.0)

    def next(self) -> None:
        self.switch(self.fest + 1)

    # ----- actions ---------------------------------------------------------

    def sprite(self, color) -> np.ndarray:
        key = tuple(int(c) for c in color)
        if key not in self._sprites:
            self._sprites[key] = make_splash(46, key)
        return self._sprites[key]

    def dab_cheek(self, x: int, y: int, color) -> None:
        """One persistent gulaal dab on a cheek."""
        self.paints.append([int(x), int(y), 0.82, tuple(color)])
        if len(self.paints) > CHEEK_STAMPS_MAX:
            self.paints.pop(0)

    def burst(self, x: int, y: int, color, n: int = 30, speed: float = 7.5) -> None:
        rng = np.random.default_rng(self.tick * 8 + n)
        for _ in range(n):
            angle = rng.uniform(0, 2 * math.pi)
            v = rng.uniform(speed * 0.35, speed)
            self._splash_append(x, y, math.cos(angle) * v, math.sin(angle) * v - 2,
                                int(rng.uniform(26, 44)), color)

    def rain_at(self, x: int) -> None:
        """Paani! droplets spawn above and fall past the raised hand."""
        rng = np.random.default_rng(self.tick)
        for _ in range(3):
            self._splash_append(x + int(rng.uniform(-46, 46)), int(-rng.uniform(0, 60)),
                                int(rng.uniform(-1, 1)), int(rng.uniform(4, 7)), int(rng.uniform(60, 90)),
                                WATER, rain=True)

    def _splash_append(self, x, y, vx, vy, life, color, rain=False) -> None:
        self.drops.append([x, y, vx, vy, 0, life, tuple(color), rain])

    def art_for(self, fest: Festival) -> dict:
        """(Re)make scene art lazily per festival - each one its own identity."""
        key = id(fest)
        cache = getattr(self, "_art_cache", {})
        if key not in cache:
            cache = {key: {
                "garland": make_garland(self.width, list(fest.palette)) if fest.garland else None,
                "lights": make_lights(self.width, list(fest.palette)) if fest.lights else None,
                "rangoli": make_rangoli(int(self.width * 0.11), fest.palette) if fest.rangoli else None,
                "moon": make_moon(64, GOLD) if fest.moon else None,
                "wash": make_wash(self.width, self.height, *fest.wash) if fest.wash else None,
            }}
            self._art_cache = cache
        return cache[key]


def stage_frame(raw: np.ndarray, session: Session) -> np.ndarray:
    """Center-crop to 16:9 and upscale + sharpen + color-grade to full HD.

    This is the "camera is the stage" step: the sensor's 480x640 becomes a
    full-screen, premium-looking image before any FX touch it.
    """
    import cv2

    h, w = raw.shape[:2]
    target = session.width / session.height
    if w / h > target:                     # too wide -> crop sides
        cw = int(h * target)
        x0 = (w - cw) // 2
        crop = raw[:, x0:x0 + cw]
    else:                                  # too tall -> crop top/bottom
        ch = int(w / target)
        y0 = max(0, (h - ch) // 2)
        crop = raw[y0:y0 + ch]
    out = cv2.resize(crop, (session.width, session.height), interpolation=cv2.INTER_CUBIC)
    # premium finish: unsharp mask + gentle warm grade (looks like real FHD)
    blur = cv2.GaussianBlur(out, (0, 0), 2.2)
    out = cv2.addWeighted(out, 1.32, blur, -0.32, 0)
    out = cv2.convertScaleAbs(out, alpha=1.06, beta=3)
    out[:, :, 2] = np.clip(out[:, :, 2].astype(np.int16) + 6, 0, 255).astype(np.uint8)
    return out


def face_dab(session: Session, face: FaceState) -> None:
    """Head tilt -> gulaal lands on the cheek on that exact side."""
    f = session.festival
    if not f.cheek_paint:
        return
    if abs(face.tilt) < TILT_ON:
        session.tilt_armed = abs(face.tilt) < TILT_OFF
        return
    if not session.tilt_armed:
        return
    cheek = face.cheeks[0] if face.tilt < 0 else face.cheeks[1]
    color = f.palette[(session.tick // 3) % len(f.palette)]
    session.dab_cheek(*cheek, color)
    session.tilt_armed = False


def update_rain(session: Session, hand: HandState | None) -> None:
    """Hand raised -> paani falls from above, down past the hand."""
    if hand is not None and session.festival.rain and hand.wrist[1] < RAIN_Y * session.height:
        session.rain_at(hand.wrist[0])


def update_ribbon(session: Session, hand: HandState | None) -> None:
    """Glide your hand -> the fingertip leaves a thick paint ribbon in the air.

    This is FestiCam's signature interaction: you literally draw in the air
    with festival colors. Fast strokes = thick vivid ribbons; stop moving
    and the paint hangs there, then slowly melts away.
    """
    if hand is None:
        return
    tip = (int(hand.tips[1][0]), int(hand.tips[1][1]))
    sm = session._sm
    if sm is None:
        session._sm = tip
        return
    gx = int(sm[0] * 0.55 + tip[0] * 0.45)      # smooth out MediaPipe jitter
    gy = int(sm[1] * 0.55 + tip[1] * 0.45)
    dist = math.hypot(gx - sm[0], gy - sm[1])
    session._sm = (gx, gy)
    if dist < GLIDE_MIN:
        return
    f = session.festival
    color = f.palette[(session.tick // 3) % len(f.palette)]
    width = max(3, int(4 + min(dist, 42) / 3))
    session.ribbons.append([sm[0], sm[1], gx, gy, tuple(color), 0,
                            int(34 + min(dist, 40) * 0.9), width])
    if len(session.ribbons) > RIBBON_MAX:
        del session.ribbons[:len(session.ribbons) - RIBBON_MAX]
    if dist > 30:                               # fast strokes throw off sparkles
        rng = np.random.default_rng(session.tick * 5 + int(dist))
        for _ in range(3):
            session._splash_append((gx + sm[0]) // 2 + int(rng.uniform(-18, 18)),
                                   (gy + sm[1]) // 2 + int(rng.uniform(-18, 18)),
                                   int(rng.uniform(-2, 2)), int(rng.uniform(1, 4)),
                                   int(rng.uniform(18, 30)), color)


def pinch_burst(session: Session, hand: HandState) -> None:
    d = hand.pinch[1]                    # thumb-index is the action gesture
    if not session.pinch_closed and d < ON and session.tick - session.last_burst > COOLDOWN:
        session.pinch_closed = True
        session.last_burst = session.tick
        tip = hand.tips[1]
        color = session.festival.burst_color
        session.burst(tip[0], tip[1], color, n=34, speed=8.5)
        session.burst(tip[0], tip[1],
                      session.festival.palette[(session.tick // 5) % len(session.festival.palette)],
                      n=18, speed=5.5)
    elif session.pinch_closed and d > OFF:
        session.pinch_closed = False


def spawn_ambience(session: Session) -> None:
    f = session.festival
    want = 90 if f.snow else (120 if f.confetti else 0)
    if want and len(session.flakes) < want:
        rng = np.random.default_rng(session.tick * 13 + len(session.flakes))
        while len(session.flakes) < want:
            color = WHITEISH if f.snow else f.palette[len(session.flakes) % len(f.palette)]
            session.flakes.append([int(rng.integers(0, session.width)),
                                   int(-rng.integers(0, session.height)),
                                   int(rng.integers(2, 5)), int(rng.integers(14, 40)), color])
    elif not want and session.flakes:
        session.flakes.clear()
    if f.stars and len(session.twinkles) < 70:
        rng = np.random.default_rng(session.tick * 7 + 11)
        while len(session.twinkles) < 70:
            session.twinkles.append((int(rng.integers(0, session.width)),
                                     int(rng.integers(0, int(session.height * 0.72)))))
    elif not f.stars and session.twinkles:
        session.twinkles.clear()
    if f.embers and len(session.embers) < 46:
        rng = np.random.default_rng(session.tick * 17 + len(session.embers))
        while len(session.embers) < 46:
            warm = ((20, 110, 255), (30, 60, 250), (40, 190, 255))[int(rng.integers(0, 3))]
            session.embers.append([int(rng.integers(0, session.width)),
                                   int(session.height + rng.integers(0, 120)),
                                   int(rng.integers(2, 5)), int(rng.integers(10, 34)),
                                   0, int(rng.uniform(80, 150)),
                                   tuple(int(c) for c in warm)])
    elif not f.embers and session.embers:
        session.embers.clear()


def _step_fx(session: Session) -> None:
    alive = []
    for d in session.drops:
        d[0] += int(d[2])
        d[1] += int(d[3])
        d[3] += 1.1                                # gravity
        d[4] += 1
        if d[4] < d[5] and d[1] < session.height + 8:
            alive.append(d)
    session.drops = alive
    for r in session.ribbons:
        r[5] += 1                                  # ribbons hang, then melt away
    while session.ribbons and session.ribbons[0][5] >= session.ribbons[0][6]:
        session.ribbons.pop(0)
    alive_e = []
    for e in session.embers:
        e[1] -= e[2]                               # sparks rise
        e[0] += int(1.6 * math.sin((session.tick + e[3]) / e[3] * 3.1))
        e[4] += 1
        if e[4] < e[5] and e[1] > -20:
            alive_e.append(e)
    session.embers = alive_e


def run_over_frame(frame_bgr: np.ndarray, session: Session,
                   hand: HandState | None = None, face: FaceState | None = None) -> np.ndarray:
    """Advance one frame; the frame is the full-screen camera image itself."""
    import cv2

    session.tick += 1
    spawn_ambience(session)

    if hand is not None:
        session.trail.append((int(hand.x), int(hand.y)))
        if len(session.trail) > 22:
            del session.trail[:6]
        update_ribbon(session, hand)
        update_rain(session, hand)
        pinch_burst(session, hand)
    if face is not None:
        face_dab(session, face)
    _step_fx(session)

    scene = frame_bgr
    _vignette_bottom(scene)
    art = session.art_for(session.festival)
    if art["wash"] is not None:                    # the festival's own color mood
        overlay(scene, art["wash"], 0, 0, WASH_ALPHA)
    if art["rangoli"] is not None:
        r = art["rangoli"]
        stamp_true(scene, r, int(session.width * 0.075), int(session.height * 0.86), 1.0, 0.9)
        stamp_true(scene, flip_h(r), session.width - int(session.width * 0.075),
                   int(session.height * 0.86), 1.0, 0.9)
    if art["moon"] is not None:
        stamp_true(scene, art["moon"], session.width - int(session.width * 0.10),
                   int(session.height * 0.24), 1.0, 0.96)
    if art["lights"] is not None:
        overlay(scene, art["lights"], 0, 0, 0.95)
    if art["garland"] is not None:
        overlay(scene, art["garland"], 0, 0, 0.97)

    _draw_ribbons(scene, session)
    _draw_twinkles(scene, session)
    _draw_embers(scene, session)
    _draw_flakes(scene, session)
    _draw_drops(scene, session)
    _draw_paints(scene, session)
    if hand is not None:
        _draw_cursor(scene, session, hand)
    _draw_banner(scene, session)
    _hud(scene, session)
    return scene


def _draw_ribbons(scene: np.ndarray, session: Session) -> None:
    import cv2

    for x0, y0, x1, y1, color, age, life, width in session.ribbons:
        fade = max(0.0, 1.0 - age / max(life, 1))
        if fade <= 0:
            continue
        c = tuple(int(v * (0.35 + 0.65 * fade)) for v in color)
        cv2.line(scene, (int(x0), int(y0)), (int(x1), int(y1)), c, width, cv2.LINE_AA)
        cv2.line(scene, (int(x0), int(y1 - 2)), (int(x1), int(y1 - 2)),
                 tuple(int(v * 0.8) for v in c), max(2, width // 3), cv2.LINE_AA)


def _draw_embers(scene: np.ndarray, session: Session) -> None:
    import cv2

    for x, y, vy, sway, age, life, color in session.embers:
        fade = max(0.0, 1.0 - age / max(life, 1))
        flick = 0.75 + 0.25 * math.sin((session.tick + sway * 7) / 5.0)
        c = tuple(int(v * fade * flick) for v in color)
        cv2.circle(scene, (int(x), int(y)), int(2 + 2 * fade), c, -1, cv2.LINE_AA)
        cv2.line(scene, (int(x), int(y - 7)), (int(x), int(y)),
                 tuple(int(v * fade * 0.45) for v in color), 1, cv2.LINE_AA)


def stamp_true(scene, art, cx, cy, scale, alpha):
    import cv2

    if scale != 1.0:
        art = cv2.resize(art, (int(art.shape[1] * scale), int(art.shape[0] * scale)),
                         interpolation=cv2.INTER_AREA)
    overlay(scene, art, cx - art.shape[1] // 2, cy - art.shape[0] // 2, alpha)


def flip_h(art: np.ndarray) -> np.ndarray:
    return art[:, ::-1].copy()


def _vignette_bottom(scene: np.ndarray) -> None:
    """Soften the very bottom for HUD readability (cheap gradient band)."""
    import cv2

    h = scene.shape[0]
    band = 110
    grad = np.linspace(0, 1, band, dtype=np.float32)[:, None, None] * 0.42
    strip = (scene[h - band:] * (1 - grad)).astype(np.uint8)
    scene[h - band:] = strip


def _draw_twinkles(scene: np.ndarray, session: Session) -> None:
    import cv2

    for i, (x, y) in enumerate(session.twinkles):
        tw = 0.5 + 0.5 * math.sin((session.tick + i * 13) / 17.0)
        c = tuple(int(v * (0.3 + tw * 0.8)) for v in GOLD)
        cv2.circle(scene, (x, y), 2 + int(2 * tw), c, -1, cv2.LINE_AA)


def _draw_flakes(scene: np.ndarray, session: Session) -> None:
    import cv2

    snow = session.festival.snow
    for fl in session.flakes:
        fl[0] += int(2 * math.sin((session.tick + fl[3]) / fl[2] * 4))
        fl[1] += fl[2] + 1
        if fl[1] > session.height:
            fl[1] = -6
        cv2.circle(scene, (int(fl[0]), int(fl[1])), 3 if snow else 4, fl[4], -1, cv2.LINE_AA)


def _draw_drops(scene: np.ndarray, session: Session) -> None:
    import cv2

    for x, y, vx, vy, age, life, color, rain in session.drops:
        fade = max(0.15, 1.0 - age / max(life, 1))
        c = tuple(int(v * fade) for v in color)
        r = 5 if rain else max(2, int(7 * fade))
        if rain:                                   # teardrop: tail + bead
            cv2.line(scene, (int(x), int(y - 14)), (int(x), int(y)), tuple(int(v * fade * 0.5) for v in color), 1,
                     cv2.LINE_AA)
        cv2.circle(scene, (int(x), int(y)), r, c, -1, cv2.LINE_AA)
        cv2.circle(scene, (int(x) - 1, int(y) - 1), max(1, r // 3), (255, 255, 255), -1, cv2.LINE_AA)


def _draw_paints(scene: np.ndarray, session: Session) -> None:
    for x, y, alpha, color in session.paints:
        stamp(scene, session.sprite(color), x, y, scale=1.0, alpha=alpha)


def _draw_cursor(scene: np.ndarray, session: Session, hand: HandState) -> None:
    import cv2

    pts = session.trail[-18:]
    color = session.festival.burst_color
    for i in range(1, len(pts)):
        t = i / len(pts)
        col = tuple(int(c * t) for c in color)
        cv2.line(scene, pts[i - 1], pts[i], col, max(1, int(4 * t)), cv2.LINE_AA)
    tip = hand.tips[1]
    glow = tuple(int(c * 0.55) for c in color)
    cv2.circle(scene, tuple(tip), 12, glow, -1, cv2.LINE_AA)
    cv2.circle(scene, tuple(tip), 6, (255, 255, 255), -1, cv2.LINE_AA)


def _draw_banner(scene: np.ndarray, session: Session) -> None:
    import cv2

    f = session.festival
    age = session.tick - session.fest_start
    slide = max(0.0, 1.0 - age / 16.0)
    y = int(210 - 160 * slide)
    scale = 1.1 if len(f.title) <= 18 else 0.9
    (tw, _), _ = cv2.getTextSize(f.title, cv2.FONT_HERSHEY_COMPLEX, scale, 3)
    x = (session.width - tw) // 2
    shimmy = int(2 * math.sin(session.tick / 30))
    soft = tuple(int(c * 0.4) for c in f.burst_color)
    cv2.putText(scene, f.title, (x + 2, y + 2), cv2.FONT_HERSHEY_COMPLEX, scale, (18, 18, 26), 4, cv2.LINE_AA)
    cv2.putText(scene, f.title, (x, y + shimmy), cv2.FONT_HERSHEY_COMPLEX, scale, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(scene, f.title, (x, y + shimmy), cv2.FONT_HERSHEY_COMPLEX, scale, soft, 1, cv2.LINE_AA)
    (tw2, _), _ = cv2.getTextSize(f.hint, cv2.FONT_HERSHEY_SIMPLEX, 0.56, 1)
    cv2.putText(scene, f.hint, ((session.width - tw2) // 2, y + 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.56, (238, 238, 238), 1, cv2.LINE_AA)


def _hud(scene: np.ndarray, session: Session) -> None:
    import cv2

    text = "1-6 festivals     c clean the cheeks     q quit"
    cv2.putText(scene, text, (22, scene.shape[0] - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (234, 234, 234), 1, cv2.LINE_AA)
    cv2.putText(scene, f"FestiCam  {session.festival.title.lower()}",
                (scene.shape[1] - 262, scene.shape[0] - 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (196, 196, 196), 1, cv2.LINE_AA)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="festicam", description="Open the camera and the festival arrives.")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args(argv)

    try:
        import cv2
    except ImportError:
        print("FestiCam needs opencv-python: pip install opencv-python")
        return 2
    try:
        import mediapipe  # noqa: F401
    except ImportError:
        print("FestiCam needs mediapipe: pip install mediapipe")
        return 2

    session = Session(width=args.width, height=args.height)
    hand_tracker = HandTracker()
    face_tracker = FaceTracker()

    if sys.platform == "win32":
        cam = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        if not cam.isOpened():
            cam = cv2.VideoCapture(args.camera)
    else:
        cam = cv2.VideoCapture(args.camera)
    if not cam.isOpened():
        print("could not open camera %d" % args.camera)
        return 2
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    win = "FestiCam - festival in your camera"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.waitKey(1)
    print("FestiCam (silent edition) - tilt head to paint cheeks, raise hand for paani, pinch to burst. 1-6 festivals, q quit.")
    try:
        while True:
            ok, raw = cam.read()
            if not ok:
                break
            raw = cv2.flip(raw, 1)                      # mirror: screen matches the user
            frame = stage_frame(raw, session)
            hand = hand_tracker.process(frame)
            face = face_tracker.process(frame)
            out = run_over_frame(frame, session, hand, face)
            cv2.imshow(win, out)
            key = cv2.waitKeyEx(1) & 0xFF
            if key == ord("q") or key == 27:
                break
            if key in b"123456":
                session.switch(key - ord("1"))
            elif key == ord("c"):
                session.paints.clear()
    except KeyboardInterrupt:
        pass
    except Exception:
        import traceback

        traceback.print_exc()
        return 1
    finally:
        hand_tracker.close()
        face_tracker.close()
        cam.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())
