# 📚 دليل APIs الأرشيف - جلب الأيام والمرضى المؤرشفة

## 📌 نظرة عامة

يوفر النظام **APIs منفصلة** لجلب الأرشيف للحجوزات العادية والذهبية، مع إمكانية الفلترة بالتاريخ والتحكم بعدد النتائج.

---

## 🔵 1. أرشيف الحجوزات العادية

### Endpoint
```http
GET /api/booking_archives/{clinic_id}
```

### المعاملات (Query Parameters)
| المعامل | النوع | اختياري | الوصف |
|---------|------|---------|-------|
| `from_date` | string | نعم | بداية نطاق التاريخ (YYYY-MM-DD) |
| `to_date` | string | نعم | نهاية نطاق التاريخ (YYYY-MM-DD) |
| `limit` | integer | نعم | الحد الأقصى لعدد الأيام المُرجعة |

### Headers المطلوبة
```http
Doctor-Secret: your-secret-here
```

### مثال 1: جلب كل الأرشيف
```bash
GET https://tabeby-api.onrender.com/api/booking_archives/4
```

### مثال 2: جلب أرشيف بنطاق تاريخي
```bash
GET https://tabeby-api.onrender.com/api/booking_archives/4?from_date=2025-11-10&to_date=2025-11-15
```

### مثال 3: جلب آخر 10 أيام مؤرشفة
```bash
GET https://tabeby-api.onrender.com/api/booking_archives/4?limit=10
```

### Response
```json
{
  "clinic_id": 4,
  "items": [
    {
      "table_date": "2025-11-13",
      "capacity_total": 600,
      "capacity_served": 5,
      "capacity_cancelled": 2,
      "patients": [
        {
          "booking_id": "B-4-20251113-0001",
          "token": 1,
          "patient_id": "P-90",
          "name": "ياسين مرتضى",
          "phone": "+46666777881",
          "source": "patient_app",
          "status": "تمت المعاينة",
          "created_at": "2025-11-12T21:07:51.020621+00:00"
        },
        {
          "booking_id": "B-4-20251113-0002",
          "token": 2,
          "patient_id": "P-85",
          "name": "محمد علي",
          "phone": "+9647701234567",
          "source": "clinic_app",
          "status": "تم الحجز",
          "created_at": "2025-11-13T08:15:30.123456+00:00"
        }
      ]
    },
    {
      "table_date": "2025-11-12",
      "capacity_total": 600,
      "capacity_served": 3,
      "capacity_cancelled": 1,
      "patients": [...]
    }
  ]
}
```

---

## 🟡 2. أرشيف الحجوزات الذهبية

### Endpoint
```http
GET /api/golden_booking_archives/{clinic_id}
```

### المعاملات (Query Parameters)
| المعامل | النوع | اختياري | الوصف |
|---------|------|---------|-------|
| `from_date` | string | نعم | بداية نطاق التاريخ (YYYY-MM-DD) |
| `to_date` | string | نعم | نهاية نطاق التاريخ (YYYY-MM-DD) |
| `limit` | integer | نعم | الحد الأقصى لعدد الأيام المُرجعة |

### Headers المطلوبة
```http
Doctor-Secret: your-secret-here
```

### مثال 1: جلب كل الأرشيف الذهبي
```bash
GET https://tabeby-api.onrender.com/api/golden_booking_archives/4
```

### مثال 2: جلب أرشيف ذهبي بنطاق تاريخي
```bash
GET https://tabeby-api.onrender.com/api/golden_booking_archives/4?from_date=2025-11-01&to_date=2025-11-30
```

### مثال 3: جلب آخر 5 أيام ذهبية مؤرشفة
```bash
GET https://tabeby-api.onrender.com/api/golden_booking_archives/4?limit=5
```

