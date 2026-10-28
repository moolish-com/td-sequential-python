# TD Sequential indicator for Python

[![test](https://github.com/moolish-com/td-sequential-python/actions/workflows/test.yml/badge.svg)](https://github.com/moolish-com/td-sequential-python/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/td-sequential.svg)](https://pypi.org/project/td-sequential/)
[![Python](https://img.shields.io/pypi/pyversions/td-sequential.svg)](https://pypi.org/project/td-sequential/)
[![Downloads](https://img.shields.io/pypi/dm/td-sequential.svg)](https://pypi.org/project/td-sequential/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`td-sequential` computes the TD Sequential indicator in Python on a list of OHLC candles: the TD Setup (the 1 to 9 count, often called TD9), the TD Countdown (1 to 13), the TDST support and resistance levels left by completed setups, and the information-only perfection and price flip flags. It works on crypto, stocks and forex candles of any timeframe, has no dependencies, supports Python 3.9 and later, and has an optional pandas helper.

It follows the plain-English rules in [SPEC.md](SPEC.md) and matches the reference output bar for bar. The free [TD Sequential counter](https://moolish.com/tools/td-sequential-counter/) on moolish.com shows the current count on a crypto pair without installing anything.

## Install

```bash
pip install td-sequential
pip install "td-sequential[pandas]"   # optional DataFrame helper
```

## Usage

```python
from td_sequential import compute, latest

# Closed bars only, oldest first. Drop the candle that is still forming.
bars = [
    {"t": 1750032000000, "o": 105594.02, "h": 108952.38, "l": 104980.37, "c": 106794.53},
    # ...
]

result = compute(bars)   # one TdBar record per input bar
now = latest(result)     # summary of the last bar

last = result[-1]
if last.buy_setup == 9:
    print("TD Setup 9 (buy) on", last.t, "resistance", last.resistance)
if last.sell_countdown == 13:
    print("TD Countdown 13 (sell) completed on", last.t)
```

A bar can be a dict with keys `t, o, h, l, c` (the long names `time, open, high, low, close` also work), a `(t, o, h, l, c)` tuple, or any object with those attributes, for example a named tuple or a dataclass. Missing fields and non-numeric prices raise a clear `ValueError` or `TypeError` that names the bar.

### pandas

```python
import pandas as pd
from td_sequential.pandas import add_td_sequential

df = pd.read_csv("btcusdt-1d.csv", index_col="time", parse_dates=True)  # open, high, low, close columns
out = add_td_sequential(df)   # returns a copy with td_* columns added
print(out[out["td_buy_setup"] == 9])
```

Column names are case-insensitive on input. Output columns carry the prefix `td_` (change it with `prefix=`). `td_resistance` and `td_support` are `NaN` when there is no active level.

## Output fields

`compute()` returns a list of frozen `TdBar` dataclasses, one per input bar, in input order.

| Field | Type | Meaning |
|---|---|---|
| `t` | any | The bar's timestamp, copied from the input |
| `buy_setup` | int | Buy TD Setup counter (0 or more; exactly 9 marks a setup 9) |
| `sell_setup` | int | Sell TD Setup counter, same meaning |
| `buy_countdown` | int | Signed buy countdown; 13 means just completed; 14 or more means no countdown in progress; negative means paused |
| `sell_countdown` | int | Signed sell countdown, same meaning |
| `resistance` | float or None | Price of the active latest TDST resistance level (plain highest high of the 9 setup bars) |
| `support` | float or None | Price of the active latest TDST support level (plain lowest low of the 9 setup bars) |
| `buy_deferred` | bool | The 13th buy countdown bar was held back by the 13-versus-8 test |
| `sell_deferred` | bool | Same for the sell countdown |
| `buy_perfected` | bool | Buy setup 9 whose bar 8 or 9 low is strictly below the lows of bars 6 and 7 (information only) |
| `sell_perfected` | bool | Sell setup 9 whose bar 8 or 9 high is strictly above the highs of bars 6 and 7 (information only) |
| `bullish_flip` | bool | Price flip: close crosses above the close 4 bars earlier after being below it (information only) |
| `bearish_flip` | bool | The mirror price flip (information only) |

The four information-only fields never change a setup, countdown or level value.

`latest(result)` returns a `Latest` dataclass: the current setup counts, the countdown in progress per side (`CountdownState(count, paused)` or `None`), whether a 13 just completed, the time of the last completed setup 9 and countdown 13 per side, and the active resistance and support. It returns `None` for an empty result.

## Rules in short

- Setup: a bar counts when its close is lower (buy) or higher (sell) than the close 4 bars earlier. Any bar that does not qualify resets the counter to 0. Counting does not stop at 9.
- Levels: a buy setup 9 records the highest high of its 9 bars as resistance, a sell setup 9 the lowest low as support (the "TDST levels", using the plain 9-bar high and low). A level is dropped when price closes beyond it or a whole bar sits beyond it.
- Countdown: starts on the setup 9 bar; a bar counts when its close is at or beyond the low (buy) or high (sell) of the bar 2 bars earlier. It needs an active level, is cancelled by the opposite setup 9, and the 13th bar must pass the 13-versus-8 test.

The full, unambiguous version is in [SPEC.md](SPEC.md).

## Verified against reference data

The test suite replays eight real candle histories (crypto pairs on 4-hour, daily and weekly timeframes, about 500 bars each) and requires every counting field to match the stored reference output on every bar. It also compares all twelve fields with the JavaScript implementation of the same rules on the same bars, and has unit cases for setup, levels, countdown, the 13-versus-8 deferral, perfection and price flips. Run it with `pip install -e ".[test]"` then `pytest`.

## What is TD Sequential?

TD Sequential is Tom DeMark's method for spotting a stretched run of closes. A TD Setup counts consecutive bars that close beyond the close four bars earlier, and a completed 9 can start a countdown that needs 13 qualifying bars. A 9 or a 13 describes past prices and gives no direction on its own; the [TD Sequential guide](https://moolish.com/learn/td-sequential/) explains the method, [TDST](https://moolish.com/learn/td-sequential/tdst/) and [perfected setups](https://moolish.com/learn/td-sequential/perfected-setup/).

## Related

- [td-sequential](https://github.com/moolish-com/td-sequential) - JavaScript and TypeScript (npm)
- [td-sequential-pine-script](https://github.com/moolish-com/td-sequential-pine-script) - TradingView Pine Script v6
- [td-sequential-screener](https://github.com/moolish-com/td-sequential-screener) - command-line screener
- [Free TD Sequential counter](https://moolish.com/tools/td-sequential-counter/) - check a crypto pair in the browser

## Attribution and disclaimer

Moolish is not affiliated with, endorsed by or sponsored by Tom DeMark or DeMARK Analytics. TD Sequential is a method created by Tom DeMark, and DeMARK is a trademark of DeMARK Analytics.

This is educational software, not financial advice. A count describes past prices; it is not a prediction.

## Licence

[MIT](LICENSE) - Copyright (c) 2026 Moolish
