# نظام تتبع مدفوعات الحجوزات الذهبية 💰

## نظرة عامة
نظام شامل لتتبع مدفوعات المرضى في الحجوزات الذهبية، مع تقارير شهرية وسنوية مفصلة.

---

## الآليــة

### عند تأكيد المريض من قبل السكرتيرة:
1. السكرتيرة تدخل الكود المكون من 4 أرقام
2. النظام يتحقق من الكود ويعرض بيانات المريض
3. عند الضغط على زر **"تأكيد"**
4. يتم إرسال طلب API لحفظ سجل الدفع:
   - المبلغ الثابت: **1500 دينار عراقي** لكل مريض
   - يتم ربط السجل بـ `clinic_id` و `booking_id`
   - يحفظ تاريخ الفحص والشهر (بصيغة `YYYY-MM`)
   - الحالة الافتراضية: `not_paid`

---

## قاعدة البيانات

### جدول `golden_payments`

```sql
CREATE TABLE golden_payments (
    id SERIAL PRIMARY KEY,
    clinic_id INTEGER NOT NULL,
    booking_id VARCHAR UNIQUE NOT NULL,
    patient_name VARCHAR NOT NULL,
    code VARCHAR(4) NOT NULL,
    exam_date VARCHAR(20) NOT NULL,
    amount INTEGER NOT NULL DEFAULT 1500,
    payment_month VARCHAR(7) NOT NULL,  -- Format: YYYY-MM
    payment_status VARCHAR(20) NOT NULL DEFAULT 'not_paid',
    book_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_clinic_payment_month ON golden_payments(clinic_id, payment_month);
```

---

## الـ APIs المتاحة

### 1️⃣ حفظ دفعة مريض جديد
**POST** `/api/golden_patient_payment`

#### Request Body:
```json
{
  "clinic_id": 4,
  "exam_date": "23/10/2025",
  "book_status": "تمت المعاينة",
  "patient_name": "عمر احمد",
  "booking_id": "G-4-20251023-P-71",
  "code": "6270"
}
```

#### Response (200):
```json
{
  "message": "تم حفظ الدفعة بنجاح",
  "booking_id": "G-4-20251023-P-71",
  "patient_name": "عمر احمد",
  "amount": 1500,
  "payment_month": "2025-10",
  "payment_status": "not_paid"
}
```

#### Response (409) - إذا كان الـ booking_id مسجل سابقاً:
```json
{
  "detail": "هذا الحجز مسجل مسبقاً"
}
```

---

### 2️⃣ التقرير الشهري للعيادة
**GET** `/api/doctor_monthly_golden_payment_status?clinic_id=4`

#### Response (200):
```json
{
  "2025-10": {
    "payment_month": "2025-10",
    "patient_count": 3,
    "total_amount": 4500,
    "payment_status": "not_paid",
    "patients": [
      {
        "patient_name": "عمر احمد",
        "exam_date": "23/10/2025",
        "amount": 1500
      },
      {
        "patient_name": "علي حسن",
        "exam_date": "25/10/2025",
        "amount": 1500
      },
      {
        "patient_name": "فاطمة محمد",
        "exam_date": "28/10/2025",
        "amount": 1500
      }
    ]
  },
  "2025-11": {
    "payment_month": "2025-11",
    "patient_count": 2,
    "total_amount": 3000,
    "payment_status": "not_paid",
    "patients": [
      {
        "patient_name": "محمد علي",
        "exam_date": "05/11/2025",
        "amount": 1500
      },
      {
        "patient_name": "سارة احمد",
        "exam_date": "12/11/2025",
        "amount": 1500
      }
    ]
  }
}
```

**الفائدة:**
- رؤية تفصيلية لكل شهر
- عدد المرضى والمبلغ الإجمالي لكل شهر
- قائمة بأسماء المرضى مع تواريخ الفحص
- معرفة الأشهر المدفوعة وغير المدفوعة

---

### 3️⃣ التقرير السنوي للعيادة
**GET** `/api/doctor_annual_payment_status?clinic_id=4`

