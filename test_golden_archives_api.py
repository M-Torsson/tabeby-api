"""
اختبار سريع لـ API جلب أرشيف الحجوزات الذهبية
"""
from fastapi.testclient import TestClient
from app.main import app
import os

# إعداد السر
os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')

client = TestClient(app)
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print("=" * 80)
print("🧪 اختبار API أرشيف الحجوزات الذهبية")
print("=" * 80)

# اختبار 1: جلب كل الأرشيف
print("\n1️⃣ اختبار: جلب كل أرشيف الحجوزات الذهبية")
print("-" * 80)
r = client.get('/api/golden_booking_archives/4', headers=headers)
print(f"Status Code: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"✅ نجح الطلب")
    print(f"   Clinic ID: {data.get('clinic_id')}")
    print(f"   عدد الأيام المؤرشفة: {len(data.get('items', []))}")
    
    if data.get('items'):
        first_item = data['items'][0]
        print(f"\n   أول يوم مؤرشف:")
        print(f"   - التاريخ: {first_item.get('table_date')}")
        print(f"   - السعة الكلية: {first_item.get('capacity_total')}")
        print(f"   - المخدومين: {first_item.get('capacity_served')}")
        print(f"   - الملغيين: {first_item.get('capacity_cancelled')}")
        print(f"   - عدد المرضى: {len(first_item.get('patients', []))}")
        
        if first_item.get('patients'):
            first_patient = first_item['patients'][0]
            print(f"\n   أول مريض:")
            print(f"   - الاسم: {first_patient.get('name')}")
            print(f"   - الهاتف: {first_patient.get('phone')}")
            print(f"   - الحالة: {first_patient.get('status')}")
            print(f"   - الكود: {first_patient.get('code')}")
            print(f"   - التوكن: {first_patient.get('token')}")
    else:
        print("   ℹ️  لا توجد أيام مؤرشفة بعد")
else:
    print(f"❌ فشل الطلب: {r.json()}")

# اختبار 2: جلب أرشيف بنطاق تاريخي
print("\n2️⃣ اختبار: جلب أرشيف بنطاق تاريخي")
print("-" * 80)
r2 = client.get(
    '/api/golden_booking_archives/4',
    headers=headers,
    params={'from_date': '2025-11-01', 'to_date': '2025-11-30'}
)
print(f"Status Code: {r2.status_code}")
if r2.status_code == 200:
    data2 = r2.json()
    print(f"✅ نجح الطلب")
    print(f"   عدد الأيام في نطاق نوفمبر: {len(data2.get('items', []))}")
else:
    print(f"❌ فشل الطلب: {r2.json()}")

# اختبار 3: جلب عدد محدود من الأيام
print("\n3️⃣ اختبار: جلب آخر 5 أيام فقط")
print("-" * 80)
r3 = client.get(
    '/api/golden_booking_archives/4',
    headers=headers,
    params={'limit': 5}
)
print(f"Status Code: {r3.status_code}")
if r3.status_code == 200:
    data3 = r3.json()
    print(f"✅ نجح الطلب")
    print(f"   عدد الأيام المرجعة: {len(data3.get('items', []))}")
else:
    print(f"❌ فشل الطلب: {r3.json()}")

# اختبار 4: اختبار بدون Header (يجب أن يفشل)
print("\n4️⃣ اختبار: الطلب بدون Doctor-Secret (يجب أن يفشل)")
print("-" * 80)
r4 = client.get('/api/golden_booking_archives/4')
print(f"Status Code: {r4.status_code}")
if r4.status_code == 403:
    print(f"✅ نجح الاختبار - تم رفض الطلب كما هو متوقع")
else:
    print(f"⚠️  نتيجة غير متوقعة: {r4.status_code}")

# اختبار 5: مقارنة مع أرشيف الحجوزات العادية
print("\n5️⃣ مقارنة: أرشيف الحجوزات العادية vs الذهبية")
print("-" * 80)
r_regular = client.get('/api/booking_archives/4', headers=headers)
r_golden = client.get('/api/golden_booking_archives/4', headers=headers)

if r_regular.status_code == 200 and r_golden.status_code == 200:
    regular_count = len(r_regular.json().get('items', []))
    golden_count = len(r_golden.json().get('items', []))
    
    print(f"✅ كلا الطلبين نجحا")
    print(f"   📊 أرشيف الحجوزات العادية: {regular_count} يوم")
    print(f"   🌟 أرشيف الحجوزات الذهبية: {golden_count} يوم")
else:
    print(f"⚠️  أحد الطلبين فشل")

print("\n" + "=" * 80)
print("✅ انتهى الاختبار")
print("=" * 80)
