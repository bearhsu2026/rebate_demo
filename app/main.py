"""FastAPI 入口（M1 骨架）。

提供：
- GET  /healthz        健康檢查（NAS / Docker 監控用）
- GET  /               簡易狀態頁（資料表筆數 + 操作說明）
- POST /api/ingest/{code}  手動抓某檔股票資料（方便開發測試）
- GET  /api/indicators/{code}  回傳近期均線/MACD/RSI（驗證指標運算）

完整 Web UI（選股清單、K線圖、損益、回測）會在後續里程碑加入。
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from . import __version__, indicators
from .db import init_db
from .ingest import db_counts, ingest_all, load_prices

app = FastAPI(title="台股追蹤系統", version=__version__)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    c = db_counts()
    return f"""
    <html lang="zh-TW"><head><meta charset="utf-8"><title>台股追蹤系統</title>
    <style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;line-height:1.6}}
    code{{background:#f0f0f0;padding:2px 6px;border-radius:4px}}
    .card{{border:1px solid #ddd;border-radius:8px;padding:16px;margin:12px 0}}</style></head>
    <body>
    <h1>台股追蹤系統 <small>v{__version__}</small></h1>
    <div class="card">
      <b>目前資料庫</b><br>
      股票數：{c['stocks']}　日K筆數：{c['price_rows']}　法人筆數：{c['institutional_rows']}
    </div>
    <div class="card">
      <b>快速測試（M1）</b>
      <ul>
        <li>抓資料：<code>POST /api/ingest/2330</code></li>
        <li>看指標：<code>GET /api/indicators/2330</code></li>
        <li>健康檢查：<code>GET /healthz</code></li>
      </ul>
    </div>
    <p style="color:#888">⚠️ 本系統僅供研究與模擬，非投資建議，不保證獲利。</p>
    </body></html>
    """


@app.post("/api/ingest/{code}")
def api_ingest(code: str, days: int = 365) -> dict:
    """抓最近 days 天的價格與法人資料入庫。"""
    start = (date.today() - timedelta(days=days)).isoformat()
    try:
        result = ingest_all(code, start)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"抓取失敗：{exc}") from exc
    return {"code": code, "start": start, **result}


@app.get("/api/indicators/{code}")
def api_indicators(code: str) -> dict:
    """回傳最新一日的 MA5/20/60、MACD、RSI（用還原收盤價）。"""
    df = load_prices(code)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"{code} 尚無資料，請先 POST /api/ingest/{code}")

    close = df["adj_close"]
    macd_df = indicators.macd(close)
    latest = {
        "date": str(df["date"].iloc[-1]),
        "close": round(float(close.iloc[-1]), 2),
        "ma5": _safe(indicators.sma(close, 5)),
        "ma20": _safe(indicators.sma(close, 20)),
        "ma60": _safe(indicators.sma(close, 60)),
        "macd_dif": _safe(macd_df["dif"]),
        "macd_dea": _safe(macd_df["dea"]),
        "rsi14": _safe(indicators.rsi(close, 14)),
    }
    return {"code": code, "rows": len(df), "latest": latest}


def _safe(series) -> float | None:
    val = series.iloc[-1]
    return None if val != val else round(float(val), 2)  # NaN 檢查
