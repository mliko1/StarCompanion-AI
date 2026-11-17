# -*- coding: utf-8 -*-
"""数据库引擎与会话（SQLAlchemy 2.x，SQLite）。

说明：
- 数据库文件固定为 data/xingban.db（规范 11 表）。
- check_same_thread=False：FastAPI 与后台线程共享连接所需。
- 原 server/db.py（原生 sqlite3）已备份为 server/db.py.bak，不再使用。
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "data", "xingban.db")

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：每次请求一个独立会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建表（只创建不存在的表），随后写入种子数据。"""
    from database import models  # noqa: F401  确保所有模型已注册到 Base
    from database import seed     # noqa: F401

    Base.metadata.create_all(bind=engine)
    seed.seed_all()