#### Response (200):
```json
{
  "clinic_id": 4,
  "year": 2025,
  "total_paid": 4500,
  "remain_amount": 3000,
  "months": {
    "2025-10": "paid",
    "2025-11": "not_paid"
  }
}
```

**الحسابات:**
- `total_paid`: مجموع المبالغ المدفوعة فعلياً (الأشهر بحالة `paid`)
- `remain_amount`: المبالغ المتبقية (الأشهر بحالة `not_paid`)
- `months`: خريطة لكل الأشهر مع حالة الدفع

---

### 4️⃣ تحديث حالة دفع شهر معين
**POST** `/api/update_payment_status`

#### Request Body:
```json
{
  "clinic_id": 4,
  "payment_month": "2025-10",
  "payment_status": "paid"
}
```

#### Response (200):
```json
{
  "message": "تم تحديث حالة الدفع بنجاح",
  "clinic_id": 4,
  "payment_month": "2025-10",
  "payment_status": "paid",
  "updated_count": 3
}
```

**ملاحظة:** `updated_count` يمثل عدد السجلات المحدثة (عدد المرضى في ذلك الشهر).

---

## الحماية والأمان

جميع الـ APIs تتطلب Header للمصادقة:
```
Doctor-Secret: YOUR_SECRET_HERE
```

يتم ضبط قيمة الـ Secret في متغيرات البيئة:
```bash
DOCTOR_PROFILE_SECRET=your-secret-value
```

---

## خطوات التشغيل

### 1. تشغيل Migration على قاعدة البيانات:
```bash
psql -U postgres -d tabeby_db -f migrations/add_golden_payments.sql
```

### 2. التأكد من تحديث الـ Environment Variables:
```bash
export DOCTOR_PROFILE_SECRET="your-secret-here"
```

### 3. إعادة تشغيل السيرفر:
```bash
uvicorn app.main:app --reload
```

---

## اختبار الـ APIs

### استخدام curl:

#### 1. حفظ دفعة:
```bash
curl -X POST "http://localhost:8000/api/golden_patient_payment" \
  -H "Doctor-Secret: test-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "clinic_id": 4,
    "exam_date": "23/10/2025",
    "book_status": "تمت المعاينة",
    "patient_name": "عمر احمد",
    "booking_id": "G-4-20251023-P-71",
    "code": "6270"
  }'
```

#### 2. عرض التقرير الشهري:
```bash
curl -X GET "http://localhost:8000/api/doctor_monthly_golden_payment_status?clinic_id=4" \
  -H "Doctor-Secret: test-secret"
```

#### 3. عرض التقرير السنوي:
```bash
curl -X GET "http://localhost:8000/api/doctor_annual_payment_status?clinic_id=4" \
  -H "Doctor-Secret: test-secret"
```

#### 4. تحديث حالة الدفع:
```bash
curl -X POST "http://localhost:8000/api/update_payment_status" \
  -H "Doctor-Secret: test-secret" \
  -H "Content-Type: application/json" \
  -d '{
    "clinic_id": 4,
    "payment_month": "2025-10",
    "payment_status": "paid"
  }'
```

---

## مثال سيناريو كامل

### السيناريو:
عيادة برقم `clinic_id = 4` لديها حجوزات ذهبية لثلاثة مرضى في أكتوبر 2025.

#### الخطوة 1: السكرتيرة تؤكد المريض الأول
```bash
POST /api/golden_patient_payment
{
  "clinic_id": 4,
  "exam_date": "10/10/2025",
  "patient_name": "أحمد محمد",
  "booking_id": "G-4-20251010-P-1",
  "code": "1234"
}
```

#### الخطوة 2: السكرتيرة تؤكد المريض الثاني
```bash
POST /api/golden_patient_payment
{
  "clinic_id": 4,
  "exam_date": "15/10/2025",
  "patient_name": "فاطمة علي",
  "booking_id": "G-4-20251015-P-2",
  "code": "5678"
}
```

