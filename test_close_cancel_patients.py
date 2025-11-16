"""
اختبار: التأكد من تغيير حالة المرضى إلى ملغى عند إغلاق التيبل
"""
from fastapi.testclient import TestClient
from app.main import app
import os

os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

client = TestClient(app)
headers = {'Doctor-Secret': 'test-secret'}

clinic_id = 85

print("=" * 80)
print("🧪 اختبار إغلاق التيبل وتغيير حالة المرضى إلى ملغى")
print("=" * 80)

# ============================================================================
# اختبار الحجوزات الذهبية
# ============================================================================
print("\n" + "🟡 " * 40)
print("📌 الحجوزات الذهبية")
print("🟡 " * 40)

# إنشاء يوم ذهبي مع مرضى
print("\n1️⃣ إنشاء يوم ذهبي مع 3 مرضى (حالات مختلفة)...")
create_golden = {
    "clinic_id": clinic_id,
    "days": {
        "2025-12-05": {
            "status": "active",
            "capacity_total": 5,
            "capacity_used": 3,
            "opening_time": "09:00",
            "closing_time": "17:00",
            "patients": [
                {
                    "name": "أحمد",
                    "phone": "+9647001",
                    "status": "active",
                    "booking_id": "G-85-20251205-0001",
                    "token": 1
                },
                {
                    "name": "فاطمة",
                    "phone": "+9647002",
                    "status": "قيد الانتظار",
                    "booking_id": "G-85-20251205-0002",
                    "token": 2
                },
                {
                    "name": "علي",
                    "phone": "+9647003",
                    "status": "تمت المعاينة",
                    "booking_id": "G-85-20251205-0003",
                    "token": 3
                }
            ]
        }
    }
}
r1 = client.post('/api/create_golden_table', json=create_golden, headers=headers)
print(f"   STATUS: {r1.status_code}")

# عرض حالة المرضى قبل الإغلاق
print("\n2️⃣ حالة المرضى قبل الإغلاق...")
r2 = client.get(f'/api/booking_golden_days?clinic_id={clinic_id}', headers=headers)
if r2.status_code == 200:
    day_data = r2.json().get('days', {}).get('2025-12-05', {})
    patients_before = day_data.get('patients', [])
    for i, p in enumerate(patients_before, 1):
        print(f"   {i}. {p.get('name')}: {p.get('status')}")

# إغلاق التيبل
print("\n3️⃣ إغلاق التيبل...")
close_payload = {"clinic_id": clinic_id, "date": "2025-12-05"}
r3 = client.post('/api/close_table_gold', json=close_payload, headers=headers)
print(f"   STATUS: {r3.status_code}")
print(f"   {r3.json().get('status')}")

# التحقق من الأرشيف
print("\n4️⃣ التحقق من الأرشيف...")
r4 = client.get(f'/api/golden_booking_archives?clinic_id={clinic_id}', headers=headers)
if r4.status_code == 200:
    archives = r4.json().get('items', [])
    for archive in archives:
        if archive.get('table_date') == '2025-12-05':
            import json
            patients_after = json.loads(archive.get('patients_json', '[]'))
            print(f"   📋 حالة المرضى في الأرشيف:")
            for i, p in enumerate(patients_after, 1):
                status = p.get('status')
                emoji = "✅" if status == "ملغى" or status == "تمت المعاينة" else "❌"
                print(f"      {emoji} {i}. {p.get('name')}: {status}")
            
            # التحقق من النتائج المتوقعة
            print(f"\n   📊 التحقق:")
            
            # أحمد: كان active → يجب أن يصبح ملغى
            ahmad_status = patients_after[0].get('status')
            if ahmad_status == "ملغى":
                print(f"      ✅ أحمد: تم تغيير حالته من 'active' إلى 'ملغى'")
            else:
                print(f"      ❌ أحمد: حالته '{ahmad_status}' (يجب أن تكون 'ملغى')")
            
            # فاطمة: كانت قيد الانتظار → يجب أن تصبح ملغى
            fatima_status = patients_after[1].get('status')
            if fatima_status == "ملغى":
                print(f"      ✅ فاطمة: تم تغيير حالتها من 'قيد الانتظار' إلى 'ملغى'")
            else:
                print(f"      ❌ فاطمة: حالتها '{fatima_status}' (يجب أن تكون 'ملغى')")
            
            # علي: كان تمت المعاينة → يجب أن يبقى تمت المعاينة
            ali_status = patients_after[2].get('status')
            if ali_status == "تمت المعاينة":
                print(f"      ✅ علي: حالته بقيت 'تمت المعاينة' (صحيح)")
            else:
                print(f"      ❌ علي: حالته '{ali_status}' (يجب أن تبقى 'تمت المعاينة')")

print("\n" + "=" * 80)
print("✅ انتهى الاختبار")
print("=" * 80)
