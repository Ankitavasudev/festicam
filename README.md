# FestiCam 🪔🎨🎄🌙

**Open your camera and the festival arrives.** FestiCam is for everyone
celebrating away from family - the kid in the hostel, the cousin in another
country. You open the webcam and your screen turns into the festival:

| key | festival | what happens on screen |
| --- | --- | --- |
| `1` | **HOLI** | point your finger - gulaal sprays from your fingertip and paints the wall; pinch for a color bomb; dhol groove |
| `2` | **DIWALI** | pinch to launch fireworks into the sky; seven diyas flicker at the bottom; golden phuljhadi wand |
| `3` | **RAKHI** | your wrist gets a golden rakhi ring tied live with sparkles |
| `4` | **EID** | crescent moon glows, stars twinkle, soft chimes ring |
| `5` | **CHRISTMAS** | snowfall + **Jingle Bells melody synthesized live** - no sample files |
| `6` | **NEW YEAR** | midnight confetti rain + fireworks |

```bash
pip install git+https://github.com/Ankitavasudev/festicam@main
python -m festicam
```

Keys: `1-6` festivals · `n` next · `SPACE` music · `c` clean the wall · `q` quit.
Hand landmark model ships in the repo - nothing to download, nothing to train.

## Roadmap (the plan)

- ✅ Six festivals with gesture + music layers
- ☐ Voice announcement ("Happy Holi!" spoken greeting)
- ☐ Phone-as-webcam support (DroidCam) for the "iPhone camera" look
- ☐ Record & share: 15 s clip export with the FX baked in
- ☐ AI-generated festive background music per region

## How it works

| Layer | What happens |
|---|---|
| `tracker.py` | MediaPipe HandLandmarker (Tasks API, VIDEO mode) → fingertip positions + pinch distance, **normalized by hand scale** |
| `festivals.py` | Each festival is **pure data** - palette, banner, groove/melody, and its gesture behaviors (`spray`, `fireworks`, `wrist_ring`, `snow`, `diyas`, `crescent`...). New festival = new dataclass entry |
| `app.py` | Generic engine: hysteresis pinch gate (proven in AirJam), particle systems (drops with gravity, flakes with sway, stains that accumulate), drop-in camera card, banner animation, frame-clock music scheduler |
| `synth.py` | All sound synthesized in numpy at 44.1 kHz: drums, tuned bells with partials, and melodies like Jingle Bells encoded as note sequences. `sounddevice` → `winsound` fallback → silent, never crashes |

The test suite (21 tests) runs headless in CI - no camera, no audio needed.

## Interview 3-liner

> "FestiCam is a festival-anywhere webcam toy I built for people away from
> family: point your finger and Holi gulaal sprays and actually paints the
> wall; pinch and Diwali fireworks launch into the sky. Everything - colors,
> fireworks, even the Jingle Bells melody - is synthesized in numpy; festivals
> are pure data classes, so the engine is generic and headless-testable
> (pytest in CI, no camera needed)."
