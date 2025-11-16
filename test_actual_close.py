# -*- coding: utf-8 -*-
"""
اختبار فعلي لإغلاق يوم ذهبي
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
print("اختبار إغلاق يوم ذهبي فعلي - clinic_id=4, date=2025-11-17")
print("=" * 80)

# 1. قبل الإغلاق
print("\n1️⃣ قبل الإغلاق:")
db = SessionLocal()
gt_before = db.query(GoldenBookingTable).filter(GoldenBookingTable.clinic_id == 4).first()
days_before = json.loads(gt_before.days_json) if gt_before and gt_before.days_json else {}

if '2025-11-17' in days_before:
    day_before = days_before['2025-11-17']
    patients_before = day_before.get('patients', [])
    print(f"   عدد المرضى: {len(patients_before)}")
    print(f"   حالة اليوم: {day_before.get('status')}")
    
    # عد الحالات
    booked = sum(1 for p in patients_before if isinstance(p, dict) and p.get('status') == 'تم الحجز')
    cancelled = sum(1 for p in patients_before if isinstance(p, dict) and p.get('status') == 'ملغى')
    
    print(f"   تم الحجز: {booked}")
    print(f"   ملغى: {cancelled}")

db.close()

# 2. إغلاق اليوم
print("\n2️⃣ إغلاق اليوم...")
close_payload = {
    "clinic_id": 4,
    "date": "2025-11-17"
}
r = client.post('/api/close_table_gold', json=close_payload, headers=headers)
print(f"   Status: {r.status_code}")
print(f"   Response: {r.json()}")

# 3. بعد الإغلاق
print("\n3️⃣ بعد الإغلاق:")

# فحص الجدول
db = SessionLocal()
gt_after = db.query(GoldenBookingTable).filter(GoldenBookingTable.clinic_id == 4).first()

if gt_after:
    days_after = json.loads(gt_after.days_json) if gt_after.days_json else {}
    if '2025-11-17' in days_after:
        print("   ❌ اليوم لا يزال موجوداً في الجدول!")
    else:
        print("   ✅ اليوم تم حذفه من الجدول")
        print(f"   الأيام المتبقية: {list(days_after.keys())}")
else:
    print("   ✅ الجدول تم حذفه بالكامل (لا توجد أيام متبقية)")

# فحص الأرشيف
arch = db.query(GoldenBookingArchive).filter(
    GoldenBookingArchive.clinic_id == 4,
    GoldenBookingArchive.table_date == '2025-11-17'
).first()

if arch:
    print("\n4️⃣ الأرشيف:")
    print(f"   ✅ وُجد في الأرشيف")
    print(f"   إجمالي: {arch.capacity_total}")
    print(f"   معاينة: {arch.capacity_served}")
    print(f"   ملغى: {arch.capacity_cancelled}")
    
    patients_arch = json.loads(arch.patients_json) if arch.patients_json else []
    print(f"   عدد المرضى: {len(patients_arch)}")
    
    # عد الحالات في الأرشيف
    statuses = {}
    for p in patients_arch:
        if isinstance(p, dict):
            s = p.get('status', 'unknown')
            statuses[s] = statuses.get(s, 0) + 1
    
    print(f"   توزيع الحالات في الأرشيف:")
    for status, count in statuses.items():
        emoji = "✅" if status in ('ملغى', 'تمت المعاينة') else "❌"
        print(f"     {emoji} {status}: {count}")
else:
    print("\n4️⃣ الأرشيف:")
    print("   ❌ لم يوجد في الأرشيف!")

db.close()

print("\n" + "=" * 80)
