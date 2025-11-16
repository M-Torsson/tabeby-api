# -*- coding: utf-8 -*-
"""
اختبار close_table_gold على بيانات حقيقية
"""
from fastapi.testclient import TestClient
from app.main import app
import os
import json

os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')

client = TestClient(app)
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print("=" * 80)
print("اختبار close_table_gold على clinic_id=4, date=2025-11-17")
print("=" * 80)

# 1. قبل الإغلاق - عرض حالة المرضى
print("\n1️⃣ حالة المرضى قبل الإغلاق:")
r_before = client.get('/golden_bookings/booking_golden_days?clinic_id=4', headers=headers)
if r_before.status_code == 200:
    data = r_before.json()
    if '2025-11-17' in data.get('days', {}):
        day = data['days']['2025-11-17']
        patients = day.get('patients', [])
        print(f"   عدد المرضى: {len(patients)}")
        print(f"   حالة اليوم: {day.get('status')}")
        
        # عد الحالات
        active_count = sum(1 for p in patients if isinstance(p, dict) and p.get('status') in ('تم الحجز', 'active'))
        cancelled_count = sum(1 for p in patients if isinstance(p, dict) and p.get('status') in ('ملغى', 'cancelled'))
        served_count = sum(1 for p in patients if isinstance(p, dict) and p.get('status') in ('تمت المعاينة', 'served'))
        
        print(f"   تم الحجز/active: {active_count}")
        print(f"   ملغى: {cancelled_count}")
        print(f"   معاينة: {served_count}")
        
        # عرض آخر 3 مرضى
        print("\n   آخر 3 مرضى:")
        for i, p in enumerate(patients[-3:], 1):
            if isinstance(p, dict):
                print(f"      {i}. {p.get('name')} - {p.get('status')} (token={p.get('token')})")
    else:
        print("   ❌ التاريخ 2025-11-17 غير موجود")
        print(f"   التواريخ المتاحة: {list(data.get('days', {}).keys())}")
else:
    print(f"   ❌ خطأ في جلب البيانات: {r_before.status_code}")

print("\n" + "=" * 80)
print("هل تريد متابعة الإغلاق الفعلي؟ (نعم/لا)")
print("=" * 80)
