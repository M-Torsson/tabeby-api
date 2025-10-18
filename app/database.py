import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# تحميل المتغيرات من ملف .env (اسمح بالكتابة فوق متغيرات البيئة الحالية)
load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

# إن كان الرابط يستخدم postgresql بدون تحديد السائق، فعَّل psycopg3 تلقائياً
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in .env file")

# حساب Pool Size الديناميكي بناءً على عدد Workers
WEB_CONCURRENCY = int(os.getenv("WEB_CONCURRENCY", "4"))
CONNECTIONS_PER_WORKER = 12
POOL_SIZE = min(WEB_CONCURRENCY * CONNECTIONS_PER_WORKER, 60)
MAX_OVERFLOW = min(POOL_SIZE * 3, 180)

# إنشاء محرك الاتصال مع إعدادات Pool محسّنة للإنتاج (يتحمل 10,000+ مستخدم)
engine = create_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,       # 60 اتصال دائم (كان 10)
    max_overflow=MAX_OVERFLOW, # 180 اتصال إضافي (كان 20)
    pool_timeout=30,           # وقت الانتظار للحصول على اتصال
    pool_pre_ping=True,        # التحقق من الاتصال قبل الاستخدام
    pool_recycle=1800,         # إعادة تدوير بعد 30 دقيقة (مناسب لـ Neon)
    pool_reset_on_return='rollback',  # إعادة تعيين الاتصال
    echo=False,                # تعطيل SQL logging
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "connect_timeout": 10,
    } if "postgresql" in DATABASE_URL else {}
)

# جلسة التعامل مع قاعدة البيانات
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# الكلاس الأساسي للنماذج
class Base(DeclarativeBase):
    pass