### Response
```json
{
  "clinic_id": 4,
  "items": [
    {
      "table_date": "2025-11-13",
      "capacity_total": 5,
      "capacity_served": 3,
      "capacity_cancelled": 1,
      "patients": [
        {
          "booking_id": "G-4-20251113-P-123",
          "token": 1,
          "patient_id": "P-123",
          "name": "أحمد حسين",
          "phone": "+9647801234567",
          "status": "تمت المعاينة",
          "code": "1234",
          "created_at": "2025-11-13T09:30:00.000000+00:00"
        },
        {
          "booking_id": "G-4-20251113-P-456",
          "token": 2,
          "patient_id": "P-456",
          "name": "فاطمة علي",
          "phone": "+9647802345678",
          "status": "تم الحجز",
          "code": "5678",
          "created_at": "2025-11-13T10:15:00.000000+00:00"
        }
      ]
    },
    {
      "table_date": "2025-11-12",
      "capacity_total": 5,
      "capacity_served": 2,
      "capacity_cancelled": 0,
      "patients": [...]
    }
  ]
}
```

---

## 📊 بنية البيانات المُرجعة

### بنية `BookingArchivesListResponse`
```json
{
  "clinic_id": <integer>,
  "items": [<BookingArchiveItem>, ...]
}
```

### بنية `BookingArchiveItem`
```json
{
  "table_date": "YYYY-MM-DD",
  "capacity_total": <integer>,
  "capacity_served": <integer|null>,
  "capacity_cancelled": <integer|null>,
  "patients": [<Patient>, ...]
}
```

### بنية `Patient` للحجوزات العادية
```json
{
  "booking_id": "B-{clinic_id}-{date}-{sequence}",
  "token": <integer>,
  "patient_id": "P-{id}",
  "name": "اسم المريض",
  "phone": "+9647XXXXXXXXX",
  "source": "patient_app" | "clinic_app",
  "status": "تم الحجز" | "تمت المعاينة" | "ملغى" | "لم يحضر",
  "created_at": "ISO8601 timestamp"
}
```

### بنية `Patient` للحجوزات الذهبية
```json
{
  "booking_id": "G-{clinic_id}-{date}-{patient_id}",
  "token": <integer>,
  "patient_id": "P-{id}",
  "name": "اسم المريض",
  "phone": "+9647XXXXXXXXX",
  "status": "تم الحجز" | "تمت المعاينة" | "ملغى" | "لم يحضر",
  "code": "4-digit code",
  "created_at": "ISO8601 timestamp"
}
```

---

## 🔐 المصادقة (Authentication)

جميع APIs تتطلب header:
```http
Doctor-Secret: your-secret-key
```

يتم تعيين `DOCTOR_PROFILE_SECRET` في متغيرات البيئة.

---

## ⚠️ رموز الأخطاء

| رمز الخطأ | الوصف |
|----------|-------|
| `400` | صيغة التاريخ غير صحيحة (يجب YYYY-MM-DD) |
| `401` | لم يتم تقديم Doctor-Secret أو غير صحيح |
| `404` | العيادة غير موجودة أو لا توجد بيانات مؤرشفة |
| `500` | خطأ في الخادم |

---

## 📝 ملاحظات مهمة

### ترتيب النتائج
- الأيام تُرجع مرتبة **تنازلياً** (الأحدث أولاً)
- يمكن التحكم في العدد باستخدام `limit`

### الأرشفة التلقائية
- تحدث الأرشفة يومياً في **الساعة 12:00 ليلاً** بتوقيت العراق
- الحجوزات العادية: 21:00 UTC (00:00 Iraq)
- الحجوزات الذهبية: 21:05 UTC (00:05 Iraq)

### الفرق بين الحجوزات العادية والذهبية

| الميزة | حجوزات عادية | حجوزات ذهبية |
|--------|--------------|---------------|
| السعة | 600+ مريض/يوم | 5 مرضى/يوم |
| الكود | لا يوجد | كود 4 أرقام |
| التوكن | تسلسلي بسيط | تسلسلي (يُعاد حساب عند الإلغاء) |
| البادئة | B- | G- |

---

## 🧪 اختبار APIs

### باستخدام cURL

#### أرشيف الحجوزات العادية
```bash
curl -X GET "https://tabeby-api.onrender.com/api/booking_archives/4" \
  -H "Doctor-Secret: your-secret-here"
```

