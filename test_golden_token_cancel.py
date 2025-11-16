# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient
from app.main import app
import json
import os

os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

c = TestClient(app)
headers = {'Doctor-Secret': 'test-secret'}

print("=" * 70)
print("🧪 اختبار إلغاء الحجز الذهبي بـ booking_id + token")
print("=" * 70)

# 1. إنشاء حجز ذهبي
print("\n1️⃣ حجز ذهبي جديد")
r1 = c.post('/api/patient_golden_booking', json={
    "clinic_id": 4,
    "date": "2025-12-01",
    "patient_id": "P-TOKEN-TEST",
    "name": "مريض اختبار التوكن",
    "phone": "+9647001234567",
    "auto_assign": True
}, headers=headers)

if r1.status_code == 200:
    data = r1.json()
    booking_id = data['booking_id']
    token = data['token']
    print(f"✅ تم الحجز: booking_id={booking_id}, token={token}")
else:
    print(f"❌ فشل الحجز: {r1.status_code} - {r1.text}")
    exit(1)

# 2. التحقق من الحجز
print("\n2️⃣ التحقق من الحجز")
r2 = c.get(f'/api/booking_golden_days?clinic_id=4', headers=headers)
if r2.status_code == 200:
    days = r2.json().get('days', {})
    day = days.get('2025-12-01', {})
    patients = day.get('patients', [])
    found = [p for p in patients if p.get('booking_id') == booking_id]
    if found:
        p = found[0]
        print(f"✅ الحجز موجود: status={p['status']}, token={p['token']}")
    else:
        print("❌ الحجز غير موجود!")

# 3. محاولة إلغاء بدون token (الطريقة القديمة)
print("\n3️⃣ محاولة إلغاء بـ booking_id فقط (بدون token)")
r3 = c.post('/api/edit_patient_gold_booking', json={
    "clinic_id": 4,
    "booking_id": booking_id,
    "status": "ملغى"
}, headers=headers)

if r3.status_code == 200:
    data = r3.json()
    print(f"✅ نجح الإلغاء: old_status={data['old_status']}, new_status={data['new_status']}")
else:
    print(f"❌ فشل الإلغاء: {r3.status_code} - {r3.text}")

# 4. التحقق بعد الإلغاء
print("\n4️⃣ التحقق بعد الإلغاء")
r4 = c.get(f'/api/booking_golden_days?clinic_id=4', headers=headers)
if r4.status_code == 200:
    days = r4.json().get('days', {})
    day = days.get('2025-12-01', {})
    patients = day.get('patients', [])
    print(f"   عدد المرضى: {len(patients)}")
    for p in patients:
        print(f"   - booking_id={p.get('booking_id')}, status={p.get('status')}, token={p.get('token')}")

# 5. حجز جديد لنفس المريض
print("\n5️⃣ حجز جديد لنفس المريض")
r5 = c.post('/api/patient_golden_booking', json={
    "clinic_id": 4,
    "date": "2025-12-01",
    "patient_id": "P-TOKEN-TEST",
    "name": "مريض اختبار التوكن",
    "phone": "+9647001234567",
    "auto_assign": True
}, headers=headers)

if r5.status_code == 200:
    data = r5.json()
    new_booking_id = data['booking_id']
    new_token = data['token']
    print(f"✅ تم الحجز الجديد: booking_id={new_booking_id}, token={new_token}")
else:
    print(f"❌ فشل الحجز: {r5.status_code} - {r5.text}")

# 6. التحقق من الوضع الآن (يجب أن يكون هناك حجز ملغى + حجز نشط)
print("\n6️⃣ الوضع النهائي")
r6 = c.get(f'/api/booking_golden_days?clinic_id=4', headers=headers)
if r6.status_code == 200:
    days = r6.json().get('days', {})
    day = days.get('2025-12-01', {})
    patients = day.get('patients', [])
    print(f"   عدد المرضى الكلي: {len(patients)}")
    active = [p for p in patients if p.get('status') != 'ملغى']
    cancelled = [p for p in patients if p.get('status') == 'ملغى']
    print(f"   النشط: {len(active)}, الملغى: {len(cancelled)}")
    for p in patients:
        print(f"   - booking_id={p.get('booking_id')}, status={p.get('status')}, token={p.get('token')}")

# 7. ✅ الاختبار الأهم: إلغاء بـ booking_id + token
print("\n7️⃣ إلغاء الحجز النشط بـ booking_id + token (الطريقة الجديدة)")
r7 = c.post('/api/edit_patient_gold_booking', json={
    "clinic_id": 4,
    "booking_id": new_booking_id,
    "token": new_token,  # ✅ نرسل التوكن
    "status": "ملغى"
}, headers=headers)

if r7.status_code == 200:
    data = r7.json()
    print(f"✅ نجح الإلغاء بالتوكن!")
    print(f"   old_status={data['old_status']}, new_status={data['new_status']}")
else:
    print(f"❌ فشل الإلغاء: {r7.status_code} - {r7.text}")

# 8. التحقق النهائي
print("\n8️⃣ التحقق النهائي")
r8 = c.get(f'/api/booking_golden_days?clinic_id=4', headers=headers)
if r8.status_code == 200:
    days = r8.json().get('days', {})
    day = days.get('2025-12-01', {})
    patients = day.get('patients', [])
    capacity_used = day.get('capacity_used', 0)
    print(f"   capacity_used: {capacity_used}")
    print(f"   عدد المرضى الكلي: {len(patients)}")
    for p in patients:
        print(f"   - booking_id={p.get('booking_id')}, status={p.get('status')}, token={p.get('token')}")
    
    # التحقق: يجب أن يكون capacity_used = 0
    if capacity_used == 0:
        print("\n✅ اختبار ناجح! capacity_used = 0 (جميع الحجوزات ملغاة)")
    else:
        print(f"\n❌ خطأ: capacity_used = {capacity_used} (يجب أن يكون 0)")

print("\n" + "=" * 70)
print("📋 الخلاصة")
print("=" * 70)
print("✅ الآن يمكن للفرونت اند استخدام:")
print("   - booking_id فقط: يلغي أول حجز مطابق")
print("   - booking_id + token: يلغي الحجز النشط فقط (الموصى به)")
print("=" * 70)
