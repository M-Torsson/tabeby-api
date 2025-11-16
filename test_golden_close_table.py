"""
اختبار إغلاق التيبل الذهبي - التأكد من حذف التيبل بعد الإغلاق
"""
from fastapi.testclient import TestClient
from app.main import app
import os

# تعيين السر للتوثيق
os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

client = TestClient(app)
headers = {'Doctor-Secret': 'test-secret'}

clinic_id = 85
test_date = "2025-11-20"

print("=" * 60)
print("🧪 اختبار إغلاق التيبل الذهبي")
print("=" * 60)

# الخطوة 1: إنشاء يوم ذهبي جديد
print("\n1️⃣ إنشاء يوم ذهبي للاختبار...")
create_payload = {
    "clinic_id": clinic_id,
    "day_date": test_date,
    "capacity_total": 5,
    "opening_time": "09:00",
    "closing_time": "17:00"
}
r1 = client.post('/api/create_golden_day', json=create_payload, headers=headers)
print(f"   STATUS: {r1.status_code}")
if r1.status_code == 200:
    print(f"   ✅ تم إنشاء اليوم الذهبي بنجاح")
else:
    print(f"   ⚠️ {r1.json()}")

# الخطوة 2: عرض الأيام قبل الإغلاق
print("\n2️⃣ عرض الأيام الذهبية قبل الإغلاق...")
r2 = client.get(f'/api/golden_days?clinic_id={clinic_id}', headers=headers)
print(f"   STATUS: {r2.status_code}")
if r2.status_code == 200:
    days_before = r2.json().get('days', {})
    print(f"   عدد الأيام قبل الإغلاق: {len(days_before)}")
    if test_date in days_before:
        print(f"   ✅ اليوم {test_date} موجود في القائمة")
    else:
        print(f"   ⚠️ اليوم {test_date} غير موجود!")

# الخطوة 3: إغلاق التيبل
print(f"\n3️⃣ إغلاق التيبل لليوم {test_date}...")
close_payload = {
    "clinic_id": clinic_id,
    "date": test_date
}
r3 = client.post('/api/close_table_gold', json=close_payload, headers=headers)
print(f"   STATUS: {r3.status_code}")
if r3.status_code == 200:
    result = r3.json()
    print(f"   ✅ {result.get('status')}")
    print(f"   removed_all: {result.get('removed_all')}")
else:
    print(f"   ❌ خطأ: {r3.json()}")

# الخطوة 4: التحقق من حذف اليوم بعد الإغلاق
print("\n4️⃣ التحقق من حذف اليوم بعد الإغلاق...")
r4 = client.get(f'/api/golden_days?clinic_id={clinic_id}', headers=headers)
print(f"   STATUS: {r4.status_code}")
if r4.status_code == 200:
    days_after = r4.json().get('days', {})
    print(f"   عدد الأيام بعد الإغلاق: {len(days_after)}")
    if test_date in days_after:
        print(f"   ❌ اليوم {test_date} ما زال موجوداً في القائمة!")
        print(f"   حالة اليوم: {days_after[test_date].get('status')}")
    else:
        print(f"   ✅ اليوم {test_date} تم حذفه من القائمة بنجاح")

# الخطوة 5: التحقق من وجود اليوم في الأرشيف
print("\n5️⃣ التحقق من حفظ اليوم في الأرشيف...")
r5 = client.get(f'/api/golden_booking_archives?clinic_id={clinic_id}', headers=headers)
print(f"   STATUS: {r5.status_code}")
if r5.status_code == 200:
    archives = r5.json().get('items', [])
    found_in_archive = False
    for archive in archives:
        if archive.get('table_date') == test_date:
            found_in_archive = True
            print(f"   ✅ اليوم محفوظ في الأرشيف:")
            print(f"      - التاريخ: {archive.get('table_date')}")
            print(f"      - السعة: {archive.get('capacity_total')}")
            print(f"      - المرضى: {archive.get('capacity_served')} تمت المعاينة")
            print(f"      - الملغيين: {archive.get('capacity_cancelled')}")
            break
    
    if not found_in_archive:
        print(f"   ⚠️ اليوم غير موجود في الأرشيف")

print("\n" + "=" * 60)
print("✅ انتهى الاختبار")
print("=" * 60)
