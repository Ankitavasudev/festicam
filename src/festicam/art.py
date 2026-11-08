"""Sticker-grade overlay art, prerendered once at startup.

Everything here is drawn in code (no asset downloads, no cheap flat
vector UI): layered petals, soft shadows, glow bloom, irregular painterly
edges.  All big pieces (garland, rangoli, moon) are rendered once at init,
so a frame only pays a handful of alpha blends.

All layers are BGRA uint8 canvases.  Compose with overlay()/stamp().
"""

from __future__ import annotations

import math

import numpy as np


def blank(w: int, h: int) -> np.ndarray:
    return np.zeros((max(1, h), max(1, w), 4), dtype=np.uint8)


def overlay(scene: np.ndarray, art: np.ndarray, x: int, y: int, alpha: float = 1.0) -> None:
    """Alpha-composite an BGRA art layer onto a BGR scene (clipping-safe)."""
    ah, aw = art.shape[:2]
    H, W = scene.shape[:2]
    x0, y0 = max(int(x), 0), max(int(y), 0)
    x1, y1 = min(int(x) + aw, W), min(int(y) + ah, H)
    if x1 <= x0 or y1 <= y0:
        return
    roi = art[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.uint16)
    k = int(max(0.0, min(1.0, alpha)) * 256)
    a = (roi[:, :, 3] * k + 127) // 255           # 0..256 (256 = fully opaque)
    src = roi[:, :, :3]
    dst = scene[y0:y1, x0:x1].astype(np.uint16)
    a = a[..., None]
    blended = (dst * (256 - a) + src * a) >> 8
    scene[y0:y1, x0:x1] = blended.astype(np.uint8)


def stamp(scene: np.ndarray, art: np.ndarray, cx: float, cy: float,
          scale: float = 1.0, alpha: float = 1.0) -> None:
    """Composite a small art sprite centered at a point."""
    import cv2

    if scale <= 0:
        return
    w = max(1, int(art.shape[1] * scale))
    h = max(1, int(art.shape[0] * scale))
    if scale != 1.0:
        art = cv2.resize(art, (w, h), interpolation=cv2.INTER_AREA)
    overlay(scene, art, int(cx - w / 2), int(cy - h / 2), alpha)


def _shadow(canvas: np.ndarray, cx: int, cy: int, r: int, strength: int = 80) -> None:
    import cv2

    cv2.circle(canvas, (cx + 2, cy + 4), r, (26, 24, 36, strength), -1, cv2.LINE_AA)


