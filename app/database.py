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

# إنشاء محرك الاتصال مع إعدادات Pool محسّنة
engine = create_engine(
    DATABASE_URL,
    pool_size=10,              # عدد الاتصالات الدائمة في البول
    max_overflow=20,           # الحد الأقصى للاتصالات الإضافية
    pool_timeout=30,           # وقت الانتظار للحصول على اتصال
    pool_pre_ping=True,        # التحقق من الاتصال قبل الاستخدام
    pool_recycle=3600,         # إعادة تدوير الاتصالات بعد ساعة
    echo=False                 # تعطيل SQL logging في الإنتاج
)

# جلسة التعامل مع قاعدة البيانات
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# الكلاس الأساسي للنماذج
class Base(DeclarativeBase):
    pass
