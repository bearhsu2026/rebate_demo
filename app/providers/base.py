"""DataProvider 抽象介面。

上層（指標、選股、推播、UI）只依賴這個介面，不管資料是來自 FinMind 還是券商。
Phase 2 接券商即時報價時，只要新增一個實作此介面的類別即可，上層完全不用改。
"""

from abc import ABC, abstractmethod

import pandas as pd


class DataProvider(ABC):
    @abstractmethod
    def get_daily_price(self, code: str, start: str, end: str | None = None) -> pd.DataFrame:
        """日K（原始 OHLCV）。

        回傳欄位：date, open, high, low, close, volume（依 date 升冪）。
        """

    @abstractmethod
    def get_daily_price_adj(self, code: str, start: str, end: str | None = None) -> pd.DataFrame:
        """除權息還原日K。回傳欄位：date, close（adj），依 date 升冪。"""

    @abstractmethod
    def get_institutional(self, code: str, start: str, end: str | None = None) -> pd.DataFrame:
        """三大法人買賣超（股數，正買負賣）。

        回傳欄位：date, foreign_net, trust_net, dealer_net, total_net（依 date 升冪）。
        """
