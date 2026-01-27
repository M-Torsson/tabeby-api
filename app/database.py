# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in .env file")

WEB_CONCURRENCY = int(os.getenv("WEB_CONCURRENCY", "4"))
CONNECTIONS_PER_WORKER = 12
POOL_SIZE = min(WEB_CONCURRENCY * CONNECTIONS_PER_WORKER, 60)
MAX_OVERFLOW = min(POOL_SIZE * 3, 180)

engine = create_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_reset_on_return='rollback',
    echo=False,
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "connect_timeout": 10,
    } if "postgresql" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

def check_database_connection():
    """التحقق من الاتصال بقاعدة البيانات"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

def dispose_engine():
    """إغلاق جميع الاتصالات عند إيقاف التطبيق"""
    try:
        engine.dispose()
    except Exception:
        pass

def get_pool_stats():
    """الحصول على إحصائيات Connection Pool"""
    try:
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_capacity": POOL_SIZE + MAX_OVERFLOW
        }
    except Exception:
        return {}