#### الخطوة 3: السكرتيرة تؤكد المريض الثالث
```bash
POST /api/golden_patient_payment
{
  "clinic_id": 4,
  "exam_date": "20/10/2025",
  "patient_name": "سارة حسن",
  "booking_id": "G-4-20251020-P-3",
  "code": "9012"
}
```

#### الخطوة 4: الطبيب يطلب التقرير الشهري
```bash
GET /api/doctor_monthly_golden_payment_status?clinic_id=4
```

**النتيجة:**
```json
{
  "2025-10": {
    "payment_month": "2025-10",
    "patient_count": 3,
    "total_amount": 4500,
    "payment_status": "not_paid",
    "patients": [
      {"patient_name": "أحمد محمد", "exam_date": "10/10/2025", "amount": 1500},
      {"patient_name": "فاطمة علي", "exam_date": "15/10/2025", "amount": 1500},
      {"patient_name": "سارة حسن", "exam_date": "20/10/2025", "amount": 1500}
    ]
  }
}
```

#### الخطوة 5: الطبيب يطلب التقرير السنوي
```bash
GET /api/doctor_annual_payment_status?clinic_id=4
```

**النتيجة:**
```json
{
  "clinic_id": 4,
  "year": 2025,
  "total_paid": 0,
  "remain_amount": 4500,
  "months": {
    "2025-10": "not_paid"
  }
}
```

#### الخطوة 6: الأدمن يحدث حالة الدفع بعد استلام المبلغ
```bash
POST /api/update_payment_status
{
  "clinic_id": 4,
  "payment_month": "2025-10",
  "payment_status": "paid"
}
```

#### الخطوة 7: الطبيب يطلب التقرير السنوي مجدداً
```bash
GET /api/doctor_annual_payment_status?clinic_id=4
```

**النتيجة بعد التحديث:**
```json
{
  "clinic_id": 4,
  "year": 2025,
  "total_paid": 4500,
  "remain_amount": 0,
  "months": {
    "2025-10": "paid"
  }
}
```

---

## ملاحظات مهمة

1. **المبلغ الثابت:** كل مريض = 1500 دينار عراقي
2. **تنسيق الشهر:** `YYYY-MM` (مثال: `2025-10`)
3. **منع التكرار:** لا يمكن حفظ نفس `booking_id` مرتين
4. **التجميع التلقائي:** النظام يجمع المرضى حسب الشهر تلقائياً
5. **الحالات المتاحة:**
   - `not_paid` (افتراضي عند الإنشاء)
   - `paid` (بعد استلام الدفع من الطبيب)

---

## الملفات المعدلة في النظام

1. **app/models.py** - إضافة `GoldenPayment` model
2. **app/schemas.py** - إضافة `GoldenPatientPaymentRequest` و `GoldenPatientPaymentResponse`
3. **app/golden_payments.py** - Router جديد يحتوي 4 endpoints
4. **app/main.py** - تسجيل الـ router الجديد
5. **migrations/add_golden_payments.sql** - Migration لإنشاء الجدول
6. **test_golden_payments.py** - دليل الاختبار مع أمثلة curl

---

## Git Commit
```
commit 1287f6e
Author: M-Torsson
Date: 2025-10-29

Add golden payments tracking system - Monthly/annual reports with 1500 IQD per patient

- Created golden_payments table with migration
- Added GoldenPayment model with clinic_id and payment_month indexes
- Implemented 4 endpoints: save payment, monthly report, annual report, update status
- Fixed amount calculation: 1500 IQD per patient
- Monthly grouping by YYYY-MM format
- Payment status tracking (not_paid/paid)
```

---

## الدعم والتطوير المستقبلي

### إضافات محتملة:
- [ ] تصدير التقارير إلى PDF
- [ ] إرسال إشعارات للطبيب عند اكتمال شهر جديد
- [ ] نظام التذكير بالمدفوعات المتأخرة
- [ ] لوحة تحكم بيانية للمدفوعات
- [ ] سجل تعديلات حالة الدفع (audit log)

---

**تم بحمد الله ✅**
