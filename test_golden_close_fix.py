# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient
from app.main import app
import os
import json

os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')

client = TestClient(app)
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print("=" * 80)
print("اختبار إصلاح close_table للحجوزات الذهبية")
print("=" * 80)

# 1. إنشاء يوم جديد
print("\n1️⃣ إنشاء يوم ذهبي جديد...")
create_payload = {
    "clinic_id": 999,
    "date": "2025-12-20",
    "capacity_total": 5
}
r1 = client.post('/golden_bookings/create_day', json=create_payload, headers=headers)
print(f"Status: {r1.status_code} - {r1.json().get('message', 'OK')}")

# 2. إضافة 3 مرضى
print("\n2️⃣ إضافة 3 مرضى...")
for i in range(1, 4):
    book_payload = {
        "clinic_id": 999,
        "date": "2025-12-20",
        "patientName": f"Patient {i}",
        "patientPhone": f"+96477012345{i}",
        "status": "active"
    }
    r2 = client.post('/golden_bookings/book', json=book_payload, headers=headers)
    print(f"   مريض {i}: {r2.status_code}")

# 3. تغيير حالة أحد المرضى إلى "تمت المعاينة"
print("\n3️⃣ تغيير حالة المريض الأول إلى 'تمت المعاينة'...")
r_days = client.get('/golden_bookings/days/999', headers=headers)
day_data = r_days.json()['days']['2025-12-20']
first_patient = day_data['patients'][0]
first_booking_id = first_patient['booking_id']

status_payload = {
    "clinic_id": 999,
    "date": "2025-12-20",
    "booking_id": first_booking_id,
    "new_status": "تمت المعاينة"
}
r3 = client.post('/golden_bookings/update_status', json=status_payload, headers=headers)
print(f"Status update: {r3.status_code}")

# 4. عرض حالة المرضى قبل الإغلاق
print("\n4️⃣ حالة المرضى قبل الإغلاق:")
r_before = client.get('/golden_bookings/days/999', headers=headers)
patients_before = r_before.json()['days']['2025-12-20']['patients']
for i, p in enumerate(patients_before, 1):
    print(f"   {i}. {p['patientName']} - {p['status']}")

# 5. إغلاق اليوم
print("\n5️⃣ إغلاق اليوم...")
close_payload = {
    "clinic_id": 999,
    "date": "2025-12-20"
}
r4 = client.post('/golden_bookings/close_table_gold', json=close_payload, headers=headers)
print(f"Close status: {r4.status_code} - {r4.json().get('status', 'OK')}")

# 6. فحص الأرشيف
print("\n6️⃣ فحص الأرشيف...")
from app.database import SessionLocal
from app.models import GoldenBookingArchive

db = SessionLocal()
arch = db.query(GoldenBookingArchive).filter(
    GoldenBookingArchive.clinic_id == 999,
    GoldenBookingArchive.table_date == "2025-12-20"
).first()

if arch:
    patients_archived = json.loads(arch.patients_json)
    print(f"✅ وجد في الأرشيف!")
    print(f"   إجمالي: {arch.capacity_total}")
    print(f"   معاينة: {arch.capacity_served}")
    print(f"   ملغى: {arch.capacity_cancelled}")
    print(f"\n   حالة المرضى في الأرشيف:")
    for i, p in enumerate(patients_archived, 1):
        status = p.get('status')
        name = p.get('patientName')
        if status == "ملغى":
            print(f"   {i}. {name} - ✅ {status}")
        elif status == "تمت المعاينة":
            print(f"   {i}. {name} - ✅ {status}")
        else:
            print(f"   {i}. {name} - ❌ {status} (يجب أن يكون ملغى أو تمت المعاينة)")
else:
    print("❌ لم يوجد في الأرشيف!")

# 7. تنظيف (حذف الأرشيف التجريبي)
if arch:
    db.delete(arch)
    db.commit()
    print("\n7️⃣ تم حذف البيانات التجريبية")

db.close()

print("\n" + "=" * 80)
print("انتهى الاختبار")
print("=" * 80)