#### أرشيف الحجوزات الذهبية
```bash
curl -X GET "https://tabeby-api.onrender.com/api/golden_booking_archives/4" \
  -H "Doctor-Secret: your-secret-here"
```

### باستخدام Python
```python
import requests

BASE_URL = "https://tabeby-api.onrender.com"
SECRET = "your-secret-here"
CLINIC_ID = 4

headers = {"Doctor-Secret": SECRET}

# جلب أرشيف الحجوزات العادية
response = requests.get(
    f"{BASE_URL}/api/booking_archives/{CLINIC_ID}",
    headers=headers
)
print("حجوزات عادية:", response.json())

# جلب أرشيف الحجوزات الذهبية
response = requests.get(
    f"{BASE_URL}/api/golden_booking_archives/{CLINIC_ID}",
    headers=headers,
    params={"from_date": "2025-11-01", "limit": 10}
)
print("حجوزات ذهبية:", response.json())
```

### باستخدام JavaScript/Fetch
```javascript
const BASE_URL = "https://tabeby-api.onrender.com";
const SECRET = "your-secret-here";
const CLINIC_ID = 4;

// جلب أرشيف الحجوزات العادية
fetch(`${BASE_URL}/api/booking_archives/${CLINIC_ID}`, {
  headers: { "Doctor-Secret": SECRET }
})
  .then(res => res.json())
  .then(data => console.log("حجوزات عادية:", data));

// جلب أرشيف الحجوزات الذهبية
fetch(`${BASE_URL}/api/golden_booking_archives/${CLINIC_ID}?limit=5`, {
  headers: { "Doctor-Secret": SECRET }
})
  .then(res => res.json())
  .then(data => console.log("حجوزات ذهبية:", data));
```

---

## 🎯 حالات استخدام شائعة

### 1. عرض تقرير شهري للحجوزات
```bash
GET /api/booking_archives/4?from_date=2025-11-01&to_date=2025-11-30
```

### 2. البحث عن مريض في الأرشيف
اجلب كل الأرشيف ثم ابحث في `patients` array:
```python
response = requests.get(f"{BASE_URL}/api/booking_archives/{CLINIC_ID}", headers=headers)
for item in response.json()["items"]:
    for patient in item["patients"]:
        if patient["phone"] == "+9647801234567":
            print(f"وجدت المريض في {item['table_date']}")
```

### 3. حساب إحصائيات الأرشيف
```python
response = requests.get(f"{BASE_URL}/api/booking_archives/{CLINIC_ID}", headers=headers)
total_served = sum(item.get("capacity_served", 0) for item in response.json()["items"])
total_cancelled = sum(item.get("capacity_cancelled", 0) for item in response.json()["items"])
print(f"إجمالي المخدومين: {total_served}")
print(f"إجمالي الملغيين: {total_cancelled}")
```

---

## 📖 المزيد من التوثيق

- **نظام الأرشفة التلقائية**: `ARCHIVE_SCHEDULER.md`
- **تعليمات التشغيل**: `INSTALLATION_ARCHIVE.md`
- **دليل Postman**: `POSTMAN_GUIDE.md`
- **ملف README الأرشيف**: `README_ARCHIVE.md`

---

## ✅ الخلاصة

يوفر النظام **endpoints منفصلة** للحجوزات العادية والذهبية:

| النوع | Endpoint | الوصف |
|------|----------|-------|
| 🔵 عادية | `/api/booking_archives/{clinic_id}` | أرشيف الحجوزات العادية |
| 🟡 ذهبية | `/api/golden_booking_archives/{clinic_id}` | أرشيف الحجوزات الذهبية |

كلاهما يدعم:
- ✅ الفلترة بالتاريخ (`from_date`, `to_date`)
- ✅ تحديد عدد النتائج (`limit`)
- ✅ إرجاع قائمة كاملة بالمرضى وتفاصيلهم
- ✅ ترتيب تنازلي (الأحدث أولاً)

🎉 **تم إضافة endpoint الحجوزات الذهبية بنجاح!**
