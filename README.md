# 台股追蹤 / 選股 / 模擬交易系統

依自訂條件篩選台股、追蹤價格、預期上漲時推播提醒買進、可能下跌時提醒賣出/停損，並提供**模擬下單**與損益計算，用來驗證選股準度。完整規格見 [`SPEC.md`](./SPEC.md)。

> ⚠️ 本系統僅供研究與模擬，非投資建議，不保證獲利。

開發策略：**先在本機（Windows）開發 → 之後搬到 Synology NAS DS425+ 用 Docker 運行**。
所有股價資料、SQLite 資料庫、密鑰都存在本機 `data/` / `.env`，**不會上 GitHub**。

---

## 目前進度

**M1 骨架（已完成）**：SQLite 資料庫、FinMind 資料抓取（日K+還原價+三大法人）、技術指標（MA/MACD/RSI/交叉判定）、FastAPI 骨架、CLI、單元測試、Docker 部署檔。

後續里程碑（M2 選股 → M3 推播 → M4 模擬交易 → M5 回測 → M6 上 NAS → M7 券商即時）見 `SPEC.md`。

---

## 在自己的 Windows 電腦上開發

把專案放到 `D:\副業\claude`：

```powershell
# 1. 取得程式碼（擇一）
git clone <你的 repo 網址> "D:\副業\claude"
cd D:\副業\claude
git checkout claude/taiwan-stock-tracker-spec-c53q4d

# 2. 建立虛擬環境並安裝套件
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. 設定（複製範本後填入 FinMind token，可先留空測試）
copy .env.example .env

# 4. 抓一檔測試（台積電 2330），資料會寫進 D:\副業\claude\data\stock.sqlite
python -m app.cli ingest 2330 --start 2024-01-01
python -m app.cli indicators 2330

# 5. 啟動 Web（瀏覽器開 http://127.0.0.1:8000）
uvicorn app.main:app --reload
```

> FinMind token：到 <https://finmindtrade.com> 免費註冊取得，填進 `.env` 的 `FINMIND_TOKEN`，可提高流量上限。

### 跑測試

```powershell
pytest -q
```

---

## 資料存在哪

| 內容 | 位置（本機） | 上 GitHub？ |
|---|---|---|
| SQLite 資料庫、股價/法人資料 | `D:\副業\claude\data\stock.sqlite` | ❌（`.gitignore` 擋下） |
| 密鑰（FinMind/Telegram token） | `D:\副業\claude\.env` | ❌ |
| 程式碼、規格、`.env.example` | repo | ✅ |

搬到 NAS 後，`data/` 會對應到 NAS 上的持久化 volume（見下）。

---

## 之後搬到 Synology DS425+（M6）

DS425+ 為 x86（Intel J4125），支援 Container Manager（Docker）。

1. 把整個專案放到 NAS（例如 `/volume1/docker/stock-tracker/`）。
2. 在該資料夾放好 `.env`（填入正式 token）。
3. Container Manager → 專案 → 用 `docker-compose.yml` 建立並啟動。
4. 瀏覽器連 `http://<NAS-IP>:8080`。
5. 資料持久化在 NAS 的 `./data`，靠 Synology 快照 / Hyper Backup 備份。

本機也可用 Docker 先驗證一致性：

```powershell
docker compose up -d --build   # 連 http://127.0.0.1:8080
```

---

## 專案結構

```
app/
├─ config.py        設定（讀 .env / 環境變數）
├─ db.py            SQLite 連線
├─ models.py        資料表（stock / price_daily / institutional）
├─ providers/       資料來源抽象 + FinMind（Phase 2 可加券商）
├─ indicators.py    MA / MACD / RSI / 黃金死亡交叉
├─ ingest.py        抓取與入庫
├─ main.py          FastAPI（/healthz, /, /api/...）
└─ cli.py           命令列工具
tests/              單元測試
data/               SQLite 與資料（本機，不進 git）
Dockerfile / docker-compose.yml   NAS 部署
SPEC.md             完整開發規格
```