def _marigold(canvas: np.ndarray, cx: int, cy: int, r: int, palette, rng) -> None:
    """Layered petal pom-pom: shadow first, then rim -> fill -> lit core."""
    import cv2

    color = palette[int(rng.integers(0, len(palette)))]
    light = tuple(min(255, int(c * 1.45) + 42) for c in color)
    dark = tuple(int(c * 0.52) for c in color)
    _shadow(canvas, cx, cy, int(r * 1.02))
    petals = 13
    for i in range(petals):
        a = 2 * math.pi * i / petals + rng.uniform(-0.09, 0.09)
        px, py = cx + int(1.05 * r * math.cos(a)), cy + int(1.05 * r * math.sin(a))
        cv2.ellipse(canvas, (px, py), (int(r * 0.5), int(r * 0.29)),
                    math.degrees(a), 0, 360, dark + (255,), -1, cv2.LINE_AA)
    for i in range(petals):
        a = 2 * math.pi * (i + 0.5) / petals
        px, py = cx + int(0.68 * r * math.cos(a)), cy + int(0.68 * r * math.sin(a))
        cv2.ellipse(canvas, (px, py), (int(r * 0.4), int(r * 0.24)),
                    math.degrees(a), 0, 360, color + (255,), -1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), int(r * 0.5), light + (255,), -1, cv2.LINE_AA)
    cv2.circle(canvas, (cx - r // 6, cy - r // 6), int(r * 0.18), (255,) * 3 + (95,), -1, cv2.LINE_AA)


def _leaf(canvas: np.ndarray, cx: int, cy: int, w: int, h: int, angle: float) -> None:
    import cv2

    cv2.ellipse(canvas, (int(cx), int(cy)), (w, h), angle, 0, 360, (58, 148, 70, 235), -1, cv2.LINE_AA)
    cv2.line(canvas, (int(cx - w * math.cos(math.radians(angle))),
                      int(cy - w * math.sin(math.radians(angle)))),
             (int(cx + w * math.cos(math.radians(angle))),
              int(cy + w * math.sin(math.radians(angle)))), (40, 108, 52, 210), 1, cv2.LINE_AA)


def make_garland(width: int, palette, dip: float = 0.20) -> np.ndarray:
    """A drooping marigold garland string spanning the screen width."""
    import cv2

    h = int(width * dip) + 100
    canvas = blank(width, h)
    rng = np.random.default_rng(404)
    n = max(11, width // 84)
    for i in range(n + 1):
        t = i / n
        x = int(10 + (width - 20) * t)
        sag = int(math.sin(t * math.pi) * h * dip * 0.85) + 10
        y = 14 + sag
        if i % 2 == 0:
            _leaf(canvas, x + (22 if i % 4 == 0 else -22), y + 26, 24, 10, 32 * (1 if i % 4 else -1))
        _marigold(canvas, x, y, int(24 + 12 * rng.uniform()) + 6, palette, rng)
        if i < n:
            xa = int(10 + (width - 20) * ((i + 0.5) / n))
            r = int(8 + 5 * rng.uniform())
            cv2.circle(canvas, (xa, 18 + int(sag * 0.55) + 16), r,
                       tuple(int(c) for c in palette[int(rng.integers(0, len(palette)))]) + (225,), -1, cv2.LINE_AA)
    return _bloomy(canvas, 0.5)


def make_rangoli(size: int, palette) -> np.ndarray:
    """Mandala ornament: three petal rings + a dotted halo + warm core."""
    import cv2

    s = max(64, size) * 2
    canvas = blank(s, s)
    cx = cy = s // 2
    for ring, rr in enumerate((0.92, 0.70, 0.46)):
        color = palette[(ring * 2 + 1) % len(palette)]
        soft = tuple(int(c * 0.85) for c in color) + (175,)
        petals = 16
        for i in range(petals):
            a = 360 * i / petals
            off = (0.34 if ring == 1 else 0.52) * rr
            px, py = cx + int(s * off / 2 * math.cos(math.radians(a))), \
                     cy + int(s * off / 2 * math.sin(math.radians(a)))
            cv2.ellipse(canvas, (int(px), int(py)), (int(s * rr * 0.10), int(s * rr * 0.055)),
                        a, 0, 360, color + (238,), -1, cv2.LINE_AA)
        cv2.circle(canvas, (cx, cy), int(s * rr * 0.10), soft, -1, cv2.LINE_AA)
    for i in range(44):
        a = 2 * math.pi * i / 44
        rr = s * 0.44
        cv2.circle(canvas, (int(cx + rr * math.cos(a)), int(cy + rr * math.sin(a))),
                   max(3, s // 110), tuple(int(c) for c in palette[i % len(palette)]) + (232,), -1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), int(s * 0.075), (255, 250, 224, 255), -1, cv2.LINE_AA)
    return _bloomy(canvas, 0.6)


def make_splash(radius: int, color, alpha: float = 0.85) -> np.ndarray:
    """Irregular soft pigment blob - the cheek-paint stamp."""
    import cv2

    s = radius * 2 + 14
    canvas = blank(s, s)
    cx = cy = s // 2
    rng = np.random.default_rng(int(color[0]) * 7 + s)
    dark = tuple(int(c * 0.72) for c in color)
    for i in range(11):                      # irregular rim
        a = 2 * math.pi * i / 11
        rr = cx * 0.72
        px, py = cx + int(rr * math.cos(a)), cy + int(rr * math.sin(a))
        cv2.circle(canvas, (int(px), int(py)), int(radius * rng.uniform(0.30, 0.5)),
                   dark + (int(200 * alpha),), -1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), int(radius * 0.82), tuple(int(c) for c in color) + (int(238 * alpha),), -1, cv2.LINE_AA)
    rng2 = np.random.default_rng(int(color[2]) + 51)      # lighter speckles for depth
    for _ in range(7):
        px, py = cx + int(rng2.uniform(-0.4, 0.4) * s), cy + int(rng2.uniform(-0.4, 0.4) * s)
        light = tuple(min(255, int(c * 1.35) + 46) for c in color)
        cv2.circle(canvas, (int(px), int(py)), int(radius * rng2.uniform(0.10, 0.22)),
                   light + (int(130 * alpha),), -1, cv2.LINE_AA)
    return _bloomy(canvas, 0.7)


def make_moon(radius: int, color) -> np.ndarray:
    """True crescent: bright disc minus an offset disc, prerendered with glow."""
    import cv2

    s = radius * 2 + 30
    canvas = blank(s, s)
    cx = cy = s // 2
    cv2.circle(canvas, (cx, cy), radius, tuple(int(c) for c in color) + (255,), -1, cv2.LINE_AA)
    cv2.circle(canvas, (cx + int(radius * 0.62), cy - int(radius * 0.16)),
               int(radius * 0.9), (0, 0, 0, 0), -1)             # punch alpha out
    hv = canvas[:, :, 3]
    yy, xx = np.mgrid[0:s, 0:s]
    dist = (xx - (cx + radius * 0.62)) ** 2 + (yy - (cy - radius * 0.16)) ** 2
    hv[dist <= (radius * 0.9) ** 2] = 0
    canvas[:, :, 3] = hv
    # lit rim along the crescent's edge
    rim = tuple(min(255, int(c * 1.3) + 40) for c in color)
    cv2.ellipse(canvas, (cx, cy), (int(radius * 0.98), int(radius * 0.98)), 0, 40, 225,
                rim + (220,), 3, cv2.LINE_AA)
    return _bloomy(canvas, 0.75)


def _bloomy(canvas: np.ndarray, amount: float = 0.55) -> np.ndarray:
    """Additive bloom pass - gives the photo-glow that kills the flat look."""
    import cv2

    rgb = canvas[:, :, :3]
    a = canvas[:, :, 3]
    glow = cv2.GaussianBlur(rgb, (0, 0), 9)
    boost = cv2.addWeighted(rgb, 1.0, glow, amount, 0)
    return np.dstack([boost, a])
