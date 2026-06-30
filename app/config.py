"""全域設定。從環境變數 / .env 讀取，密鑰不寫死在程式裡。"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 專案根目錄（這個檔的上上層）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 資料來源
    finmind_token: str = ""

    # 推播（M3 使用）
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Web 介面登入
    web_username: str = "admin"
    web_password: str = "change-me"

    # 資料存放位置。預設專案下的 data/；NAS Docker 會用環境變數 DATA_DIR=/app/data 覆寫。
    data_dir: Path = BASE_DIR / "data"

    timezone: str = "Asia/Taipei"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stock.sqlite"

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


settings = Settings()

# 確保資料夾存在（本機 = ./data，NAS = volume 掛載點）
settings.data_dir.mkdir(parents=True, exist_ok=True)
