"""資料抓取與入庫。把 DataProvider 取得的資料 upsert 進 SQLite。"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import func, select

from .db import get_session
from .models import Institutional, PriceDaily, Stock
from .providers import DataProvider, FinMindProvider


def ensure_stock(code: str, name: str = "") -> None:
    with get_session() as s:
        obj = s.get(Stock, code)
        if obj is None:
            s.add(Stock(code=code, name=name))
        elif name and not obj.name:
            obj.name = name


def ingest_price(
    code: str, start: str, end: str | None = None, provider: DataProvider | None = None
) -> int:
    """抓日K（原始 OHLCV）+ 還原收盤價，合併後 upsert。回傳寫入筆數。"""
    provider = provider or FinMindProvider()
    raw = provider.get_daily_price(code, start, end)
    if raw.empty:
        return 0

    adj = provider.get_daily_price_adj(code, start, end)
    if not adj.empty:
        merged = raw.merge(adj.rename(columns={"close": "adj_close"}), on="date", how="left")
    else:
        merged = raw.assign(adj_close=raw["close"])
    # 還原價缺漏時退回用原始收盤價，確保指標一定有值
    merged["adj_close"] = merged["adj_close"].fillna(merged["close"])

    ensure_stock(code)
    with get_session() as s:
        for row in merged.itertuples(index=False):
            s.merge(
                PriceDaily(
                    date=row.date,
                    code=code,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    adj_close=float(row.adj_close),
                    volume=int(row.volume),
                )
            )
    return len(merged)


def ingest_institutional(
    code: str, start: str, end: str | None = None, provider: DataProvider | None = None
) -> int:
    """抓三大法人買賣超並 upsert。回傳寫入筆數。"""
    provider = provider or FinMindProvider()
    df = provider.get_institutional(code, start, end)
    if df.empty:
        return 0

    ensure_stock(code)
    with get_session() as s:
        for row in df.itertuples(index=False):
            s.merge(
                Institutional(
                    date=row.date,
                    code=code,
                    foreign_net=int(row.foreign_net),
                    trust_net=int(row.trust_net),
                    dealer_net=int(row.dealer_net),
                    total_net=int(row.total_net),
                )
            )
    return len(df)


def ingest_all(code: str, start: str, end: str | None = None) -> dict[str, int]:
    """一檔股票的價格 + 法人一起抓。"""
    provider = FinMindProvider()
    return {
        "price": ingest_price(code, start, end, provider),
        "institutional": ingest_institutional(code, start, end, provider),
    }


def load_prices(code: str) -> pd.DataFrame:
    """從 DB 讀出某股所有日K，依日期升冪，供指標運算使用。"""
    with get_session() as s:
        rows = s.execute(
            select(PriceDaily).where(PriceDaily.code == code).order_by(PriceDaily.date)
        ).scalars().all()
        # 在 session 仍開啟時就把值取出，避免 DetachedInstanceError
        records = [
            {
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "adj_close": r.adj_close,
                "volume": r.volume,
            }
            for r in rows
        ]
    return pd.DataFrame(records)


def db_counts() -> dict[str, int]:
    """各資料表筆數，供首頁/健康檢查顯示。"""
    with get_session() as s:
        return {
            "stocks": s.scalar(select(func.count()).select_from(Stock)) or 0,
            "price_rows": s.scalar(select(func.count()).select_from(PriceDaily)) or 0,
            "institutional_rows": s.scalar(select(func.count()).select_from(Institutional)) or 0,
        }
