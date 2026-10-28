"""TD Sequential setup, countdown and support/resistance counter.

Pure Python, no dependencies. Written from SPEC.md: one record per closed bar,
oldest first. Nothing here is trading advice; a count describes past prices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Tuple

__all__ = ["TdBar", "CountdownState", "Latest", "compute", "latest"]

MAX_LEVELS = 20
IDLE = 14  # cancellation / "no countdown in progress" value

# Attribute / key names accepted for each bar field, first match wins.
_NAMES = {
    "t": ("t", "time", "timestamp"),
    "o": ("o", "open"),
    "h": ("h", "high"),
    "l": ("l", "low"),
    "c": ("c", "close"),
}


@dataclass(frozen=True)
class TdBar:
    """One output record per input bar (SPEC.md, section 4)."""

    t: Any
    buy_setup: int
    sell_setup: int
    buy_countdown: int
    sell_countdown: int
    resistance: Optional[float]
    support: Optional[float]
    buy_deferred: bool
    sell_deferred: bool
    buy_perfected: bool
    sell_perfected: bool
    bullish_flip: bool
    bearish_flip: bool


@dataclass(frozen=True)
class CountdownState:
    """A countdown in progress: `count` of 13, `paused` when the last bar did not qualify."""

    count: int
    paused: bool


@dataclass(frozen=True)
class Latest:
    """Summary of the final bar of a `compute()` result."""

    t: Any
    buy_setup: int
    sell_setup: int
    buy_countdown: Optional[CountdownState]
    sell_countdown: Optional[CountdownState]
    buy_completed_13_now: bool
    sell_completed_13_now: bool
    last_buy_setup_9: Any
    last_sell_setup_9: Any
    last_buy_countdown_13: Any
    last_sell_countdown_13: Any
    resistance: Optional[float]
    support: Optional[float]


def _field(bar: Any, key: str, index: int) -> Any:
    names = _NAMES[key]
    if isinstance(bar, dict):
        for name in names:
            if name in bar:
                return bar[name]
    else:
        for name in names:
            if hasattr(bar, name):
                return getattr(bar, name)
    raise ValueError(f"bar {index}: missing field '{names[0]}' (also accepted: {', '.join(names[1:]) or 'none'})")


def _price(value: Any, key: str, index: int) -> float:
    if isinstance(value, bool):
        raise TypeError(f"bar {index}: '{key}' must be a number, got bool")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise TypeError(f"bar {index}: '{key}' must be a number, got {type(value).__name__}") from None
    if math.isnan(number):
        raise ValueError(f"bar {index}: '{key}' is NaN")
    return number


def _normalize(bars: Iterable[Any]) -> List[Tuple[Any, float, float, float]]:
    """Return (t, high, low, close) per bar. Accepts dicts, (t,o,h,l,c) tuples or objects."""
    rows: List[Tuple[Any, float, float, float]] = []
    for i, bar in enumerate(bars):
        if isinstance(bar, (tuple, list)):
            if len(bar) != 5:
                raise ValueError(f"bar {i}: a tuple bar must be (t, o, h, l, c), got {len(bar)} items")
            t, o, h, l, c = bar
        else:
            t, o, h, l, c = (_field(bar, k, i) for k in ("t", "o", "h", "l", "c"))
        _price(o, "o", i)
        rows.append((t, _price(h, "h", i), _price(l, "l", i), _price(c, "c", i)))
    return rows


class _Countdown:
    """State of one side's countdown (SPEC.md, section 3)."""

    def __init__(self) -> None:
        self.value = 0
        self.eight_close = math.nan

    def step(self, own9: bool, other9: bool, level_active: bool, qualifies: bool, test: bool, close: float) -> Tuple[int, bool]:
        prev = self.value
        deferred = False
        if own9:
            value = 1 if qualifies else 0
        elif other9 or not level_active:
            value = IDLE
        elif abs(prev) == 12 and qualifies and not test:
            value, deferred = -12, True
        elif qualifies:
            value = abs(prev) + 1
        else:
            value = 0 if prev == 0 else -abs(prev)
        if value == 8:  # only a transition to +8 gets here
            self.eight_close = close
        self.value = value
        return value, deferred


class _Level:
    __slots__ = ("price", "active")

    def __init__(self, price: float) -> None:
        self.price = price
        self.active = True


