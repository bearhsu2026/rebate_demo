# 台股追蹤 / 選股 / 模擬交易系統 — 開發 Spec

## Context（為什麼做、要解決什麼）

你想要一隻**台股追蹤與選股系統**：依自訂條件篩出股票、追蹤價格，預期會漲時主動推播提醒買進，偵測到可能下跌時提醒賣出或停損；同時提供**模擬下單**功能，假設照系統建議買賣，能算出平均成本、未實現/已實現損益，用來驗證「選股到底準不準」。

開發策略：**先在本機（Mac/PC）開發**，完成後**搬到 Synology NAS DS425+ 用 Docker 長期運行**。

關鍵現實限制（已查證，2026/06）：
- **三大法人買賣超是「盤後」資料**：證交所約每日 15:00 後才公布，免費資料源（FinMind）拿到的是當日/歷史收盤數字。**「盤中即時法人拋售」在免費階段做不到**，第一階段以「盤後 → 隔日提醒」為主。
- **真正的盤中 tick 即時報價需要券商帳戶**（永豐 Shioaji / 富果 Fugle）。免費的 FinMind / 證交所開放資料偏盤後或延遲。→ 所以採**兩階段**架構。
- **LINE Notify 已於 2025/03/31 終止**，推播改用 **Telegram Bot**（免費、無訊息量限制）。
- **DS425+ 規格**：Intel Celeron J4125（4 核、無 AVX 指令集）、預設 2GB RAM（最大 6GB）、x86 架構、支援 Docker（Container Manager）。→ 走**輕量路線**：SQLite、純 Python 指標運算、避開需要 AVX 或重編譯的套件。

現有 repo（`rebate_demo`）只有一支無關的 `index.html`（SWAG 博弈遊戲 UI 範本），本專案視為**全新開發**，不沿用該檔。

---

## 1. 目標與範圍（分兩階段）

| 階段 | 資料 | 提醒時機 | 需要券商帳戶 |
|---|---|---|---|
| **Phase 1（先做）** | FinMind / 證交所免費盤後資料（日K、技術指標、三大法人、基本面） | 每日盤後跑批 → 算出隔日買進候選 / 持股賣出建議 → 推播 | 否 |
| **Phase 2（之後）** | 接券商 API（Shioaji/Fugle）取盤中即時報價 | 盤中即時觸發買/賣提醒 | 是 |

架構上**資料來源做成抽象介面**（`DataProvider`），Phase 1 實作 `FinMindProvider`，Phase 2 只要新增 `ShioajiProvider` / `FugleProvider`，上層策略/提醒/UI 完全不用改。

非目標（明確排除）：真實下單（只做模擬）、保證獲利、投資建議（系統僅供研究，需顯示免責聲明）。

---

## 2. 技術棧（為 DS425+ 輕量化挑選）

