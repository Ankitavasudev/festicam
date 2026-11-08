"""Festival data: palettes, banners, music, and per-festival behavior.

Adding a new festival = adding one FESTIVALS entry. The engine in app.py
is generic; only data lives here.
"""

from __future__ import annotations

from dataclasses import dataclass

from .synth import JINGLE_BELLS, SPARKLE_BELLS, KICK, SNARE, HIHAT

# bgr colors
PINK = (180, 60, 255)
MAGENTA = (255, 90, 200)
SUNSET = (60, 130, 255)
GREEN = (80, 220, 80)
CYAN = (255, 190, 40)
GOLD = (30, 200, 255)
VIOLET = (220, 60, 220)
WHITEISH = (240, 240, 240)


@dataclass
class Festival:
    key: str                       # hotkey 1..6
    title: str                     # big banner line
    subtitle: str
    palette: list[int]             # bgr colors used by particles/garlands
    groove: tuple = ()             # drum step pattern when music on
    melody: tuple = ()             # bell note sequence, overrides groove
    spray: bool = False            # pointing finger sprays palette from the tip
    fireworks: bool = False        # pinch launches a firework at the finger
    wrist_ring: bool = False       # golden ring ties itself around the wrist
    snow: bool = False             # snowfall ambience
    stars: bool = False            # twinkling ambient sparkles
    diyas: bool = False            # row of oil lamps at the bottom
    stains: bool = False           # colors accumulate on the wall (Holi paint)
    confetti: bool = False         # falling confetti ambience
    crescent: bool = False         # big crescent moon


HOLI = Festival(
    key="1",
    title="HAPPY HOLI!",
    subtitle="point to spray gulaal  |  pinch for a color bomb",
    palette=[PINK, MAGENTA, SUNSET, GREEN, CYAN, VIOLET],
    groove=(KICK, HIHAT, SNARE, HIHAT, KICK, KICK, SNARE, HIHAT),
    spray=True,
    stains=True,
    confetti=True,
)

DIWALI = Festival(
    key="2",
    title="HAPPY DIWALI!",
    subtitle="pinch to launch fireworks  |  point for golden phuljhadi",
    palette=[GOLD, SUNSET, PINK, CYAN],
    spray=True,
    fireworks=True,
    diyas=True,
    stars=True,
)

RAKHI = Festival(
    key="3",
    title="HAPPY RAKSHA BANDHAN!",
    subtitle="show your wrist - the rakhi ties itself",
    palette=[GOLD, PINK, SUNSET],
    wrist_ring=True,
    stars=True,
)

EID = Festival(
    key="4",
    title="EID MUBARAK!",
    subtitle="look up - the crescent is yours tonight",
    palette=[GOLD, GREEN, CYAN],
    melody=SPARKLE_BELLS,
    wrist_ring=True,
    stars=True,
    crescent=True,
)

CHRISTMAS = Festival(
    key="5",
    title="MERRY CHRISTMAS!",
    subtitle="wave for snow  |  hum along - Jingle Bells is live",
    palette=[GOLD, CYAN, SUNSET, WHITEISH],
    melody=JINGLE_BELLS,
    spray=True,
    snow=True,
)

NEW_YEAR = Festival(
    key="6",
    title="HAPPY NEW YEAR!",
    subtitle="pinch to ring in the midnight sky",
    palette=[GOLD, MAGENTA, PINK, CYAN, GREEN],
    fireworks=True,
    confetti=True,
)

FESTIVALS = (HOLI, DIWALI, RAKHI, EID, CHRISTMAS, NEW_YEAR)
