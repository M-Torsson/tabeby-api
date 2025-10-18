# إصلاح مشكلة Connection Pool Timeout

## المشكلة
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00
```

## التشخيص
المشكلة تحدث عندما:
1. يتم استنفاد جميع الاتصالات المتاحة في connection pool (5 + 10 = 15 اتصال)
2. الاتصالات لا يتم إرجاعها بشكل صحيح إلى البول
3. طلبات SSE (Server-Sent Events) تحتفظ بالاتصالات مفتوحة لفترات طويلة

## الحلول المطبقة

### 1. زيادة حجم Connection Pool (في `app/database.py`)
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,              # زيادة من 5 إلى 10
    max_overflow=20,           # زيادة من 10 إلى 20
    pool_timeout=30,           # وقت الانتظار
    pool_pre_ping=True,        # التحقق من الاتصال قبل الاستخدام
    pool_recycle=3600,         # إعادة تدوير الاتصالات كل ساعة
    echo=False                 # تعطيل SQL logging
)
```

**الفوائد:**
- السماح بعدد أكبر من الاتصالات المتزامنة (30 بدلاً من 15)
- `pool_recycle=3600`: يمنع الاتصالات من البقاء مفتوحة إلى الأبد
- `pool_pre_ping=True`: يتحقق من صلاحية الاتصال قبل استخدامه

### 2. إصلاح SSE في `app/bookings.py` و `app/golden_bookings.py`

**المشكلة الأصلية:**
```python
async def event_gen():
    # يستخدم نفس db من الـ dependency
    days = _load_days_raw(db, clinic_id)  # ❌ يحبس الاتصال
    while True:
        await asyncio.sleep(poll_interval)
        days = _load_days_raw(db, clinic_id)  # ❌ نفس الاتصال محبوس
```

**الحل:**
```python
async def event_gen():
    # استخدام session منفصل
    local_db = SessionLocal()
    try:
        days = _load_days_raw(local_db, clinic_id)  # ✅
        while True:
            await asyncio.sleep(poll_interval)
            # استخدام session جديد لكل استعلام
            temp_db = SessionLocal()
            try:
                days = _load_days_raw(temp_db, clinic_id)  # ✅
            finally:
                temp_db.close()  # ✅ إغلاق فوري
    finally:
        local_db.close()  # ✅ التأكد من الإغلاق
```

**الفوائد:**
- كل استعلام يستخدم اتصال جديد ويغلقه مباشرة
- الاتصالات لا تبقى محبوسة أثناء `await asyncio.sleep()`
- يمنع تراكم الاتصالات المفتوحة

### 3. التحقق من استخدام Dependency Injection

**الطريقة الصحيحة:**
```python
@router.get("/endpoint")
def my_endpoint(db: Session = Depends(get_db)):
    # ✅ FastAPI ستغلق الاتصال تلقائياً
    result = db.query(Model).all()
    return result
```

**الطريقة الخاطئة:**
```python
@router.get("/endpoint")
def my_endpoint():
    db = SessionLocal()  # ❌
    result = db.query(Model).all()
    # ⚠️ قد ينسى المطور إغلاق db
    return result
```

## التوصيات الإضافية

### 1. مراقبة الاتصالات
أضف logging لمراقبة استخدام connection pool:
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo_pool=True  # يطبع معلومات عن البول
)
```

### 2. استخدام Context Manager
في الحالات الاستثنائية التي تحتاج SessionLocal() مباشرة:
```python
def some_function():
    db = SessionLocal()
    try:
        # العمليات هنا
        result = db.query(Model).all()
        return result
    finally:
        db.close()  # ✅ دائماً أغلق
```

### 3. تقليل timeout للـ SSE
في `bookings.py` و `golden_bookings.py`:
```python
timeout: int = 300,  # 5 دقائق - قلل إذا كنت تريد
```

### 4. استخدام Database Middleware
للتأكد من إغلاق جميع الاتصالات:
```python
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = await call_next(request)
    # يمكن إضافة تنظيف هنا إذا لزم الأمر
    return response
```

## التحقق من الحل

### 1. راقب logs بعد التحديث
ابحث عن:
- ✅ لا توجد TimeoutError
- ✅ الطلبات تعمل بشكل طبيعي
- ✅ عدد الاتصالات المفتوحة معقول

### 2. استخدام Database Monitoring
في PostgreSQL:
```sql
-- عرض الاتصالات النشطة
SELECT count(*) FROM pg_stat_activity 
WHERE datname = 'your_database_name';

-- عرض الاتصالات المعلقة
SELECT * FROM pg_stat_activity 
WHERE state = 'idle in transaction'
AND state_change < NOW() - INTERVAL '5 minutes';
```

### 3. Health Check
استخدم `/health` endpoint للتحقق من صحة الاتصالات:
```bash
curl https://your-api.onrender.com/health
```

## ملاحظات للإنتاج

1. **Render.com Settings:**
   - تأكد من أن database plan يدعم عدد الاتصالات المطلوبة
   - قد تحتاج upgrade إذا كان عدد المستخدمين كبير

2. **Environment Variables:**
   ```env
   DATABASE_URL=postgresql+psycopg://user:pass@host/db
   # تأكد من استخدام psycopg (أسرع من psycopg2)
   ```

3. **Monitoring:**
   - استخدم أدوات مثل Sentry أو DataDog لمراقبة الأخطاء
   - فعّل `echo_pool=True` مؤقتاً للتشخيص

## الخلاصة

التعديلات الرئيسية:
1. ✅ زيادة pool_size من 5 إلى 10
2. ✅ زيادة max_overflow من 10 إلى 20
3. ✅ إصلاح SSE في bookings.py
4. ✅ إصلاح SSE في golden_bookings.py
5. ✅ إضافة pool_recycle لمنع الاتصالات القديمة

هذه الحلول يجب أن تحل المشكلة بشكل كامل! 🎉
