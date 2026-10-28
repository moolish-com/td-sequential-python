import pytest

from td_sequential import compute

pd = pytest.importorskip("pandas")

from td_sequential.pandas import add_td_sequential  # noqa: E402


def frame(n=20):
    closes = [100 - i for i in range(n)]
    return pd.DataFrame(
        {"Open": closes, "High": [c + 0.5 for c in closes], "Low": [c - 0.5 for c in closes], "Close": closes},
        index=pd.date_range("2026-01-01", periods=n, freq="D"),
    )


def test_adds_columns_matching_compute_and_keeps_input_untouched():
    df = frame()
    out = add_td_sequential(df)
    assert list(df.columns) == ["Open", "High", "Low", "Close"]
    assert out["td_buy_setup"].iloc[12] == 9
    assert out["td_resistance"].iloc[12] == 96.5
    assert pd.isna(out["td_resistance"].iloc[11])
    assert pd.isna(out["td_support"].iloc[12])
    ref = compute(
        (i, o, h, l, c) for i, o, h, l, c in zip(df.index, df["Open"], df["High"], df["Low"], df["Close"])
    )
    assert list(out["td_buy_countdown"]) == [r.buy_countdown for r in ref]
    assert out.index.equals(df.index)


def test_prefix_and_missing_columns():
    out = add_td_sequential(frame().rename(columns=str.lower), prefix="tdx_")
    assert "tdx_sell_setup" in out.columns
    with pytest.raises(KeyError, match="close"):
        add_td_sequential(pd.DataFrame({"open": [1], "high": [1], "low": [1]}))
