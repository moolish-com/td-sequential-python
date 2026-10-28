"""Optional pandas helper. Install with `pip install td-sequential[pandas]`."""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from .core import TdBar, compute

__all__ = ["add_td_sequential"]

_COLUMNS = [f.name for f in fields(TdBar) if f.name != "t"]
_REQUIRED = ("open", "high", "low", "close")


def add_td_sequential(df: Any, prefix: str = "td_") -> Any:
    """Return a copy of `df` with the TD Sequential columns added.

    `df` needs `open`, `high`, `low` and `close` columns (case-insensitive), one
    closed bar per row, oldest first; the index is used as the bar time. Added
    columns are `<prefix>buy_setup`, `<prefix>sell_setup`, `<prefix>buy_countdown`,
    `<prefix>sell_countdown`, `<prefix>resistance`, `<prefix>support` (NaN when
    there is no active level), `<prefix>buy_deferred`, `<prefix>sell_deferred`,
    `<prefix>buy_perfected`, `<prefix>sell_perfected`, `<prefix>bullish_flip`
    and `<prefix>bearish_flip`.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError("add_td_sequential needs pandas: pip install td-sequential[pandas]") from exc

    lookup = {str(name).lower(): name for name in df.columns}
    missing = [name for name in _REQUIRED if name not in lookup]
    if missing:
        raise KeyError(f"DataFrame is missing column(s): {', '.join(missing)}")

    bars = (
        (idx, o, h, l, c)
        for idx, o, h, l, c in zip(df.index, *(df[lookup[name]] for name in _REQUIRED))
    )
    records = compute(bars)

    out = df.copy()
    for name in _COLUMNS:
        values = [getattr(r, name) for r in records]
        if name in ("resistance", "support"):
            out[prefix + name] = pd.Series(values, index=df.index, dtype="float64")
        else:
            out[prefix + name] = pd.Series(values, index=df.index)
    return out
