"""
اختبار متقدم: إغلاق تيبل ذهبي مع وجود أيام مؤرشفة
"""
from fastapi.testclient import TestClient
from app.main import app
import os

os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

client = TestClient(app)
headers = {'Doctor-Secret': 'test-secret'}

clinic_id = 85

print("=" * 70)
print("🧪 اختبار إغلاق التيبل الذهبي مع وجود أيام مؤرشفة")
print("=" * 70)

# الخطوة 1: إنشاء 3 أيام
print("\n1️⃣ إنشاء 3 أيام ذهبية...")
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
        },
        "2025-11-26": {
            "status": "active",
            "capacity_total": 5,
            "capacity_used": 0,
            "opening_time": "09:00",
            "closing_time": "17:00",
            "patients": []
        },
        "_archived_2025-11-20": {
            "status": "closed",
            "capacity_total": 3,
            "capacity_used": 2,
            "patients": []
        }
    }
}
r1 = client.post('/api/create_golden_table', json=create_payload, headers=headers)
print(f"   STATUS: {r1.status_code}")
if r1.status_code == 200:
    print(f"   ✅ تم إنشاء 3 أيام (2 نشطة + 1 مؤرشف)")
else:
    print(f"   ❌ {r1.json()}")
    exit()

# الخطوة 2: عرض الأيام
print("\n2️⃣ عرض الأيام الموجودة...")
r2 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)
if r2.status_code == 200:
    days = r2.json().get('days', {})
    print(f"   عدد الأيام الكلي: {len(days)}")
    for date, day_data in days.items():
        status = day_data.get('status', 'N/A')
        print(f"      - {date}: {status}")

# الخطوة 3: إغلاق يوم واحد (2025-11-25)
print("\n3️⃣ إغلاق يوم واحد (2025-11-25)...")
close_payload = {
    "clinic_id": clinic_id,
    "date": "2025-11-25"
}
r3 = client.post('/api/close_table_gold', json=close_payload, headers=headers)
print(f"   STATUS: {r3.status_code}")
if r3.status_code == 200:
    result = r3.json()
    print(f"   ✅ {result.get('status')}")
    print(f"   removed_all: {result.get('removed_all')}")
    
    if result.get('removed_all'):
        print(f"   ⚠️ removed_all = True (لا يجب أن يحذف كل شيء!)")
    else:
        print(f"   ✅ removed_all = False (صحيح! لأن هناك أيام أخرى)")
else:
    print(f"   ❌ {r3.json()}")
    exit()

# الخطوة 4: التحقق من الأيام المتبقية
print("\n4️⃣ التحقق من الأيام المتبقية...")
r4 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)

if r4.status_code == 200:
    days_after = r4.json().get('days', {})
    print(f"   عدد الأيام المتبقية: {len(days_after)}")
    
    for date, day_data in days_after.items():
        status = day_data.get('status', 'N/A')
        print(f"      - {date}: {status}")
    
    # التحقق من النتائج المتوقعة
    print(f"\n   📊 التحقق:")
    if "2025-11-25" in days_after:
        print(f"      ❌ اليوم 2025-11-25 ما زال موجوداً (يجب أن يُحذف)")
    else:
        print(f"      ✅ اليوم 2025-11-25 تم حذفه")
    
    if "2025-11-26" in days_after:
        print(f"      ✅ اليوم 2025-11-26 ما زال موجوداً (صحيح)")
    else:
        print(f"      ❌ اليوم 2025-11-26 محذوف (خطأ!)")
    
    if "_archived_2025-11-20" in days_after:
        print(f"      ✅ اليوم المؤرشف _archived_2025-11-20 ما زال موجوداً (صحيح)")
    else:
        print(f"      ❌ اليوم المؤرشف محذوف (خطأ!)")
        
elif r4.status_code == 404:
    print(f"   ❌ لا يوجد جدول ذهبي (تم حذف كل شيء - خطأ!)")
    print(f"   ⚠️ كان يجب أن يبقى يوم 2025-11-26 واليوم المؤرشف")

# الخطوة 5: إغلاق اليوم الثاني (2025-11-26)
print("\n5️⃣ إغلاق اليوم الثاني (2025-11-26)...")
close_payload2 = {
    "clinic_id": clinic_id,
    "date": "2025-11-26"
}
r5 = client.post('/api/close_table_gold', json=close_payload2, headers=headers)
print(f"   STATUS: {r5.status_code}")
if r5.status_code == 200:
    result = r5.json()
    print(f"   ✅ {result.get('status')}")
    print(f"   removed_all: {result.get('removed_all')}")
    
    # الآن يجب أن يكون removed_all = False لأن هناك يوم مؤرشف
    if result.get('removed_all'):
        print(f"   ⚠️ removed_all = True (خطأ! لأن هناك يوم مؤرشف)")
    else:
        print(f"   ✅ removed_all = False (صحيح! لأن هناك يوم مؤرشف)")
elif r5.status_code == 404:
    print(f"   ⚠️ لا يوجد جدول (تم حذفه بالكامل بعد الإغلاق الأول)")

# الخطوة 6: التحقق النهائي
print("\n6️⃣ التحقق النهائي...")
r6 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)
if r6.status_code == 200:
    days_final = r6.json().get('days', {})
    print(f"   عدد الأيام النهائي: {len(days_final)}")
    if len(days_final) == 1 and "_archived_2025-11-20" in days_final:
        print(f"   ✅ النتيجة صحيحة: بقي فقط اليوم المؤرشف")
    elif len(days_final) == 0:
        print(f"   ❌ تم حذف كل شيء (حتى اليوم المؤرشف!)")
    else:
        print(f"   الأيام المتبقية:")
        for date in days_final.keys():
            print(f"      - {date}")
elif r6.status_code == 404:
    print(f"   ⚠️ لا يوجد جدول (تم حذف كل شيء)")

print("\n" + "=" * 70)
print("✅ انتهى الاختبار المتقدم")
print("=" * 70)
