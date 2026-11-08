"""Synthesis for FestiCam: festival drums, bells, and melodies.

Same zer-asset philosophy as the sibling project: every sound is computed
- kick/snare/hihat/crash drums, tuned bells for festival music, and whole
melodies (Jingle Bells!) rendered as note sequences. Playback tries
sounddevice, falls back to Windows' stdlib winsound (in-memory WAV), and
never raises on its own.
"""

from __future__ import annotations

import io
import wave

import numpy as np

RATE = 44100

KICK, SNARE, HIHAT, CRASH = range(4)
NAMES = ("kick", "snare", "hi-hat", "crash")
BELL = 4


def _env(n: int, decay: float) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / RATE
    return np.exp(-t / decay)


def _noise(rng_seed: int, n: int) -> np.ndarray:
    return np.random.default_rng(rng_seed).uniform(-1, 1, n)


def _highpass(noise: np.ndarray, k: int) -> np.ndarray:
    return noise - np.convolve(noise, np.ones(k) / k, mode="same")


def _kick() -> np.ndarray:
    n = int(RATE * 0.30)
    t = np.arange(n, dtype=np.float64) / RATE
    freq = 42.0 + 105.0 * np.exp(-t / 0.028)
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    click = _noise(7, n) * _env(n, 0.004) * 0.25
    return (np.sin(phase) * _env(n, 0.14) + click).astype(np.float32)


def _snare() -> np.ndarray:
    n = int(RATE * 0.22)
    t = np.arange(n, dtype=np.float64) / RATE
    tone = np.sin(2 * np.pi * 185 * t) + 0.5 * np.sin(2 * np.pi * 330 * t)
    tone *= _env(n, 0.09)
    noise = _highpass(_noise(11, n), 24) * _env(n, 0.055)
    return (0.4 * tone + noise).astype(np.float32)


def _hihat() -> np.ndarray:
    n = int(RATE * 0.09)
    t = np.arange(n, dtype=np.float64) / RATE
    noise = _highpass(_noise(23, n), 12) * _env(n, 0.022)
    return noise.astype(np.float32)


def _crash() -> np.ndarray:
    n = int(RATE * 0.9)
    t = np.arange(n, dtype=np.float64) / RATE
    shimmer = _highpass(_noise(31, n), 6) * _env(n, 0.3)
    return (0.7 * shimmer).astype(np.float32)


def bell(freq: float, dur: float = 0.8, soft: bool = False) -> np.ndarray:
    """Tuned bell-tone: sine + partials with a ringing envelope."""
    n = int(RATE * dur)
    t = np.arange(n, dtype=np.float64) / RATE
    tone = (np.sin(2 * np.pi * freq * t)
            + 0.45 * np.sin(2 * np.pi * freq * 2 * t)
            + 0.18 * np.sin(2 * np.pi * freq * 3.02 * t))
    decay = 0.5 if soft else 0.32
    return (tone * _env(n, decay) * (0.75 if soft else 1.0)).astype(np.float32)


_cache: dict[int, np.ndarray] = {}


def sample(drum: int) -> np.ndarray:
    """Cached instrument sample (drums + a default bell)."""
    if drum in _cache:
        return _cache[drum]
    if drum == KICK:
        s = _kick()
    elif drum == SNARE:
        s = _snare()
    elif drum == HIHAT:
        s = _hihat()
    elif drum == CRASH:
        s = _crash()
    elif drum == BELL:
        s = bell(880.0)
    else:
        raise ValueError(f"unknown instrument {drum}")
    _cache[drum] = s
    return s


def repitch(s: np.ndarray, pitch: float) -> np.ndarray:
    """Resample for a pitch shift - turns one bell into a whole scale."""
    n = len(s)
    idx = np.linspace(0, (n - 1) / max(pitch, 0.05), n)
    return np.interp(idx, np.arange(n), s).astype(np.float32)


# melodies: (note, beats) - note None = rest, freqs in Hz
_C4, _D4, _E4, _G4, _A4 = 261.6, 293.7, 329.6, 392.0, 440.0
JINGLE_BELLS = (
    (_E4, 1), (_E4, 1), (_E4, 2),
    (_E4, 1), (_E4, 1), (_E4, 2),
    (_E4, 1), (_G4, 1), (_C4, 1.5), (_D4, 0.5), (_E4, 4),
)
SPARKLE_BELLS = ((_E4, 1), (_G4, 1), (_E4, 1), (_C4, 1), (_D4, 1), (_E4, 2))  # sa re ga pa


def play_sound_buffer(device, buf: np.ndarray) -> bool:
    """Push one buffer out on the best available path. True = played."""
    if device is not None:
        try:
            device.play(buf, RATE)
            return True
        except Exception:
            return False
    return _winsound_buffer(buf)


def _winsound_buffer(buf: np.ndarray) -> bool:
    try:
        import winsound

        winsound.PlaySound(_to_wav(buf), winsound.SND_MEMORY | winsound.SND_ASYNC)
        return True
    except Exception:
        return False


def _to_wav(s: np.ndarray) -> bytes:
    peak = float(np.abs(s).max()) or 1.0
    s = s / peak * 0.85
    pcm = (np.clip(s, -1, 1) * 32767).astype("<i2")
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    return out.getvalue()


class Player:
    """Best-available audio out; absolute last resort = silence."""

    def __init__(self):
        try:
            import sounddevice

            self._device = sounddevice
            self.backend = "sounddevice"
        except Exception:
            self._device = None
            self.backend = "winsound" if _winsound_available() else "silent"

    def play(self, instrument: int, pitch: float = 1.0) -> None:
        try:
            play_sound_buffer(self._device, repitch(sample(instrument), pitch))
        except Exception:
            pass

    def play_note(self, freq: float, dur: float = 0.8, soft: bool = False) -> None:
        try:
            play_sound_buffer(self._device, bell(freq, dur, soft))
        except Exception:
            pass


def _winsound_available() -> bool:
    try:
        import winsound  # noqa: F401

        return True
    except Exception:
        return False