- **語言**：Python 3.11+
- **資料來源**：[FinMind](https://github.com/FinMind/FinMind)（免費，註冊後 600 req/hr；提供日K、還原股價、三大法人、融資券、月營收、財報、EPS）
- **指標運算**：`pandas` + `pandas-ta`（純 Python，**不用 TA-Lib**，避免 NAS 上 C 編譯與 AVX 問題）
- **資料庫**：**SQLite**（單檔、零維運、2GB RAM 友善），ORM 用 SQLAlchemy / SQLModel
- **後端 / Web**：**FastAPI** + Uvicorn
- **前端**：Jinja2 server-render + **HTMX** + **Chart.js**（免前端打包、footprint 極小，最適合 NAS）
- **排程**：**APScheduler**（in-process，跟著容器跑，免依賴 Synology Task Scheduler）
- **推播**：Telegram Bot HTTP API（`httpx`）
- **部署**：Docker + docker-compose（`python:3.11-slim`，x86）
- **設定/密鑰**：`.env`（本機）/ Container Manager 環境變數（NAS），**絕不進 git**
- **測試**：pytest（指標、損益、策略以固定樣本資料驗證）

> 替代方案：UI 若想更快做出來可用 Streamlit，但記憶體較吃、且自訂彈性低 → 本 spec 採 FastAPI+HTMX 為主。

---

## 3. 系統架構（元件）

```
                ┌──────────────────────────────────────────────┐
排程 APScheduler │  每日盤後 Pipeline（18:00 Asia/Taipei）        │
   ───────────► │  1. 抓資料  2. 算指標  3. 選股  4. 持股檢查    │
                │  5. 產生訊號  6. 去重/冷卻  7. 推播            │
                └───────┬───────────────────────────┬──────────┘
                        │                           │
   DataProvider(抽象)   ▼                           ▼
   ├ FinMindProvider  ┌────────┐   StrategyEngine ┌──────────────┐
   └ ShioajiProvider  │ SQLite │◄──────────────── │ 技術/籌碼/基本 │
       (Phase 2)      │ 資料庫 │                  │ 面策略模組     │
                      └───┬────┘                  └──────────────┘
                          │
       ┌──────────────────┼───────────────────┬─────────────────┐
       ▼                  ▼                   ▼                 ▼
  PaperTrading      AlertDispatcher       FastAPI Web        Backtester
  (模擬下單/損益)    (Telegram 推播)       (Dashboard)       (歷史驗證)
```

核心模組：
1. **DataProvider 抽象層** — 統一介面：日K(還原)、即時報價、三大法人、基本面/EPS、市值/股本、大盤指數。
2. **Storage（SQLite）** — 見 §4 資料表。
3. **IndicatorEngine** — MA、MACD、RSI、KD、ADX、量能、52週高/低、相對強弱 RS。
4. **StrategyEngine** — 買進策略（§5）、賣出/停損策略（§6），參數可由設定檔/UI 調整。
5. **Screener** — 對 universe（全市場或自選池）跑買進策略 → 候選清單 + 評分。
6. **PaperTrading** — 模擬下單、加權平均成本、已/未實現損益、含台股交易成本（§7）。
7. **AlertDispatcher** — 訊息格式化 + 去重/冷卻 + Telegram 發送 + 發送紀錄。
8. **Backtester** — 用歷史資料回放策略，計算勝率/報酬/最大回檔（§8）。
9. **Web UI（FastAPI）** — §9 各頁面。
10. **Scheduler** — 每日 pipeline；Phase 2 加盤中輪詢。

---

## 4. 資料模型（SQLite 主要資料表）

- `stock`：股票代號、名稱、產業別、上市/上櫃、股本。
- `price_daily`：date, code, open/high/low/close, volume,**還原收盤價**（adj_close，除權息調整，算報酬/指標必用）。
- `institutional`：date, code, 外資/投信/自營商 買賣超張數、合計。
- `fundamental`：code, 季度, EPS, 年增率, ROE, 毛利率, 月營收 YoY, 本益比, 股價淨值比。
- `indicator_daily`（可選快取）：date, code, ma5/20/60, macd, rsi, kd, adx, rs_rank。
- `watchlist`：自選追蹤池（code, 加入原因, 加入日）。
- `screen_result`：date, code, strategy, score, 觸發條件明細(JSON)。
- `signal`：date, code, type(BUY/SELL/STOP), reason, price_ref, strategy。
- `paper_order`：模擬委託（datetime, code, side, qty, price, fee, tax, strategy, note）。
- `position`：持股（code, qty, **加權平均成本**, 首次買進日, 來源策略）。
- `trade_pnl`：每筆賣出的已實現損益（含成本、報酬率、持有天數）。
- `alert_log`：已發送提醒（去重/冷卻依據：code+type+date）。
- `settings`：策略參數、門檻、推播開關（可由 UI 改）。

---

## 5. 買進 / 選股條件（你提的 + 補強）

每檔候選給**綜合評分**（各條件加權，門檻可調），達標才推播。

**A. 技術面（基本盤）**
- **即將黃金交叉**：短均線（MA5/MA20）由下接近長均線（MA20/MA60），定義為
  (1) 兩線差距 < X%（如 1.5%）且短均線斜率向上，或 (2) 依斜率外推預估 N 日內交叉；
  另搭配 **MACD**（DIF 上穿 DEA）佐證。
- **近期漲幅趨勢（動能）**：收盤站上 MA20/MA60、近 20 日報酬 > X%、出現更高高點、RSI 在健康區（50–70）、ADX > 20（趨勢成形）。
- **量能配合**：突破/起漲日成交量 > 近 20 日均量 ×1.5（避免無量假突破）。

**B. 籌碼面（基本盤）**
- **三大法人連續買超**：近 N 日（如 3–5 日）合計淨買超 > 門檻，或單日淨買超占成交量比重高；外資+投信同步買超加分。
- **投信認養**：投信連續買超（CANSLIM 的法人贊助 "I" 概念）。

**C. 基本面 — 綜合 + 歐尼爾 CANSLIM（你選的）**
- **C** 當季 EPS 年增率 > 門檻（如 20%+）
- **A** 年度 EPS 成長、ROE 高
- **N** 創新高 / 新產品 / 創 52 週新高
- **S** 量價配合（已含於 A）
- **L** 相對強弱 RS（強勢股，報酬贏大盤前段）
- **I** 法人認養（已含於 B）
- **M** **大盤過濾（重要補充）**：大盤（加權指數）站上季線才積極選股，空頭盤減少買進訊號 → 避免逆勢進場。
- 通用價值/品質過濾：低本益比相對同業、低負債、穩定獲利（過濾地雷股）。

> 條件採「**必要 + 加分**」設計：技術面或籌碼面其一達標為必要，基本面/CANSLIM 為加分拉高評分與排序。

---

## 6. 賣出 / 停損條件（你提的 + 補強）

對**持股（position）**逐日（Phase 2 盤中）檢查：
- **獲利目標**：未實現報酬 > 目標 %（可調，如 +20%）→ 提醒分批/全出。
- **移動停利（補充）**：從持有期間高點回落 > X%（trailing stop）→ 鎖住獲利。
- **停損**：跌破成本 −X%（如 −8%，CANSLIM 紀律）或跌破關鍵支撐 → 提醒停損。
- **死亡交叉 / 空頭（你說的「空多」）**：短均線下穿長均線、MACD 死叉、收盤跌破 MA20/MA60。
- **三大法人轉賣超**：近 N 日由買轉賣超（Phase 1 為隔日訊號，Phase 2 用盤中逐筆推估）。
- **量價背離 / RSI 過熱回落（補充）**：創新高但量縮、RSI 從 >80 回落。
- **基本面惡化（補充）**：月營收 YoY 連續轉負、財報雷。

每個賣出訊號附當前報酬、距成本/高點幅度、觸發原因。

---

## 7. 模擬下單與損益模組（核心驗證功能）

- **模擬下單**：手動（UI 按「依建議買進/賣出」）或自動（依訊號自動建倉，可開關）。
- **成交價模型**：可設定「隔日開盤價」或「當日收盤價」成交（Phase 2 可用即時價）。
- **台股交易成本（重要補充，讓損益真實）**：
  - 手續費：成交額 × 0.1425%（買賣各收，可設折數）
  - 證交稅：**賣出**時成交額 × 0.3%
- **平均成本**：同一檔多次買進採**加權平均成本**；賣出後重算。
- **損益**：
  - 未實現損益 = (現價 − 平均成本) × 張數 − 預估賣出成本
  - 已實現損益 = 賣出淨額 − 對應成本（記入 `trade_pnl`）
- **選股準確度驗證（你的核心目的）**：
  - 每筆/每策略：勝率、平均報酬、平均持有天數、最大回檔、報酬 vs 大盤同期。
  - 依「來源策略」分組統計，看哪個條件組合最準。

---

## 8. 回測 / 歷史驗證模組（補充 — 不用等未來就能驗證選股準不準）

- 用 SQLite 既有歷史日K + 法人 + 基本面，**回放**過去 N 個月：每日套用買進策略產生模擬持倉，套用賣出/停損規則出場。
- 輸出：總報酬、勝率、最大回檔、夏普值（簡版）、與大盤對比、各策略貢獻。
- 與「forward paper trading」互補：回測快速驗證歷史、paper trading 驗證未來。

---

## 9. Telegram 推播

- 一個 Bot，買進候選/賣出提醒分開訊息格式（含代號、名稱、現價、觸發條件、評分、報酬）。
- **去重 + 冷卻（重要補充）**：同一 `code+type` 在 M 天內不重複推播，避免每日洗版。
- **錯誤告警**：pipeline 失敗、資料抓取異常也推給你（系統健康監控）。
- 設定（`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`）走環境變數。

---

## 10. Web UI 頁面（FastAPI + HTMX + Chart.js）

1. **Dashboard**：今日買進候選、持股賣出警示、總損益總覽、大盤狀態。
2. **選股結果**：候選清單 + 評分 + 觸發條件明細，可一鍵模擬買進。
3. **自選池 / Watchlist**：管理追蹤標的。
4. **個股頁**：K線圖 + 均線/MACD/法人買賣超疊圖。
5. **持股與損益**：持股、平均成本、未實現/已實現損益、報酬曲線。
6. **策略驗證 / 回測**：各策略勝率/報酬/與大盤對比圖表。
7. **設定**：策略門檻、推播開關、成交價模型、交易成本折數。
- **存取保護（補充）**：NAS 上會曝在區網，UI 加簡單認證（Basic Auth / 單一 token）。

---

## 11. 排程（APScheduler）

- **Phase 1**：每交易日 **18:00 Asia/Taipei** 跑完整 pipeline（確保價格與法人 EOD 都已公布）；可加 14:30 抓盤後價、15:40 補法人。
- **交易日曆（補充）**：跳過台股休市日（用資料源回傳的有資料日判斷，或維護休市表）。
- **Phase 2**：盤中（09:00–13:30）每 N 分鐘輪詢即時價檢查觸發。
- 失敗重試 + 指數退避 + 失敗推播告警。

---

## 12. 本機開發環境

- `python -m venv` + `requirements.txt`；`.env` 放 token；SQLite 檔在 `./data/`。
- `uvicorn app.main:app --reload` 起 Web；APScheduler 可用「手動觸發 pipeline」的 CLI/UI 按鈕方便除錯。
- 提供 `make dev` / `make pipeline` / `make test`。
- **與 NAS 環境一致**：本機也用 docker-compose 跑一份，確保 parity。

---

## 13. NAS DS425+ 部署

- **Dockerfile**：`python:3.11-slim`（x86），裝 `requirements.txt`；`numpy/pandas/pandas-ta` 在 J4125（無 AVX）可正常跑（pip wheel 為通用 x86-64）。
- **docker-compose.yml**：
  - service：app（FastAPI+APScheduler 同容器）
  - `volumes`：`./data:/app/data`（SQLite + 設定持久化在 NAS）
  - `environment`：Telegram token、認證密碼、`TZ=Asia/Taipei`
  - `restart: unless-stopped`
  - 記憶體限制（如 `mem_limit: 512m`，留資源給 DSM）
  - 對外 port（如 `8080:8000`），用 DSM 反向代理 + HTTPS（選配）
- **部署到 DSM**：Container Manager → 用 docker-compose（專案匯入）→ 啟動 → 瀏覽器連 `NAS-IP:8080`。
- **備份**：SQLite 檔放在 NAS volume，靠 Synology 快照 / Hyper Backup 備份。
- **資源注意**：J4125 偏弱，全市場掃描分批/加快取；避免並發重運算。

---

## 14. 安全 / 設定 / 免責（補充）

- 密鑰（Telegram、Phase 2 券商 API key）只走環境變數，`.gitignore` 排除 `.env`、`data/`。
- Web UI 加認證；NAS 對外建議走反向代理 + HTTPS，勿直接曝公網。
- 全站顯示**免責聲明**：本系統僅供研究與模擬，非投資建議，不保證獲利。
- 完整 logging + `/healthz` 健康檢查端點。

---

## 15. 建議專案結構

```
rebate_demo/
├─ app/
│  ├─ main.py                # FastAPI 入口 + 路由
│  ├─ config.py              # 設定/環境變數
│  ├─ db.py                  # SQLite/SQLAlchemy
│  ├─ models.py              # 資料表
│  ├─ providers/             # DataProvider 抽象 + FinMind(+Phase2 券商)
│  ├─ indicators.py          # MA/MACD/RSI/KD/ADX/RS
│  ├─ strategies/            # buy_*.py / sell_*.py / canslim.py
│  ├─ screener.py
│  ├─ paper_trading.py       # 下單/平均成本/損益/成本模型
│  ├─ backtester.py
│  ├─ alerts.py              # Telegram + 去重冷卻
│  ├─ scheduler.py           # APScheduler pipeline
│  ├─ templates/             # Jinja2 + HTMX
│  └─ static/                # Chart.js 等
├─ tests/                    # pytest（指標/損益/策略樣本驗證）
├─ data/                     # SQLite + 設定（git 忽略，NAS volume）
├─ requirements.txt
├─ Dockerfile
├─ docker-compose.yml
├─ .env.example
├─ Makefile
└─ README.md
```

---

## 16. 開發里程碑

1. **M1 骨架**：專案結構、SQLite、FinMindProvider、抓日K+法人入庫、指標運算。
2. **M2 選股**：技術/籌碼/CANSLIM 策略 + Screener + 評分 + 個股 K 線頁。
3. **M3 提醒**：訊號引擎 + Telegram 推播 + 去重冷卻 + 每日排程。
4. **M4 模擬交易**：模擬下單、加權平均成本、含成本損益、持股與損益頁。
5. **M5 驗證**：回測模組 + 策略勝率/報酬統計頁。
6. **M6 容器化部署**：Dockerfile + compose，本機驗證 → 搬上 DS425+ Container Manager。
7. **M7（Phase 2）**：接券商即時報價，盤中即時觸發。

---

## 17. 驗證方式（如何確認可動）

- **單元測試**：`pytest tests/` — 用固定樣本驗證指標數值、黃金/死亡交叉判定、加權平均成本與含稅費損益計算正確。
- **資料抓取**：跑一次 `make pipeline`，確認 SQLite 有當日價格/法人資料、無缺漏。
- **選股**：Dashboard 出現候選清單且觸發條件明細正確。
- **推播**：手動觸發一則測試訊號，Telegram 確實收到。
- **模擬交易**：模擬買一檔 → 隔日重算未實現損益 → 賣出後 `trade_pnl` 數字（含手續費 0.1425% / 證交稅 0.3%）正確。
- **回測**：對過去數月跑回測，輸出勝率/報酬/最大回檔，與大盤比對合理。
- **NAS**：在 DS425+ Container Manager 啟動容器，瀏覽器連入 Web、收到排程推播、重啟容器後資料仍在（volume 持久化）。

---

## 待你確認的細節（實作時可再調）
- 各門檻數值（漲幅 %、法人買超張數、停損 %、獲利目標 %）採可調設定，先給預設值。
- universe 範圍：先全市場掃描還是先用自選池起步（影響 NAS 運算量）。
- Phase 2 要接哪家券商（Shioaji / Fugle）視你開哪個帳戶再定。
