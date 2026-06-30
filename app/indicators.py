"""技術指標（純 pandas 實作，不依賴 TA-Lib / pandas-ta，避免 NAS 上 AVX / C 編譯問題）。

所有函式輸入皆為已依日期升冪排序的價格序列（pandas.Series），通常用還原收盤價 adj_close。
"""

from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    """簡單移動平均。"""
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    """指數移動平均。"""
    return close.ewm(span=period, adjust=False).mean()


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD。回傳 dif（快慢線差）、dea（訊號線）、hist（柱狀）。"""
    dif = ema(close, fast) - ema(close, slow)
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = dif - dea
    return pd.DataFrame({"dif": dif, "dea": dea, "hist": hist})


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI（Wilder 平滑）。"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def crossover(short: pd.Series, long: pd.Series) -> pd.Series:
    """黃金交叉：短線「今天 > 長線」且「昨天 <= 長線」。回傳布林序列。"""
    return (short > long) & (short.shift(1) <= long.shift(1))


def crossunder(short: pd.Series, long: pd.Series) -> pd.Series:
    """死亡交叉：短線「今天 < 長線」且「昨天 >= 長線」。回傳布林序列。"""
    return (short < long) & (short.shift(1) >= long.shift(1))
