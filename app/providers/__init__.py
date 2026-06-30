"""資料來源層。Phase 1 使用 FinMind（免費盤後）；Phase 2 可加入券商即時報價。"""

from .base import DataProvider
from .finmind import FinMindProvider

__all__ = ["DataProvider", "FinMindProvider"]
