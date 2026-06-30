"""命令列工具，方便本機開發時手動抓資料 / 看指標。

用法：
    python -m app.cli init                         建立資料表
    python -m app.cli ingest 2330 --start 2024-01-01
    python -m app.cli indicators 2330
    python -m app.cli counts
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from . import indicators
from .db import init_db
from .ingest import db_counts, ingest_all, load_prices


def _cmd_init(_: argparse.Namespace) -> None:
    init_db()
    print("資料表已建立。")


def _cmd_ingest(args: argparse.Namespace) -> None:
    init_db()
    start = args.start or (date.today() - timedelta(days=args.days)).isoformat()
    result = ingest_all(args.code, start, args.end)
    print(f"{args.code} 自 {start} 起：價格 {result['price']} 筆、法人 {result['institutional']} 筆。")


def _cmd_indicators(args: argparse.Namespace) -> None:
    init_db()
    df = load_prices(args.code)
    if df.empty:
        print(f"{args.code} 尚無資料，請先 ingest。")
        return
    close = df["adj_close"]
    macd_df = indicators.macd(close)
    print(f"{args.code} 最新 {df['date'].iloc[-1]}　收盤(還原) {close.iloc[-1]:.2f}")
    print(f"  MA5 {indicators.sma(close,5).iloc[-1]:.2f}  "
          f"MA20 {indicators.sma(close,20).iloc[-1]:.2f}  "
          f"MA60 {indicators.sma(close,60).iloc[-1]:.2f}")
    print(f"  MACD dif {macd_df['dif'].iloc[-1]:.3f}  dea {macd_df['dea'].iloc[-1]:.3f}  "
          f"RSI14 {indicators.rsi(close,14).iloc[-1]:.1f}")


def _cmd_counts(_: argparse.Namespace) -> None:
    init_db()
    print(db_counts())


def main() -> None:
    parser = argparse.ArgumentParser(description="台股追蹤系統 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="建立資料表").set_defaults(func=_cmd_init)

    p_ing = sub.add_parser("ingest", help="抓某檔股票價格+法人")
    p_ing.add_argument("code")
    p_ing.add_argument("--start", help="起始日 YYYY-MM-DD")
    p_ing.add_argument("--end", help="結束日 YYYY-MM-DD")
    p_ing.add_argument("--days", type=int, default=365, help="未給 start 時抓最近幾天（預設365）")
    p_ing.set_defaults(func=_cmd_ingest)

    p_ind = sub.add_parser("indicators", help="顯示最新指標")
    p_ind.add_argument("code")
    p_ind.set_defaults(func=_cmd_indicators)

    sub.add_parser("counts", help="顯示資料表筆數").set_defaults(func=_cmd_counts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
