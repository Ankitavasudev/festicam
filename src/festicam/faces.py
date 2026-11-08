"""Face tracker: head tilt + cheek positions for the Holi paint moment.

Uses MediaPipe FaceLandmarker (Tasks API, VIDEO mode) with the model
shipped in models/face_landmarker.task.  MediaPipe imports lazily so the
headless test suite never needs it.

The camera frame is mirrored (cv2.flip) before it reaches us, so all
geometry below works in *screen* coordinates: "left" means the left of
what the user sees on screen, exactly like a mirror.  Tilt your head
left -> the cheek on the left of the screen gets painted.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

# landmark ids (mirrored-screen geometry, anatomical labels are MediaPipe's)
EYE_A, EYE_B = 33, 263                    # outer eye corners: the tilt line
CHEEK_A = (50, 101, 205)                  # cheek cluster, screen-left side
CHEEK_B = (280, 330, 425)                 # cheek cluster, screen-right side
NOSE = 1


@dataclass
class FaceState:
    """Head geometry in screen coordinates (pixels)."""

    tilt: float                  # -1 .. +1; who is lower: screen-left eye(<0) or right(>0)
    scale: float                 # eye-corner distance in px -> stamps size with the face
    cheeks: tuple[tuple[int, int], tuple[int, int]]     # (screen-left cheek, screen-right cheek)
    nose: tuple[int, int]


def roll_ratio(lm) -> float:
    """How tilted the eye line is, normalized by its own length (-1..1)."""
    a_pt, b_pt = lm[EYE_A], lm[EYE_B]
    dx, dy = b_pt.x - a_pt.x, b_pt.y - a_pt.y
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-6:
        return 0.0
    return dy / length


def cheek_point(lm, ids, w: int, h: int) -> tuple[int, int]:
    xs = [lm[i].x * w for i in ids]
    ys = [lm[i].y * h for i in ids]
    return int(sum(xs) / len(xs)), int(sum(ys) / len(ys))


def state_from(lm, w: int, h: int) -> FaceState:
    tilt = max(-1.0, min(1.0, roll_ratio(lm) * 3.0))
    eye_dist = abs(lm[EYE_B].x - lm[EYE_A].x) * w
    left = cheek_point(lm, CHEEK_A, w, h)
    right = cheek_point(lm, CHEEK_B, w, h)
    # keep the paint on the cheek that is actually on the tilt side
    if left[0] > right[0]:
        left, right = right, left
    nose = (int(lm[NOSE].x * w), int(lm[NOSE].y * h))
    return FaceState(tilt=tilt, scale=max(12.0, eye_dist), cheeks=(left, right), nose=nose)


class FaceTracker:
    """One face at a time. process() returns None when no face is visible."""

    def __init__(self):
        self._landmarker = None
        self._ts_ms = 0

    def _ensure(self):
        if self._landmarker is None:
            from pathlib import Path

            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            model_path = Path(__file__).resolve().parent / "models" / "face_landmarker.task"
            if not model_path.exists():
                model_path.parent.mkdir(parents=True, exist_ok=True)
                import urllib.request

                print("downloading face_landmarker.task (one-time)...")
                urllib.request.urlretrieve(MODEL_URL, model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=0.5,
            )
            self._landmarker = vision.FaceLandmarker.create_from_options(options)
        return self._landmarker

    def process(self, frame_bgr: np.ndarray) -> FaceState | None:
        import mediapipe as mp

        self._ts_ms += 33
        landmarker = self._ensure()
        rgb = frame_bgr[:, :, ::-1].copy()
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect_for_video(image, self._ts_ms)
        if not result.face_landmarks:
            return None
        h, w = frame_bgr.shape[:2]
        return state_from(result.face_landmarks[0], w, h)

    def close(self) -> None:
        self._landmarker = None
