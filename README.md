# FestiCam 🪔🎨🌙

**Open your camera and the festival arrives.** FestiCam is for everyone
celebrating away from family - the kid in the hostel, the cousin in another
country. You open the webcam and your screen *becomes* the festival:

| key | festival | what happens on screen |
| --- | --- | --- |
| `1` | **HOLI** | tilt your head left/right - **gulaal lands on that very cheek**; raise a hand - **paani falls**; pinch - color burst |
| `2` | **DIWALI** | tilt lights your cheeks with gold; pinch launches fireworks; art garland + rangoli corners |
| `3` | **RAKHI** | sparkles + pinch bursts of gold |
| `4` | **EID** | a true glowing crescent in the sky + twinkling stars |
| `5` | **CHRISTMAS** | snowfall ambience + rosy cheek glow |
| `6` | **NEW YEAR** | confetti rain + midnight bursts |

```bash
pip install git+https://github.com/Ankitavasudev/festicam@main
python -m festicam
```

Keys: `1-6` festivals · `c` clean the cheeks · `q` quit. That is the whole
interface - zero effort, one gesture per effect.

## The feel (v2)

- **The camera is the stage.** The webcam fills the screen (center-cropped
  to 16:9, upscaled to 1280x720 with an unsharp pass + warm color grade) -
  no side panel, no camera-in-a-box.
- **Sticker-grade art, zero image assets.** The marigold garland, rangoli
  mandalas, cheek-paint splashes and the Eid crescent are drawn in code
  (layered petals, soft shadows, painterly speckles, a bloom pass) and
  *prerendered once* at startup - a frame pays only alpha blends.
- **Silent by design.** No sound layer at all; the vibe is pure picture.
- **Head tilting works like a mirror.** Head tilts left -> the cheek on
  the left of the screen gets painted, exactly where you expect it.

## How it works

| Layer | What happens |
|---|---|
| `tracker.py` | MediaPipe HandLandmarker (Tasks API, VIDEO mode) -> fingertips + **wrist** + pinch distance normalized by hand scale |
| `faces.py` | MediaPipe FaceLandmarker (VIDEO mode, model ships in the repo) -> eye-line tilt + screen-space cheek anchors |
| `art.py` | Prerendered sticker art: `make_garland`, `make_rangoli`, `make_splash`, `make_moon` with a gaussian bloom pass |
| `festivals.py` | Each festival is **pure data** - palette, hint line, and behavior flags (`cheek_paint`, `rain`, `snow`, `garland`...). New festival = new dataclass entry |
| `app.py` | Generic engine: `stage_frame` (crop/upscale/grade), tilt->cheek dab with hysteresis, wrist-raised rain, hysteresis pinch gate (proven in AirJam), particle steps, banner + minimal HUD |

The test suite (33 tests) runs headless in CI - no camera, no face, no
audio needed.

## Roadmap

- ☐ 5-6 more festivals (Karwa Chauth, Baisakhi, Pongal, Halloween...)
- ☐ Record & share: 15 s clip export with the FX baked in
- ☐ Two faces at once (couple celebration)
- ☐ DroidCam / phone-webcam support for an even better camera look

## Interview 3-liner

> "FestiCam is a festival-anywhere webcam app I built for people away from
> family: open your camera and the screen turns into Holi, Diwali or Eid.
> Tilt your head and gulaal lands on that exact cheek; raise a hand and
> water falls. All the festive art is code-drawn and prerendered, the
> engine is data-driven per festival, and the test suite runs headless in CI."
