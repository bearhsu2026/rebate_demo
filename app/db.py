"""SQLite 連線與 session 管理。資料庫檔固定落在 settings.data_dir（本機/NAS 皆同）。"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(
    settings.db_url,
    # SQLite + FastAPI/排程多執行緒共用時需要
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """建立所有資料表（若不存在）。"""
    from . import models  # noqa: F401  確保 model 被載入註冊

    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Iterator[Session]:
    """以 context manager 取得 session，結束自動 commit / rollback / close。"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
