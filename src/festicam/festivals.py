"""Festival data: palette, banner, ambience, and per-festival behaviors.

Adding a new festival = adding one FESTIVALS entry. The engine in app.py
is generic; only data lives here. No sound in FestiCam - the vibe is
pure picture.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# bgr colors
PINK = (180, 60, 255)
MAGENTA = (255, 90, 200)
SUNSET = (60, 130, 255)
GREEN = (80, 220, 80)
CYAN = (255, 190, 40)
GOLD = (30, 200, 255)
VIOLET = (220, 60, 220)
WHITEISH = (242, 242, 242)
WATER = (255, 198, 88)          # soft pani blue
GARLAND = (60, 170, 240)        # marigold orange


@dataclass
class Festival:
    key: str                      # hotkey 1..6
    title: str
    hint: str                     # one easy line: what to do
    palette: list[int]            # bgr colors for cheek paint + bursts
    garland: bool = False         # marigold art across the top
    rangoli: bool = False         # mandala art in the corners
    moon: bool = False            # glowing crescent
    stars: bool = False           # twinkling sparkles
    snow: bool = False            # snowfall ambience
    confetti: bool = False        # falling confetti ambience
    rain: bool = False            # hand raised -> paani falls
    cheek_paint: bool = False     # head tilt -> gulaal on the cheeks
    burst_color: tuple = field(default_factory=lambda: PINK)


HOLI = Festival(
    key="1",
    title="HAPPY HOLI!",
    hint="tilt your head to paint your cheeks   |   raise a hand for paani   |   pinch for a burst",
    palette=[PINK, MAGENTA, SUNSET, GREEN, CYAN, VIOLET],
    garland=True,
    rangoli=True,
    rain=True,
    cheek_paint=True,
    burst_color=PINK,
)

DIWALI = Festival(
    key="2",
    title="HAPPY DIWALI!",
    hint="tilt to light up your cheeks with gold   |   pinch to launch fireworks",
    palette=[GOLD, SUNSET, PINK, CYAN],
    garland=True,
    rangoli=True,
    stars=True,
    cheek_paint=True,
    burst_color=GOLD,
)

RAKHI = Festival(
    key="3",
    title="HAPPY RAKSHA BANDHAN!",
    hint="raise your hand to catch the blessings   |   pinch for a sparkle",
    palette=[GOLD, PINK, SUNSET],
    garland=True,
    stars=True,
    burst_color=GOLD,
)

EID = Festival(
    key="4",
    title="EID MUBARAK!",
    hint="look up - the crescent is yours tonight   |   pinch for sparkles",
    palette=[GOLD, GREEN, CYAN],
    garland=True,
    moon=True,
    stars=True,
    burst_color=GREEN,
)

CHRISTMAS = Festival(
    key="5",
    title="MERRY CHRISTMAS!",
    hint="let it snow   |   tilt for a rosy cheeks glow   |   pinch for a twinkle",
    palette=[GOLD, CYAN, SUNSET, WHITEISH],
    garland=True,
    snow=True,
    cheek_paint=True,
    burst_color=(60, 60, 255),
)

NEW_YEAR = Festival(
    key="6",
    title="HAPPY NEW YEAR!",
    hint="pinch the sky to ring in midnight   |   raise a hand for confetti",
    palette=[GOLD, MAGENTA, PINK, CYAN, GREEN],
    garland=True,
    confetti=True,
    stars=True,
    rain=True,
    burst_color=GOLD,
)

FESTIVALS = (HOLI, DIWALI, RAKHI, EID, CHRISTMAS, NEW_YEAR)
