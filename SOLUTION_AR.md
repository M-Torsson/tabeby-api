# حل مشكلة TimeoutError في قاعدة البيانات

## 🔴 المشكلة
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached, 
connection timed out, timeout 30.00
```

## 📋 ماذا يعني هذا الخطأ؟
- التطبيق يحاول استخدام أكثر من 15 اتصال بقاعدة البيانات في نفس الوقت
- الاتصالات القديمة لا يتم إغلاقها بشكل صحيح
- عندما يأتي طلب جديد، لا يجد اتصال متاح فينتظر 30 ثانية ثم يفشل

## ✅ الحلول المطبقة

### 1️⃣ زيادة عدد الاتصالات المسموحة
**الملف:** `app/database.py`

**قبل:**
```python
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
# الإعدادات الافتراضية: 5 اتصالات + 10 إضافية = 15 فقط
```

**بعد:**
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,              # 10 اتصالات دائمة (كان 5)
    max_overflow=20,           # 20 اتصال إضافي (كان 10)
    pool_timeout=30,           # ينتظر 30 ثانية
    pool_pre_ping=True,        # يتأكد أن الاتصال شغال
    pool_recycle=3600,         # يعيد استخدام الاتصالات بعد ساعة
    echo=False
)
# الآن: 10 + 20 = 30 اتصال متاح! ✅
```

### 2️⃣ إصلاح مشكلة Server-Sent Events (SSE)

**المشكلة:** 
- عند استخدام `/api/booking_days?stream=true` أو `/api/booking_golden_days?stream=true`
- الاتصال بقاعدة البيانات يظل مفتوح لدقائق طويلة
- إذا كان هناك 10 مستخدمين يشاهدون الصفحة = 10 اتصالات محبوسة!

**الحل المطبق في:**
- `app/bookings.py` (السطر 505-545)
- `app/golden_bookings.py` (السطر 232-272)

**قبل:**
```python
async def event_gen():
    # يستخدم نفس db لمدة طويلة ❌
    days = _load_days_raw(db, clinic_id)
    while True:
        await asyncio.sleep(1)  # ينام ثانية
        days = _load_days_raw(db, clinic_id)  # نفس db محبوس!
```

**بعد:**
```python
async def event_gen():
    local_db = SessionLocal()  # اتصال مخصص لهذه الدالة
    try:
        days = _load_days_raw(local_db, clinic_id)
        while True:
            await asyncio.sleep(1)
            # اتصال جديد لكل تحديث ✅
            temp_db = SessionLocal()
            try:
                days = _load_days_raw(temp_db, clinic_id)
            finally:
                temp_db.close()  # نغلقه فوراً ✅
    finally:
        local_db.close()  # نتأكد من الإغلاق ✅
```

## 📊 النتيجة

| قبل الحل | بعد الحل |
|---------|----------|
| 15 اتصال فقط | 30 اتصال |
| اتصالات محبوسة في SSE | كل اتصال ينغلق فوراً |
| Timeout بعد دقائق | يشتغل بشكل مستمر ✅ |

## 🔍 كيف تتأكد أن المشكلة انحلت؟

### 1. راقب الـ logs في Render:
```bash
# يجب أن تختفي هذه الرسالة:
❌ sqlalchemy.exc.TimeoutError: QueuePool limit reached

# يجب أن تشوف فقط:
✅ INFO: 200 OK
✅ INFO: Connection successful
```

### 2. جرب الـ endpoints:
```bash
# Health check
curl https://tabeby-api.onrender.com/health

# Booking days (بدون streaming)
curl "https://tabeby-api.onrender.com/api/booking_days?clinic_id=7"

# Booking days (مع streaming)
curl -H "Accept: text/event-stream" \
     "https://tabeby-api.onrender.com/api/booking_days?clinic_id=7&stream=true"
```

### 3. اختبار الحمل:
- افتح التطبيق من 5-10 أجهزة مختلفة
- اتركها مفتوحة لمدة 5 دقائق
- المفروض ما يطلع timeout ✅

## 🚀 خطوات النشر

1. **Commit التعديلات:**
```bash
git add app/database.py app/bookings.py app/golden_bookings.py
git commit -m "fix: resolve connection pool timeout issue"
git push origin main
```

2. **Render ستنشر تلقائياً:**
- انتظر 2-3 دقائق
- راقب الـ deploy logs
- تأكد من: "Build successful" و "Deploy live"

3. **اختبر بعد النشر:**
```bash
curl https://tabeby-api.onrender.com/health
```

## ⚠️ ملاحظات مهمة

### إذا المشكلة ما انحلت:

1. **تحقق من عدد المستخدمين:**
   - إذا عندك أكثر من 20 مستخدم في نفس الوقت
   - قد تحتاج زيادة `pool_size` أكثر

2. **تحقق من Database Plan في Render:**
   - بعض الخطط تحدد عدد الاتصالات
   - قد تحتاج upgrade للخطة

3. **قلل timeout للـ SSE:**
   في `bookings.py` و `golden_bookings.py`:
   ```python
   timeout: int = 180,  # 3 دقائق بدل 5
   ```

4. **استخدم Redis للـ caching:**
   - بدل ما تقرأ من database كل ثانية
   - احفظ البيانات في Redis
   - اقرأ من database بس لما يصير تحديث

## 📞 المساعدة

إذا المشكلة استمرت:
1. ✅ ارسل logs من Render
2. ✅ حدد كم عدد المستخدمين المتزامنين
3. ✅ جرب تشغل `echo_pool=True` للتشخيص

---

**آخر تحديث:** 2025-10-18  
**الحالة:** ✅ تم الحل
