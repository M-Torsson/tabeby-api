# تعليمات تشغيل نظام الأرشفة التلقائية

## الخطوة 1: تثبيت المتطلبات

قم بتثبيت المكتبات المطلوبة:

```bash
pip install -r requirements.txt
```

أو تثبيت APScheduler مباشرة:

```bash
pip install APScheduler>=3.10.4
```

## الخطوة 2: التحقق من التثبيت

تحقق من أن المكتبة مثبتة بشكل صحيح:

```bash
python -c "from apscheduler.schedulers.background import BackgroundScheduler; print('OK')"
```

## الخطوة 3: اختبار النظام

قبل تشغيل الـ API، يمكنك اختبار نظام الأرشفة:

```bash
python test_archive_scheduler.py
```

## الخطوة 4: تشغيل الـ API

الآن يمكنك تشغيل الـ API بشكل طبيعي:

```bash
uvicorn app.main:app --reload
```

## التحقق من التشغيل

عند بدء التطبيق، يجب أن تظهر الرسائل التالية في السجلات:

```
✅ Scheduler started successfully
المهام المجدولة:
  - أرشفة الحجوزات العادية: يوميًا 12:00 ص (توقيت العراق)
  - أرشفة الحجوزات الذهبية: يوميًا 12:05 ص (توقيت العراق)
```

## الجدول الزمني

| الوقت (العراق) | الوقت (UTC) | المهمة |
|----------------|-------------|--------|
| 00:00 ص        | 21:00       | أرشفة الحجوزات العادية |
| 00:05 ص        | 21:05       | أرشفة الحجوزات الذهبية |

## ما الذي يحدث تلقائيًا؟

### كل يوم في الساعة 12 ليلاً:

1. **الحجوزات العادية**:
   - جمع جميع الأيام القديمة (قبل اليوم الحالي) من `booking_tables`
   - حفظ كل يوم في `booking_archives` مع:
     - بيانات المرضى
     - السعة الكلية
     - عدد المخدومين
     - عدد الملغيين
   - حذف الأيام القديمة من `booking_tables`

2. **الحجوزات الذهبية** (بعد 5 دقائق):
   - نفس العملية لجداول `golden_booking_tables`
   - حفظ في `golden_booking_archives`

## مثال على البيانات المؤرشفة

```sql
-- عرض الأرشيفات لعيادة رقم 4
SELECT 
    table_date,
    capacity_total,
    capacity_served,
    capacity_cancelled
FROM booking_archives
WHERE clinic_id = 4
ORDER BY table_date DESC;
```

### نموذج نتيجة:

| table_date  | capacity_total | capacity_served | capacity_cancelled |
|-------------|----------------|-----------------|-------------------|
| 2025-11-13  | 600           | 1              | 0                |
| 2025-11-12  | 600           | 1              | 0                |
| 2025-11-11  | 600           | 4              | 0                |
| 2025-11-10  | 600           | 1              | 0                |

## استرجاع البيانات المؤرشفة

### عبر API

```http
GET /api/booking_archives/4
```

### عبر Python

```python
from app.database import SessionLocal
from app import models
import json

db = SessionLocal()

# جلب أرشيف يوم محدد
archive = db.query(models.BookingArchive).filter(
    models.BookingArchive.clinic_id == 4,
    models.BookingArchive.table_date == "2025-11-10"
).first()

if archive:
    patients = json.loads(archive.patients_json)
    print(f"اليوم: {archive.table_date}")
    print(f"عدد المرضى: {len(patients)}")
    for p in patients:
        print(f"  - {p['name']}: {p['status']}")
```

## استكشاف الأخطاء

### المشكلة: المجدول لا يعمل

**الحل:**
- تحقق من السجلات (logs)
- تأكد من تثبيت APScheduler
- أعد تشغيل التطبيق

### المشكلة: لا توجد بيانات في الأرشيف

**السبب المحتمل:**
- لا توجد أيام قديمة للأرشفة
- الأيام القديمة مؤرشفة مسبقًا

**التحقق:**
```python
# عرض الأيام الحالية
from app.database import SessionLocal
from app import models
import json

db = SessionLocal()
bt = db.query(models.BookingTable).filter(
    models.BookingTable.clinic_id == 4
).first()

if bt:
    days = json.loads(bt.days_json)
    print("الأيام الحالية:", list(days.keys()))
```

### المشكلة: أخطاء في التوقيت

**الحل:**
- النظام يستخدم توقيت العراق (UTC+3) تلقائيًا
- يتم التحويل داخل الكود
- لا حاجة لتعديل إعدادات السيرفر

## الصيانة

### إيقاف المجدول مؤقتًا

إذا كنت تريد إيقاف المجدول مؤقتًا، علّق هذا السطر في `main.py`:

```python
# start_scheduler()
```

### تشغيل الأرشفة يدويًا

```python
from app.scheduler import archive_old_bookings, archive_old_golden_bookings

# أرشفة فورية
archive_old_bookings()
archive_old_golden_bookings()
```

## الأسئلة الشائعة

**س: هل ستتم أرشفة اليوم الحالي؟**
ج: لا، فقط الأيام **قبل** اليوم الحالي.

**س: ماذا لو كانت قاعدة البيانات معطلة؟**
ج: سيسجل النظام الخطأ ويحاول مجددًا في اليوم التالي.

**س: هل يمكن تغيير التوقيت؟**
ج: نعم، عدّل قيمة `hour` في ملف `scheduler.py`.

**س: هل البيانات المؤرشفة قابلة للحذف؟**
ج: نعم، لكن احفظ نسخة احتياطية أولاً.

## الدعم

للمزيد من المعلومات، راجع:
- `ARCHIVE_SCHEDULER.md` - الوثائق الكاملة
- `app/scheduler.py` - الكود المصدري
- `test_archive_scheduler.py` - ملف الاختبار
