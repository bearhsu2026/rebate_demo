"""指標單元測試（用固定序列，不需網路）。"""

import pandas as pd

from app import indicators


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    ma = indicators.sma(s, 3)
    assert pd.isna(ma.iloc[0]) and pd.isna(ma.iloc[1])
    assert ma.iloc[2] == 2.0  # (1+2+3)/3
    assert ma.iloc[4] == 4.0  # (3+4+5)/3


def test_rsi_all_gains_approaches_100():
    s = pd.Series(range(1, 40), dtype=float)  # 持續上漲
    r = indicators.rsi(s, 14)
    assert r.iloc[-1] > 99


def test_rsi_all_losses_approaches_0():
    s = pd.Series(range(40, 1, -1), dtype=float)  # 持續下跌
    r = indicators.rsi(s, 14)
    assert r.iloc[-1] < 1


def test_macd_shapes():
    s = pd.Series(range(1, 100), dtype=float)
    m = indicators.macd(s)
    assert list(m.columns) == ["dif", "dea", "hist"]
    assert len(m) == len(s)


def test_golden_and_death_cross():
    short = pd.Series([1, 2, 3, 4, 5], dtype=float)
    long = pd.Series([3, 3, 3, 3, 3], dtype=float)
    gc = indicators.crossover(short, long)
    dc = indicators.crossunder(short, long)
    # short 在 index 3 由 3->4 上穿 long(3) => index 3 為黃金交叉
    assert gc.iloc[3]
    assert not dc.any()
