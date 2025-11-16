"""
اختبار بسيط: إغلاق تيبل ذهبي موجود
"""
from fastapi.testclient import TestClient
from app.main import app
import os

os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

client = TestClient(app)
headers = {'Doctor-Secret': 'test-secret'}

clinic_id = 85

print("=" * 70)
print("🧪 اختبار إغلاق التيبل الذهبي")
print("=" * 70)

# الخطوة 1: عرض الأيام الذهبية الموجودة
print("\n1️⃣ عرض الأيام الذهبية الموجودة...")
r1 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)
print(f"   STATUS: {r1.status_code}")

if r1.status_code != 200:
    print(f"   ⚠️ لا يوجد أيام ذهبية للعيادة {clinic_id}")
    print("   سننشئ يوم جديد للاختبار...")
    
    # إنشاء يوم جديد
    create_payload = {
        "clinic_id": clinic_id,
        "days": {
            "2025-11-25": {
                "status": "active",
                "capacity_total": 5,
                "capacity_used": 0,
                "opening_time": "09:00",
                "closing_time": "17:00",
                "patients": []
            }
        }
    }
    r_create = client.post('/api/create_golden_table', json=create_payload, headers=headers)
    print(f"   إنشاء يوم جديد - STATUS: {r_create.status_code}")
    if r_create.status_code == 200:
        print(f"   ✅ {r_create.json()}")
        test_date = "2025-11-25"
    else:
        print(f"   ❌ فشل الإنشاء: {r_create.json()}")
        exit()
else:
    days_data = r1.json()
    days = days_data.get('days', {})
    print(f"   عدد الأيام الموجودة: {len(days)}")
    
    if len(days) == 0:
        print("   ⚠️ لا يوجد أيام، سننشئ يوم جديد...")
        create_payload = {
            "clinic_id": clinic_id,
            "days": {
                "2025-11-25": {
                    "status": "active",
                    "capacity_total": 5,
                    "capacity_used": 0,
                    "opening_time": "09:00",
                    "closing_time": "17:00",
                    "patients": []
                }
            }
        }
        r_create = client.post('/api/create_golden_table', json=create_payload, headers=headers)
        if r_create.status_code == 200:
            test_date = "2025-11-25"
            print(f"   ✅ تم إنشاء يوم {test_date}")
        else:
            exit()
    else:
        # نختار أول يوم موجود
        test_date = list(days.keys())[0]
        print(f"   سنختبر على اليوم: {test_date}")
        print(f"   حالة اليوم: {days[test_date].get('status')}")
        print(f"   السعة: {days[test_date].get('capacity_used')}/{days[test_date].get('capacity_total')}")

# الخطوة 2: عد الأيام قبل الإغلاق
print(f"\n2️⃣ عد الأيام قبل الإغلاق...")
r2 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)
days_before = r2.json().get('days', {})
count_before = len(days_before)
print(f"   عدد الأيام قبل الإغلاق: {count_before}")

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
    exit()

# الخطوة 4: عد الأيام بعد الإغلاق
print(f"\n4️⃣ عد الأيام بعد الإغلاق...")
r4 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)
print(f"   STATUS: {r4.status_code}")

if r4.status_code == 200:
    days_after = r4.json().get('days', {})
    count_after = len(days_after)
    print(f"   عدد الأيام بعد الإغلاق: {count_after}")
    
    if test_date in days_after:
        print(f"   ❌ اليوم {test_date} ما زال موجوداً!")
        print(f"   حالته: {days_after[test_date].get('status')}")
    else:
        print(f"   ✅ اليوم {test_date} تم حذفه بنجاح")
    
    print(f"\n   📊 المقارنة:")
    print(f"      قبل الإغلاق: {count_before} يوم")
    print(f"      بعد الإغلاق: {count_after} يوم")
    print(f"      الفرق: {count_before - count_after} يوم")
elif r4.status_code == 404:
    print(f"   ✅ لا يوجد جدول ذهبي للعيادة (تم حذف كل الأيام)")
    print(f"   📊 تم حذف {count_before} يوم (كل الأيام)")

print("\n" + "=" * 70)
print("✅ انتهى الاختبار")
print("=" * 70)
