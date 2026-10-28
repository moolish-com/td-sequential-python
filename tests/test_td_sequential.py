import dataclasses
from types import SimpleNamespace

import pytest

from td_sequential import CountdownState, TdBar, compute, latest

FIELDS = [
    "t", "buy_setup", "sell_setup", "buy_countdown", "sell_countdown",
    "resistance", "support", "buy_deferred", "sell_deferred",
    "buy_perfected", "sell_perfected", "bullish_flip", "bearish_flip",
]


def bars(closes):
    """Bars from closes: open = close, high = close + 0.5, low = close - 0.5."""
    return [{"t": 1000 * (i + 1), "o": c, "h": c + 0.5, "l": c - 0.5, "c": c} for i, c in enumerate(closes)]


def falling(n, start=100):
    return [start - i for i in range(n)]


def col(res, key):
    return [getattr(r, key) for r in res]


def test_setup_needs_4_earlier_bars_counts_without_cap_and_equal_closes_reset():
    r = compute(bars(falling(15)))
    assert col(r, "buy_setup")[:6] == [0, 0, 0, 0, 1, 2]
    assert r[12].buy_setup == 9
    assert r[13].buy_setup == 10
    assert r[14].buy_setup == 11
    assert all(x.sell_setup == 0 for x in r)

    flat = compute(bars([10, 10, 10, 10, 9, 9, 9, 9, 9, 9]))
    assert col(flat, "buy_setup") == [0, 0, 0, 0, 1, 2, 3, 4, 0, 0]
    assert all(x.sell_setup == 0 for x in flat)


def test_setup_non_qualifying_bar_resets_counter():
    r = compute(bars([10, 10, 10, 10, 9, 8, 7, 20, 6, 5]))
    assert col(r, "buy_setup") == [0, 0, 0, 0, 1, 2, 3, 0, 1, 2]
    assert r[7].sell_setup == 1


def test_sell_setup_mirrors_buy_setup():
    r = compute(bars([200 - c for c in falling(15)]))
    assert r[12].sell_setup == 9
    assert r[13].sell_setup == 10
    assert all(x.buy_setup == 0 for x in r)


def test_buy_9_adds_resistance_and_sell_9_adds_support():
    r = compute(bars(falling(14)))
    assert r[11].resistance is None
    assert r[12].resistance == 96.5
    assert r[13].resistance == 96.5
    assert all(x.support is None for x in r)

    s = compute(bars([200 - c for c in falling(14)]))
    assert s[12].support == 103.5
    assert all(x.resistance is None for x in s)


def test_resistance_breaks_when_close_or_whole_bar_goes_above_it():
    base = falling(13)
    by_close = compute(bars(base) + [{"t": 99, "o": 90, "h": 98, "l": 88, "c": 97}])
    assert by_close[13].resistance is None
    by_low = compute(bars(base) + [{"t": 99, "o": 97, "h": 98, "l": 96.75, "c": 96.5}])
    assert by_low[13].resistance is None
    touch = compute(bars(base) + [{"t": 99, "o": 90, "h": 97.5, "l": 88, "c": 95}])
    assert touch[13].resistance == 96.5


def test_countdown_is_idle_until_setup_9_and_level_exist():
    r = compute(bars([5, 6, 7, 8, 9, 10]))
    assert all(x.buy_countdown == 14 and x.sell_countdown == 14 for x in r)


def test_countdown_starts_on_setup_9_and_completes_at_13_on_non_consecutive_bars():
    r = compute(bars(falling(27)))
    assert r[12].buy_countdown == 1
    assert r[13].buy_countdown == 2
    assert r[24].buy_countdown == 13
    assert r[25].buy_countdown == 14
    assert r[26].buy_countdown == 15

    closes = falling(14)
    closes += [closes[12] + 5, 70]
    p = compute(bars(closes))
    assert p[13].buy_countdown == 2
    assert p[14].buy_countdown == -2
    assert p[15].buy_countdown == 3


def test_countdown_cancelled_when_opposite_setup_9_completes():
    closes = falling(13) + [85 + 5 * i for i in range(14)]
    b = bars(closes)
    r = compute(b)
    s9 = next(i for i, x in enumerate(r) if x.sell_setup == 9)
    assert s9 > 13
    assert r[s9].buy_countdown == 14
    assert r[s9].sell_countdown in (0, 1)
    assert r[s9].support == b[s9 - 8]["l"]


def test_countdown_cancelled_when_its_level_breaks():
    r = compute(bars(falling(13) + [99, 98]))
    assert r[12].buy_countdown == 1
    assert r[13].buy_countdown == 14
    assert r[14].buy_countdown == 14


def deferral_series(at24):
    b = bars(falling(24))
    b.append(at24)
    b.append({"t": 26000, "o": 70, "h": 70.5, "l": 69.5, "c": 70})
    return b


AT24 = {"t": 25000, "o": 80, "h": 90, "l": 85, "c": 77}