def _add_level(levels: List[_Level], price: float) -> None:
    if not price > 0 or any(x.active and x.price == price for x in levels):
        return
    levels.append(_Level(price))
    if len(levels) > MAX_LEVELS:
        levels.pop(0)


def _reported(levels: List[_Level]) -> Optional[float]:
    if levels and levels[-1].active:
        return levels[-1].price
    return None


def compute(bars: Iterable[Any]) -> List[TdBar]:
    """Compute one `TdBar` per input bar.

    `bars` is ordered oldest first and holds closed bars only. Each bar is a dict
    with keys t, o, h, l, c (long names such as "close" also work), a
    (t, o, h, l, c) tuple, or an object with those attributes.
    """
    rows = _normalize(bars)
    out: List[TdBar] = []
    resistances: List[_Level] = []
    supports: List[_Level] = []
    buy = _Countdown()
    sell = _Countdown()
    buy_setup = 0
    sell_setup = 0

    for i, (t, h, l, c) in enumerate(rows):
        buy_setup = buy_setup + 1 if i >= 4 and c < rows[i - 4][3] else 0
        sell_setup = sell_setup + 1 if i >= 4 and c > rows[i - 4][3] else 0
        buy9 = buy_setup == 9
        sell9 = sell_setup == 9

        if buy9:
            _add_level(resistances, max(r[1] for r in rows[i - 8 : i + 1]))
        if sell9:
            _add_level(supports, min(r[2] for r in rows[i - 8 : i + 1]))
        for r in resistances:
            if r.active and (c > r.price or l > r.price):
                r.active = False
        for s in supports:
            if s.active and (c < s.price or h < s.price):
                s.active = False
        resistance = _reported(resistances)
        support = _reported(supports)

        l2 = rows[i - 2][2] if i >= 2 else math.nan
        h2 = rows[i - 2][1] if i >= 2 else math.nan
        b_value, b_deferred = buy.step(buy9, sell9, resistance is not None, i >= 2 and c <= l2, l <= buy.eight_close, c)
        s_value, s_deferred = sell.step(sell9, buy9, support is not None, i >= 2 and c >= h2, h >= sell.eight_close, c)

        # Information only: perfection on the setup-9 bar, and price flips.
        buy_perfected = buy9 and min(rows[i - 1][2], l) < min(rows[i - 3][2], rows[i - 2][2])
        sell_perfected = sell9 and max(rows[i - 1][1], h) > max(rows[i - 3][1], rows[i - 2][1])
        bullish_flip = i >= 5 and rows[i - 1][3] < rows[i - 5][3] and c > rows[i - 4][3]
        bearish_flip = i >= 5 and rows[i - 1][3] > rows[i - 5][3] and c < rows[i - 4][3]

        out.append(
            TdBar(
                t=t,
                buy_setup=buy_setup,
                sell_setup=sell_setup,
                buy_countdown=b_value,
                sell_countdown=s_value,
                resistance=resistance,
                support=support,
                buy_deferred=b_deferred,
                sell_deferred=s_deferred,
                buy_perfected=buy_perfected,
                sell_perfected=sell_perfected,
                bullish_flip=bullish_flip,
                bearish_flip=bearish_flip,
            )
        )
    return out


def _last_where(result: List[TdBar], predicate: Any) -> Any:
    for record in reversed(result):
        if predicate(record):
            return record.t
    return None


def _countdown_state(value: int) -> Optional[CountdownState]:
    if value != 0 and abs(value) < 13:
        return CountdownState(count=abs(value), paused=value < 0)
    return None


def latest(result: List[TdBar]) -> Optional[Latest]:
    """Summary of the final bar of a `compute()` result, or None for an empty result."""
    if not result:
        return None
    last = result[-1]
    return Latest(
        t=last.t,
        buy_setup=last.buy_setup,
        sell_setup=last.sell_setup,
        buy_countdown=_countdown_state(last.buy_countdown),
        sell_countdown=_countdown_state(last.sell_countdown),
        buy_completed_13_now=last.buy_countdown == 13,
        sell_completed_13_now=last.sell_countdown == 13,
        last_buy_setup_9=_last_where(result, lambda r: r.buy_setup == 9),
        last_sell_setup_9=_last_where(result, lambda r: r.sell_setup == 9),
        last_buy_countdown_13=_last_where(result, lambda r: r.buy_countdown == 13),
        last_sell_countdown_13=_last_where(result, lambda r: r.sell_countdown == 13),
        resistance=last.resistance,
        support=last.support,
    )
