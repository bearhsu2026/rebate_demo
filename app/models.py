"""資料表定義（M1 核心：股票清單、日K、三大法人）。

之後里程碑會再加入：fundamental / signal / paper_order / position / trade_pnl / alert_log。
"""

from datetime import date as date_type

from sqlalchemy import BigInteger, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Stock(Base):
    """股票基本資料。"""

    __tablename__ = "stock"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), default="")
    industry: Mapped[str] = mapped_column(String(50), default="")
    market: Mapped[str] = mapped_column(String(10), default="")  # TWSE / TPEX


class PriceDaily(Base):
    """日K。close 為原始收盤價；adj_close 為除權息還原價（算指標/報酬用）。"""

    __tablename__ = "price_daily"

    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    open: Mapped[float] = mapped_column(Float, default=0.0)
    high: Mapped[float] = mapped_column(Float, default=0.0)
    low: Mapped[float] = mapped_column(Float, default=0.0)
    close: Mapped[float] = mapped_column(Float, default=0.0)
    adj_close: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)  # 股數


class Institutional(Base):
    """三大法人買賣超（盤後資料），單位為股數，正=買超、負=賣超。"""

    __tablename__ = "institutional"

    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    foreign_net: Mapped[int] = mapped_column(BigInteger, default=0)  # 外資
    trust_net: Mapped[int] = mapped_column(BigInteger, default=0)    # 投信
    dealer_net: Mapped[int] = mapped_column(BigInteger, default=0)   # 自營商
    total_net: Mapped[int] = mapped_column(BigInteger, default=0)    # 合計
