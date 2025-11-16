# -*- coding: utf-8 -*-
"""
اختبار save_table_gold - يجب أن يحذف اليوم من JSON بعد الحفظ
"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import GoldenBookingTable, GoldenBookingArchive
import os
import json

os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')

client = TestClient(app)
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print("=" * 80)
print("اختبار save_table_gold - يجب حذف اليوم بعد الحفظ")
print("=" * 80)

# 1. إنشاء يوم تجريبي
print("\n1️⃣ إنشاء يوم تجريبي...")
db = SessionLocal()

# تحقق من وجود جدول
gt = db.query(GoldenBookingTable).filter(GoldenBookingTable.clinic_id == 4).first()
if not gt:
    print("   ❌ لا يوجد جدول ذهبي")
    db.close()
    exit()

# إضافة يوم تجريبي
days = json.loads(gt.days_json) if gt.days_json else {}
test_date = "2025-12-25"
days[test_date] = {
    "status": "open",
    "capacity_total": 10,
    "capacity_used": 1,
    "patients": [
        {
            "booking_id": "TEST-123",
            "name": "مريض تجريبي",
            "phone": "+9647700000000",
            "status": "تم الحجز"
        }
    ]
}
gt.days_json = json.dumps(days, ensure_ascii=False)
db.add(gt)
db.commit()
print(f"   ✅ تم إضافة يوم {test_date}")
print(f"   عدد الأيام قبل الحفظ: {len(days)}")

db.close()

# 2. استدعاء save_table_gold
print("\n2️⃣ استدعاء save_table_gold...")
payload = {
    "clinic_id": 4,
    "closed_date": test_date  # استخدام closed_date حسب schema
}
r = client.post('/api/save_table_gold', json=payload, headers=headers)
print(f"   Status: {r.status_code}")
print(f"   Response: {r.json()}")

# 3. فحص النتيجة
print("\n3️⃣ فحص النتيجة:")
db = SessionLocal()

# فحص الجدول
gt_after = db.query(GoldenBookingTable).filter(GoldenBookingTable.clinic_id == 4).first()
if gt_after:
    days_after = json.loads(gt_after.days_json) if gt_after.days_json else {}
    if test_date in days_after:
        print(f"   ❌ اليوم {test_date} لا يزال موجوداً في الجدول!")
    else:
        print(f"   ✅ اليوم {test_date} تم حذفه من الجدول")
    print(f"   عدد الأيام بعد الحفظ: {len(days_after)}")
else:
    print("   ✅ الجدول تم حذفه بالكامل")

# فحص الأرشيف
arch = db.query(GoldenBookingArchive).filter(
    GoldenBookingArchive.clinic_id == 4,
    GoldenBookingArchive.table_date == test_date
).first()

if arch:
    print(f"\n4️⃣ الأرشيف:")
    print(f"   ✅ اليوم موجود في الأرشيف")
    print(f"   إجمالي: {arch.capacity_total}")
    patients = json.loads(arch.patients_json) if arch.patients_json else []
    print(f"   عدد المرضى: {len(patients)}")
    
    # تنظيف - حذف الأرشيف التجريبي
    db.delete(arch)
    db.commit()
    print(f"\n5️⃣ تم حذف البيانات التجريبية من الأرشيف")
else:
    print(f"\n4️⃣ الأرشيف:")
    print(f"   ❌ اليوم غير موجود في الأرشيف!")

db.close()

print("\n" + "=" * 80)
