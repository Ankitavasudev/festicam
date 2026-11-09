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
    wash: tuple                   # (top, bottom) bgr scene tint -> each festival's mood
    garland: bool = False         # marigold art across the top
    lights: bool = False          # glowing fairy-light string across the top
    rangoli: bool = False         # mandala art in the corners
    moon: bool = False            # glowing crescent
    stars: bool = False           # twinkling sparkles
    embers: bool = False          # warm sparks rising from below
    snow: bool = False            # snowfall ambience
    confetti: bool = False        # falling confetti ambience
    rain: bool = False            # hand raised -> paani falls
    cheek_paint: bool = False     # head tilt -> gulaal on the cheeks
    burst_color: tuple = field(default_factory=lambda: PINK)


HOLI = Festival(
    key="1",
    title="HAPPY HOLI!",
    hint="glide your hand to paint ribbons   |   tilt head for gulaal   |   pinch for a burst",
    palette=[PINK, MAGENTA, SUNSET, GREEN, CYAN, VIOLET],
    wash=((170, 70, 210), (60, 180, 90)),
    garland=True,
    rangoli=True,
    rain=True,
    cheek_paint=True,
    burst_color=PINK,
)

DIWALI = Festival(
    key="2",
    title="HAPPY DIWALI!",
    hint="glide golden ribbons in the air   |   pinch to launch fireworks",
    palette=[GOLD, SUNSET, PINK, CYAN],
    wash=((30, 100, 245), (10, 40, 160)),
    lights=True,
    rangoli=True,
    stars=True,
    embers=True,
    burst_color=GOLD,
)

RAKHI = Festival(
    key="3",
    title="HAPPY RAKSHA BANDHAN!",
    hint="wave your hand - rosy ribbons follow it   |   pinch for a sparkle",
    palette=[GOLD, PINK, SUNSET],
    wash=((150, 90, 225), (90, 130, 255)),
    garland=True,
    stars=True,
    burst_color=GOLD,
)

EID = Festival(
    key="4",
    title="EID MUBARAK!",
    hint="glide silver-green ribbons   |   look up - the crescent is yours",
    palette=[GOLD, GREEN, CYAN],
    wash=((255, 205, 80), (255, 160, 50)),
    moon=True,
    lights=True,
    stars=True,
    burst_color=GREEN,
)

CHRISTMAS = Festival(
    key="5",
    title="MERRY CHRISTMAS!",
    hint="let it snow   |   glide icy ribbons   |   tilt for a rosy glow",
    palette=[CYAN, (40, 40, 200), WHITEISH, GOLD],
    wash=((250, 130, 70), (0, 30, 80)),
    garland=True,
    snow=True,
    cheek_paint=True,
    burst_color=(60, 60, 255),
)

NEW_YEAR = Festival(
    key="6",
    title="HAPPY NEW YEAR!",
    hint="glide neon ribbons   |   pinch the sky to ring in midnight",
    palette=[GOLD, MAGENTA, PINK, CYAN, GREEN],
    wash=((200, 40, 170), (0, 15, 50)),
    confetti=True,
    lights=True,
    stars=True,
    burst_color=GOLD,
)

FESTIVALS = (HOLI, DIWALI, RAKHI, EID, CHRISTMAS, NEW_YEAR)
