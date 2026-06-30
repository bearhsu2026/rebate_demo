"""FinMind 資料來源（直接打 v4 REST API，不依賴 FinMind 套件，footprint 最小、最適合 NAS）。

API 文件：https://finmind.github.io/
免費註冊取得 token 後流量上限較高（約 600 req/hr）。
"""

from __future__ import annotations

import httpx
import pandas as pd

from ..config import settings
from .base import DataProvider

API_URL = "https://api.finmindtrade.com/api/v4/data"


class FinMindProvider(DataProvider):
    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self.token = token if token is not None else settings.finmind_token
        self.timeout = timeout

    def _query(self, dataset: str, code: str, start: str, end: str | None) -> pd.DataFrame:
        params = {
            "dataset": dataset,
            "data_id": code,
            "start_date": start,
        }
        if end:
            params["end_date"] = end
        if self.token:
            params["token"] = self.token

        resp = httpx.get(API_URL, params=params, timeout=self.timeout)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != 200:
            raise RuntimeError(f"FinMind API 錯誤 ({dataset} {code}): {payload.get('msg')}")
        data = payload.get("data", [])
        return pd.DataFrame(data)

    def get_daily_price(self, code: str, start: str, end: str | None = None) -> pd.DataFrame:
        df = self._query("TaiwanStockPrice", code, start, end)
        if df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["date"]).dt.date,
                "open": df["open"].astype(float),
                "high": df["max"].astype(float),
                "low": df["min"].astype(float),
                "close": df["close"].astype(float),
                "volume": df["Trading_Volume"].astype("int64"),
            }
        )
        return out.sort_values("date").reset_index(drop=True)

    def get_daily_price_adj(self, code: str, start: str, end: str | None = None) -> pd.DataFrame:
        df = self._query("TaiwanStockPriceAdj", code, start, end)
        if df.empty:
            return pd.DataFrame(columns=["date", "close"])
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["date"]).dt.date,
                "close": df["close"].astype(float),
            }
        )
        return out.sort_values("date").reset_index(drop=True)

    def get_institutional(self, code: str, start: str, end: str | None = None) -> pd.DataFrame:
        df = self._query("TaiwanStockInstitutionalInvestorsBuySell", code, start, end)
        cols = ["date", "foreign_net", "trust_net", "dealer_net", "total_net"]
        if df.empty:
            return pd.DataFrame(columns=cols)

        df["net"] = df["buy"].astype("int64") - df["sell"].astype("int64")
        df["date"] = pd.to_datetime(df["date"]).dt.date

        # name 例：Foreign_Investor / Investment_Trust / Dealer_self / Dealer_Hedging ...
        def bucket(name: str) -> str:
            n = name.lower()
            if "foreign" in n:
                return "foreign_net"
            if "trust" in n:
                return "trust_net"
            if "dealer" in n:
                return "dealer_net"
            return "other"

        df["bucket"] = df["name"].map(bucket)
        pivot = (
            df.pivot_table(index="date", columns="bucket", values="net", aggfunc="sum")
            .reset_index()
        )
        for c in ["foreign_net", "trust_net", "dealer_net"]:
            if c not in pivot.columns:
                pivot[c] = 0
        pivot["total_net"] = (
            pivot["foreign_net"].fillna(0)
            + pivot["trust_net"].fillna(0)
            + pivot["dealer_net"].fillna(0)
        )
        out = pivot[cols].fillna(0)
        for c in cols[1:]:
            out[c] = out[c].astype("int64")
        return out.sort_values("date").reset_index(drop=True)