def test_13_versus_8_defers_when_low_is_above_close_of_count_8():
    r = compute(deferral_series(AT24))
    assert r[19].buy_countdown == 8
    assert r[23].buy_countdown == 12
    assert r[24].buy_countdown == -12
    assert r[24].buy_deferred is True
    assert r[25].buy_countdown == 13
    assert r[25].buy_deferred is False


def test_13_versus_8_sell_side_is_the_mirror_image():
    mirror = [
        {"t": x["t"], "o": 200 - x["o"], "h": 200 - x["l"], "l": 200 - x["h"], "c": 200 - x["c"]}
        for x in deferral_series(AT24)
    ]
    r = compute(mirror)
    assert r[24].sell_countdown == -12
    assert r[24].sell_deferred is True
    assert r[25].sell_countdown == 13
    assert all(x.buy_countdown == 14 for x in r)


def test_new_own_setup_9_restarts_the_countdown():
    closes = falling(14) + [120 - i for i in range(14)]
    r = compute(bars(closes))
    nines = [i for i, x in enumerate(r) if x.buy_setup == 9]
    assert len(nines) == 2
    assert r[nines[1]].buy_countdown in (0, 1)


def test_output_carries_timestamp_and_exact_contract_fields():
    r = compute(bars([1, 2, 3]))
    assert [f.name for f in dataclasses.fields(r[0])] == FIELDS
    assert col(r, "t") == [1000, 2000, 3000]
    assert compute([]) == []


def test_latest_summarises_final_bar():
    assert latest([]) is None
    s = latest(compute(bars(falling(20))))
    assert s.t == 20000
    assert s.buy_setup == 16
    assert s.last_buy_setup_9 == 13000
    assert s.last_sell_setup_9 is None
    assert s.resistance == 96.5
    assert s.buy_countdown == CountdownState(count=8, paused=False)
    assert s.sell_countdown is None
    assert s.last_buy_countdown_13 is None

    done = latest(compute(bars(falling(25))))
    assert done.buy_completed_13_now is True
    assert done.last_buy_countdown_13 == 25000
    assert done.buy_countdown is None


def test_perfection_buy_9_perfected_when_bar_8_or_9_undercuts_bars_6_and_7():
    inp = bars([100, 100, 100, 100] + falling(9, 99))
    r = compute(inp)
    nine = next(i for i, x in enumerate(r) if x.buy_setup == 9)
    assert r[nine].buy_perfected is True
    flat = [
        {**b, "l": inp[nine - 3]["l"] + 5, "h": b["h"] + 6} if nine - 1 <= i <= nine else b
        for i, b in enumerate(inp)
    ]
    r2 = compute(flat)
    assert r2[nine].buy_setup == 9
    assert r2[nine].buy_perfected is False
    assert all(i == nine or not x.buy_perfected for i, x in enumerate(r))


def test_perfection_sell_side_mirrors():
    inp = bars([100, 100, 100, 100] + [100 + 1 + i for i in range(9)])
    r = compute(inp)
    nine = next(i for i, x in enumerate(r) if x.sell_setup == 9)
    assert r[nine].sell_perfected is True
    assert not any(x.buy_perfected for x in r)


def test_price_flips_mark_change_of_side():
    r = compute(bars([10, 10, 10, 10, 10, 11, 9, 8, 7, 6]))
    assert r[6].bearish_flip is True
    assert r[6].bullish_flip is False
    up = compute(bars([10, 10, 10, 10, 10, 9, 11, 12]))
    assert up[6].bullish_flip is True


# --- input handling -------------------------------------------------------

def test_accepts_tuples_dicts_long_names_objects_and_generators():
    ref = compute(bars(falling(15)))
    as_tuples = [(b["t"], b["o"], b["h"], b["l"], b["c"]) for b in bars(falling(15))]
    assert compute(as_tuples) == ref
    long_names = [{"time": b["t"], "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"]} for b in bars(falling(15))]
    assert compute(long_names) == ref
    objects = [SimpleNamespace(**b) for b in bars(falling(15))]
    assert compute(objects) == ref
    assert compute(iter(bars(falling(15)))) == ref


def test_rejects_malformed_bars():
    with pytest.raises(ValueError, match="bar 1: missing field 'h'"):
        compute([{"t": 1, "o": 1, "h": 1, "l": 1, "c": 1}, {"t": 2, "o": 1, "l": 1, "c": 1}])
    with pytest.raises(ValueError, match=r"must be \(t, o, h, l, c\)"):
        compute([(1, 2, 3)])
    with pytest.raises(TypeError, match="bar 0: 'c' must be a number"):
        compute([{"t": 1, "o": 1, "h": 1, "l": 1, "c": "x"}])
    with pytest.raises(ValueError, match="NaN"):
        compute([{"t": 1, "o": 1, "h": 1, "l": 1, "c": float("nan")}])


def test_records_are_immutable_tdbar_instances():
    r = compute(bars([1, 2]))
    assert isinstance(r[0], TdBar)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r[0].buy_setup = 5  # type: ignore[misc]
